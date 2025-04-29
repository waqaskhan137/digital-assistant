# Classification Service

This service is responsible for analyzing incoming emails and classifying them into different categories (such as support, important, spam, etc.) based on configurable rules.

## Overview

The Classification Service consumes email messages from a RabbitMQ queue, applies classification logic to determine the email's category and priority, and then publishes the results to another queue for downstream processing.

## Features

- Rule-based email classification with configurable rules
- Support for complex logical conditions (AND, OR, NOT)
- Regular expression pattern matching
- Rule usage statistics and monitoring
- Resilient RabbitMQ connections with automatic recovery
- Comprehensive logging

## Architecture

The service follows a clean architecture pattern with distinct components:

- **Core**: Contains the classification logic and interfaces
- **Consumer**: Handles RabbitMQ message consumption
- **Publisher**: Sends classification results to output queue
- **Config**: Manages service configuration
- **Models**: Defines data structures

## Configuration

The service can be configured using environment variables:

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| `RABBITMQ_HOST` | RabbitMQ host address | localhost |
| `RABBITMQ_PORT` | RabbitMQ port | 5672 |
| `RABBITMQ_USER` | RabbitMQ username | guest |
| `RABBITMQ_PASSWORD` | RabbitMQ password | guest |
| `RABBITMQ_VHOST` | RabbitMQ virtual host | / |
| `CLASSIFICATION_INPUT_QUEUE` | Input queue name | email_to_classify |
| `CLASSIFICATION_OUTPUT_QUEUE` | Output queue name | classification_results |
| `RULES_CONFIG_PATH` | Path to rules configuration file | src/rules.json |
| `LOG_LEVEL` | Logging level | INFO |

## Custom Rules

Rules can be defined in a JSON configuration file. The default location is `src/rules.json`, but this can be changed with the `RULES_CONFIG_PATH` environment variable.

Example rule configuration:

```json
{
  "rules": [
    {
      "name": "Support Request",
      "category": "support",
      "needs_reply": true,
      "condition": {
        "operator": "or",
        "conditions": [
          {
            "field": "subject",
            "pattern": "help"
          },
          {
            "field": "recipient",
            "pattern": "support@"
          }
        ]
      },
      "confidence": 0.9,
      "priority": 2,
      "explanation": "Email appears to be a support request"
    }
  ]
}
```

### Rule Conditions

- **Simple conditions** match a specific field against a pattern
- **Compound conditions** use logical operators (and, or, not) to combine multiple conditions
- **Regular expressions** can be used for complex pattern matching (prefix with "regex:")

### Available Fields

- `sender`: Email sender address
- `recipient`: Email recipient address
- `subject`: Email subject line
- `body`: Email body (text version)
- `body_html`: Email body (HTML version)
- `has_attachments`: Boolean indicating if attachments are present
- `date`: Email date
- `thread_id`: Email thread ID
- `labels`: Email labels

## API Endpoints

- `GET /health`: Health check endpoint
- `GET /rules`: List all configured rules and their statistics
- `GET /rules/stats`: Get detailed statistics about rule usage

## Running the Service

### Using Docker

```bash
docker build -t classification-service .
docker run -p 8003:8000 \
  -e RABBITMQ_HOST=rabbitmq \
  -e CLASSIFICATION_INPUT_QUEUE=email_to_classify \
  -e CLASSIFICATION_OUTPUT_QUEUE=classification_results \
  classification-service
```

### Using Docker Compose

```bash
docker-compose up classification-service
```

## Development

### Setting Up the Development Environment

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the service:
   ```
   uvicorn src.main:app --reload
   ```

### Running Tests

```bash
pytest
```

To run integration tests with RabbitMQ:

```bash
pytest tests/integration/test_rabbitmq_integration.py
```

## Message Format

### Input (Email Message)

The service expects messages in the following format:

```json
{
  "message_id": "unique-id",
  "thread_id": "thread-id",
  "sender": "sender@example.com",
  "recipient": "recipient@example.com",
  "subject": "Email subject",
  "body_text": "Email body in plain text",
  "body_html": "<p>Email body in HTML</p>",
  "date": "2023-01-01T00:00:00Z",
  "labels": ["INBOX", "IMPORTANT"],
  "attachments": []
}
```

### Output (Classification Result)

The service produces classification results in the following format:

```json
{
  "category": "support",
  "needs_reply": true,
  "confidence": 0.9,
  "priority": 2,
  "email_id": "unique-id",
  "explanation": "Email appears to be a support request"
}
```

## License

This project is proprietary and confidential.