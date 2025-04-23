# Gmail Automation Project

A microservices-based application for automating Gmail categorization and response generation.

## Project Overview

The Gmail Automation project is a collection of microservices that work together to:
1. Authenticate with users' Gmail accounts via OAuth 2.0
2. Ingest emails from Gmail API
3. Categorize and label emails using rule-based and ML-based classification
4. Generate draft responses using AI for emails that need replies
5. Save responses as drafts in Gmail

## Architecture

The project follows a microservices architecture with strict separation of concerns:

1. **Auth Service**: Handles OAuth 2.0 authentication with Gmail API
2. **Email Ingestion Service**: Retrieves emails from Gmail API
3. **Classification Service**: Categorizes emails and determines if they need replies
4. **Response Generation Service**: Generates email responses using AI
5. **Draft Management Service**: Saves responses as drafts in Gmail
6. **API Gateway**: Routes requests to appropriate microservices

## Technology Stack

- **Language**: Python
- **Framework**: FastAPI
- **Messaging**: RabbitMQ
- **Storage**: Redis for token management
- **Containerization**: Docker and Docker Compose
- **AI Integration**: OpenAI API (with adapter pattern for flexibility)
- **Testing**: pytest with TDD approach

## Development Approach

This project follows the Test-Driven Development (TDD) methodology:
1. Write tests first
2. Implement code to make tests pass
3. Refactor while maintaining passing tests

We also adhere to the single responsibility principle, with each microservice having a clear, focused purpose.

## Project Structure

```
gmail-automation/
├── services/
│   ├── auth_service/           # OAuth authentication
│   ├── email_service/          # Email ingestion from Gmail API
│   ├── classification_service/ # Email categorization
│   ├── response_service/       # AI response generation
│   ├── draft_service/          # Draft creation in Gmail
│   └── api_gateway/            # API routing and coordination
├── shared/
│   ├── models/                 # Shared data models
│   └── utils/                  # Shared utilities
├── docker-compose.yml          # Service orchestration
└── README.md                   # Project documentation
```

## Current Progress

- ✅ Project architecture defined
- ✅ Auth Service implemented with TDD (OAuth flow, token management)
- ⬜️ Email Ingestion Service
- ⬜️ Classification Service
- ⬜️ Response Generation Service
- ⬜️ Draft Management Service
- ⬜️ API Gateway

## Getting Started

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Google OAuth credentials
- OpenAI API key (for response generation)

### Environment Setup

Create a `.env` file in the project root with the following variables:

```
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
REDIRECT_URI=http://localhost:8000/auth/callback
OPENAI_API_KEY=your_openai_api_key
```

### Running the Services

```bash
# Start all services
docker-compose up

# Run tests for all services
python -m pytest

# Run tests for a specific service
python -m pytest services/auth_service/tests/
```

## Next Steps

1. Implement Email Ingestion Service using TDD
2. Develop Classification Service with rule-based approach
3. Create Response Generation Service with AI integration
4. Implement Draft Management Service
5. Set up API Gateway for service coordination