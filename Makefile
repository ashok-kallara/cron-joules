.PHONY: sync test lint format invoke-local invoke-telegram local-api build deploy clean help

# Default target
help:
	@echo "Cron Joules - Available commands:"
	@echo ""
	@echo "  make sync           - Install dependencies with uv"
	@echo "  make test           - Run unit tests"
	@echo "  make lint           - Run linting checks"
	@echo "  make format         - Format code with ruff"
	@echo "  make invoke-local   - Invoke CheckBattery Lambda locally"
	@echo "  make invoke-telegram - Invoke Telegram webhook locally"
	@echo "  make local-api      - Start local API Gateway"
	@echo "  make build          - Build SAM application"
	@echo "  make deploy         - Deploy to AWS"
	@echo "  make clean          - Clean build artifacts"

# Install dependencies
sync:
	uv sync

# Run unit tests
test:
	uv run pytest tests/ -v --cov=src --cov-report=term-missing

# Run tests with HTML coverage report
test-cov:
	uv run pytest tests/ -v --cov=src --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# Run linting
lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

# Format code
format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

# Invoke CheckBattery Lambda locally
invoke-local:
	sam local invoke CheckBatteryFunction --env-vars .env.json

# Invoke Telegram webhook locally with test event
invoke-telegram:
	sam local invoke TelegramWebhookFunction -e events/telegram_status.json --env-vars .env.json

# Invoke Assistant query locally
invoke-assistant:
	sam local invoke AssistantQueryFunction -e events/assistant_query.json --env-vars .env.json

# Start local API Gateway
local-api:
	sam local start-api --env-vars .env.json

# Check that AWS SAM CLI is installed (required for build/deploy)
check-sam:
	@command -v sam >/dev/null 2>&1 || { echo ""; echo "Error: AWS SAM CLI is not installed."; echo "Install it with: brew install aws-sam-cli"; echo "See: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"; echo ""; exit 1; }

# Export requirements and build SAM application
build: check-sam
	uv export --no-hashes --no-dev > requirements.txt
	sam build

# Deploy to AWS
deploy: build
	sam deploy

# Deploy with guided setup (first time)
deploy-guided: build
	sam deploy --guided

# Clean build artifacts
clean:
	rm -rf .aws-sam/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -f requirements.txt
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Validate SAM template
validate:
	sam validate

# View CloudFormation logs
logs:
	sam logs --stack-name cron-joules --tail
