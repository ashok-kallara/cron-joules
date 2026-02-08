"""Pytest fixtures and configuration."""

import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# Set test environment variables before importing modules
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["DYNAMODB_TABLE"] = "cron-joules-test"
os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb_table(aws_credentials):
    """Create mock DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="cron-joules-test",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table


@pytest.fixture
def mock_kia_credentials():
    """Mock Kia Connect credentials."""
    with patch("utils.secrets.get_kia_credentials") as mock:
        mock.return_value = {
            "username": "test@example.com",
            "password": "testpassword",
            "pin": "1234",
        }
        yield mock


@pytest.fixture
def mock_telegram_config():
    """Mock Telegram configuration."""
    with patch("utils.secrets.get_telegram_config") as mock:
        mock.return_value = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "-1001234567890",
        }
        yield mock


@pytest.fixture
def mock_vehicle_status():
    """Mock vehicle status response."""
    from services.kia_client import VehicleStatus

    return VehicleStatus(
        battery_level=40,
        is_charging=False,
        is_plugged_in=False,
        estimated_range=120,
        last_updated="2024-01-15 10:30:00",
    )


@pytest.fixture
def mock_kia_client(mock_vehicle_status):
    """Mock KiaClient for testing."""
    with patch("services.kia_client.get_vehicle_status") as mock:
        mock.return_value = mock_vehicle_status
        yield mock


@pytest.fixture
def mock_telegram_send():
    """Mock Telegram send_message."""
    with patch("services.telegram_client.send_message") as mock:
        mock.return_value = {"ok": True, "result": {"message_id": 123}}
        yield mock


@pytest.fixture
def lambda_context():
    """Create mock Lambda context."""
    context = MagicMock()
    context.function_name = "test-function"
    context.memory_limit_in_mb = 256
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
    context.aws_request_id = "test-request-id"
    return context
