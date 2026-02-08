# Cron Joules

A serverless reminder system for Kia EV6 that sends Telegram notifications when your car needs charging.

## Features

- **Scheduled Checks**: Automatically checks battery at 7 PM and 10 PM daily
- **Smart Reminders**: Only notifies when battery is below threshold AND charger is not connected
- **Follow-up Alerts**: Sends a second reminder at 10 PM if car still isn't charging
- **Telegram Bot Commands**:
  - `/status` - Check current battery level
  - `/vacation on/off` - Disable/enable reminders when away
  - `/threshold <number>` - Set battery threshold (default: 45%)
  - `/config` - View current settings
- **Google Assistant** (optional): Ask "Does my car need charging?" via IFTTT integration

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  EventBridge    │────▶│  Lambda          │────▶│  Telegram       │
│  (7PM & 10PM)   │     │  (check_battery) │     │  Bot API        │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                                 ▼
┌─────────────────┐     ┌──────────────────┐
│  Kia Connect    │◀────│  DynamoDB        │
│  API            │     │  (config)        │
└─────────────────┘     └──────────────────┘
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) - Python package manager
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) — on macOS: `brew install aws-sam-cli`
- AWS account with credentials configured
- Kia Connect account (with EV6 registered)
- Telegram account

## Setup

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/yourusername/cron-joules.git
cd cron-joules
uv sync
```

### 2. Install AWS SAM CLI

Required for `make build` and `make deploy-guided`. On macOS:

```bash
brew install aws-sam-cli
```

Other platforms: see [Install the AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html).

### 3. Create Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Save the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Add the bot to your group or start a chat with it
5. Get your chat ID using [@userinfobot](https://t.me/userinfobot)

### 4. Configure AWS credentials

Deploy and SSM commands need valid AWS credentials. Configure them first:

```bash
# Option A: Interactive (access key + secret from IAM)
aws configure

# Option B: AWS SSO
aws sso login --profile your-profile
export AWS_PROFILE=your-profile
```

Verify with: `aws sts get-caller-identity`

### 5. Store Secrets in AWS SSM Parameter Store

```bash
# Kia Connect credentials
aws ssm put-parameter --name "/cron-joules/kia/username" --value "your-email" --type SecureString
aws ssm put-parameter --name "/cron-joules/kia/password" --value "your-password" --type SecureString
aws ssm put-parameter --name "/cron-joules/kia/pin" --value "1234" --type SecureString

# Telegram configuration
aws ssm put-parameter --name "/cron-joules/telegram/bot_token" --value "your-bot-token" --type SecureString
aws ssm put-parameter --name "/cron-joules/telegram/chat_id" --value "-1001234567890" --type String

# Webhook security secrets
aws ssm put-parameter --name "/cron-joules/telegram/webhook_secret" --value "$(openssl rand -hex 32)" --type SecureString
aws ssm put-parameter --name "/cron-joules/assistant/webhook_secret" --value "$(openssl rand -hex 32)" --type SecureString
```

### 6. Deploy to AWS

```bash
# First time deployment (guided)
make deploy-guided

# Subsequent deployments
make deploy
```

### 7. Set Up Telegram Webhook

After deployment, get the webhook URL from the CloudFormation outputs and register it with Telegram.
Include the `secret_token` parameter so Telegram sends it in the `X-Telegram-Bot-Api-Secret-Token`
header on every webhook request (must match the value you stored in SSM above):

```bash
# Get the webhook URL from deployment output
WEBHOOK_URL="https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/telegram/webhook"

# Retrieve the secret you stored in SSM (or use the same value you generated)
WEBHOOK_SECRET=$(aws ssm get-parameter --name "/cron-joules/telegram/webhook_secret" --with-decryption --query "Parameter.Value" --output text)

# Register webhook with Telegram (includes secret_token for request verification)
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=${WEBHOOK_URL}&secret_token=${WEBHOOK_SECRET}"
```

## Local Development

### Run Tests

```bash
make test
```

### Run Linting

```bash
make lint
```

### Format Code

```bash
make format
```

### Invoke Lambda Locally

```bash
# Create .env.json for local testing
cp .env.example .env
# Edit .env with your credentials, then create .env.json:
cat > .env.json << 'EOF'
{
  "CheckBatteryFunction": {
    "KIA_USERNAME": "your-email",
    "KIA_PASSWORD": "your-password",
    "KIA_PIN": "1234",
    "TELEGRAM_BOT_TOKEN": "your-token",
    "TELEGRAM_WEBHOOK_SECRET": "your-telegram-webhook-secret",
    "TELEGRAM_CHAT_ID": "-1001234567890",
    "DYNAMODB_TABLE": "cron-joules-dev"
  }
}
EOF

# Invoke the check battery function
make invoke-local
```

### Start Local API

```bash
make local-api
# Then test with: curl -X POST http://localhost:3000/telegram/webhook -d '...'
```

### Local end-to-end testing (including real Telegram)

You can test the full flow locally in two ways.

#### Option A: Invoke the Telegram webhook Lambda locally (real replies in Telegram)

This runs the handler with a fake “Telegram update” event. The handler calls the real Kia API and sends a **real reply** to your Telegram chat.

1. **Create `.env.json`** with credentials for local invocation (see “Invoke Lambda Locally” above). Use the same structure for `TelegramWebhookFunction`:

   ```json
   {
     "TelegramWebhookFunction": {
       "KIA_USERNAME": "your-email",
       "KIA_PASSWORD": "your-password",
       "KIA_PIN": "1234",
       "TELEGRAM_BOT_TOKEN": "your-bot-token",
       "TELEGRAM_WEBHOOK_SECRET": "your-telegram-webhook-secret",
       "TELEGRAM_CHAT_ID": "-1001234567890",
       "DYNAMODB_TABLE": "cron-joules-dev"
     }
   }
   ```

2. **Ensure the DynamoDB table exists** (e.g. deploy once with `make deploy-guided` or create the table in AWS). Local runs use `DYNAMODB_TABLE` and your default AWS credentials.

3. **Invoke with a sample event** (the handler sends a real reply to the chat ID in the event):

   ```bash
   make invoke-telegram
   ```

   The reply goes to the `chat.id` in the event JSON. To receive it in your chat, edit `events/telegram_status.json` and set `"chat": {"id": YOUR_CHAT_ID, ...}` (same value as `TELEGRAM_CHAT_ID`).

   To simulate other commands, invoke with a different event:

   ```bash
   sam local invoke TelegramWebhookFunction -e events/telegram_vacation_on.json --env-vars .env.json
   ```

   Or build your own event and pass it with `-e your_event.json`.

#### Option B: Real Telegram → local API (full E2E with your phone/client)

Telegram sends updates to your machine; your local API runs the handler and the bot replies in the same chat.

1. **Create `.env.json`** as in Option A (include `TelegramWebhookFunction` with Kia, Telegram, and `DYNAMODB_TABLE`).

2. **Start the local API:**

   ```bash
   make local-api
   ```

   Leave it running. By default the API is at `http://127.0.0.1:3000`.

3. **Expose it with a tunnel** so Telegram can reach your machine (e.g. [ngrok](https://ngrok.com)):

   ```bash
   ngrok http 3000
   ```

   Note the HTTPS URL ngrok gives you (e.g. `https://abc123.ngrok.io`).

4. **Set the Telegram webhook** to your tunnel URL:

   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://YOUR_NGROK_URL/telegram/webhook"
   ```

   Example: if ngrok URL is `https://abc123.ngrok.io`:

   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://abc123.ngrok.io/telegram/webhook"
   ```

5. **Send commands in Telegram** (to the bot in a group or DM). You should see the request in the terminal running `make local-api` and the bot’s reply in Telegram.

6. **Unset the webhook when done** (so production or polling works as intended):

   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook"
   ```

## Google Assistant Integration (Optional)

To enable "Hey Google, does my car need charging?":

1. Create an [IFTTT](https://ifttt.com) account
2. Create a new Applet:
   - **Trigger**: Google Assistant V2 → "Activate scene"
   - **Action**: Webhooks → Make a web request
     - URL: Your Assistant Query URL (from deployment outputs)
     - Method: POST
     - Content Type: application/json
     - Additional Headers: `X-Webhook-Secret: <your-assistant-webhook-secret>` (the value stored in SSM)
3. In Google Home app, create a Routine:
   - **Trigger**: "Does my car need charging?"
   - **Action**: Adjust home devices → Adjust scene → Select your IFTTT scene

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Battery threshold | 45% | Send reminder if battery below this level |
| Check times | 7 PM, 10 PM | When to check battery (configurable in template.yaml) |
| Timezone | America/Los_Angeles | Timezone for scheduled checks |

## Troubleshooting

### Check CloudWatch Logs

```bash
make logs
```

### Common Issues

1. **"No vehicles found"**: Make sure your EV6 is registered in the Kia Connect app
2. **"Missing Kia Connect credentials"**: Verify SSM parameters are set correctly
3. **Telegram not responding**: Check webhook is registered and bot has admin rights in group

## Cost Estimate

This solution runs entirely within AWS free tier:
- Lambda: ~60 invocations/month (well under 1M free)
- DynamoDB: ~100 read/write units/month (25 GB free)
- EventBridge: 2 scheduled rules (free)
- API Gateway: ~100 requests/month (1M free)

**Estimated monthly cost: $0**

## License

MIT
