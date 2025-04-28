# Technical Context

## Technology Stack

### Backend
- **Language**: Python (finalized)
- **Framework**: FastAPI for all microservices
  - Using modern lifespan handlers for application lifecycle management
  - Leveraging asynccontextmanager for clean startup/shutdown handling
- **Authentication**: OAuth 2.0 with Google APIs

### Data Processing
- **Queue System**: RabbitMQ for inter-service communication
- **Classification**:
  - Rule-based: Regex engine, custom heuristics
  - ML-based: scikit-learn for advanced classification (future)

### AI Integration
- **Primary Option**: OpenAI API (GPT models)
- **Alternative**: Google Gemini API
- **Abstraction Layer**: Custom adapter for provider switching

### Persistence
- **Cache**: Redis for token/session management
  - Implemented for Auth Service with structured token storage
  - JSON serialization/deserialization of token objects
  - Used for Email Service rate limiting and sync state tracking
- **Database**: 
  - Service-specific data stores as needed
  - PostgreSQL for user preferences and audit logging

### Deployment
- **Containerization**: Docker for each microservice
- **Orchestration**: Docker Compose (dev), Kubernetes (prod)
- **CI/CD**: GitHub Actions with automated testing

### Testing Framework
- **Unit Testing**: pytest with pytest-asyncio
- **Mock Framework**: pytest-mock
- **Test Coverage**: pytest-cov with minimum 80% coverage requirement
- **Integration Testing**: TestContainers for service dependencies

### Monitoring & Logging
- **Metrics**: Prometheus with service-specific exporters
- **Visualization**: Grafana
- **Logging**: Centralized logging with correlation IDs
- **Alerting**: Slack integration

## Development Environment
- **Version Control**: Git
- **IDE**: VS Code recommended
- **Package Management**: Poetry for dependency management
- **Documentation**: OpenAPI/Swagger for each service API
- **Local Development**: Docker Compose for services orchestration

## Microservices Structure
```
gmail-automation/
├── services/
│   ├── auth_service/
│   ├── email_service/
│   ├── classification_service/
│   ├── response_service/
│   ├── draft_service/
│   └── api_gateway/
├── shared/
│   ├── models/
│   └── utils/
└── docker-compose.yml
```

## External API Dependencies

### Gmail API
- **Authentication**: OAuth 2.0
- **Scope Requirements**:
  - `https://www.googleapis.com/auth/gmail.readonly` (for reading emails)
  - `https://www.googleapis.com/auth/gmail.modify` (for creating drafts, labels)
  - `https://www.googleapis.com/auth/gmail.labels` (for managing labels)
- **Rate Limits**: 
  - 1 billion quota units per day
  - 250 quota units per user per second
- **Email Ingestion Parameters**:
  - Batch Size: 100 emails per request (configurable 10-500)
  - Initial Sync Period: 30 days default (configurable 7-90 days)
  - Polling Frequency: 5 minutes default (adaptive based on volume)
  - Rate Control: Token bucket algorithm (200 quota units/second)

### OpenAI API / Google Gemini
- **Authentication**: API key
- **Models**: 
  - OpenAI: GPT-3.5-turbo or GPT-4
  - Gemini: Gemini Pro
- **Rate Limits**: Depends on subscription tier
- **Cost Considerations**: Per-token pricing

## Email Service Technical Implementation
- **Gmail API Client**: Custom Python client with retries and error handling
- **Sync Mechanism**:
  - Initial sync with configurable time window
  - Incremental updates based on last sync timestamp
  - Resumable operations for interrupted syncs
- **Rate Limiting Implementation**:
  - Redis-backed token bucket algorithm
  - Quota usage tracking with alerts
  - Circuit breaker pattern for API failures
- **Adaptive Polling**:
  - Volume-based frequency adjustment
  - Email throughput monitoring
  - User-configurable preferences

## Test-Driven Development Approach
- **Test First**: Write tests before implementing functionality
- **Red-Green-Refactor Cycle**:
  1. Write a failing test (Red)
  2. Implement code to make the test pass (Green)
  3. Refactor code while maintaining passing tests
- **Test Types**:
  - Unit tests for individual components
  - Service tests for API contracts
  - Integration tests for service interactions
  - End-to-end tests for critical user flows
- **Mocking Strategy**:
  - External APIs mocked for unit/service tests
  - Service boundaries mocked for cross-service tests
  - Test doubles used for dependencies

## Technical Constraints
- **Security**: Must encrypt tokens and sensitive data
- **Performance**: Email processing should complete within seconds
- **Scalability**: Each microservice should scale independently
- **Resilience**: Services should handle failures gracefully
- **Compliance**: Privacy considerations for email content
- **Rate Limits**: Must respect Gmail API quotas

## Development Workflow
1. Feature branch development with TDD
2. Local testing with Docker Compose
3. CI/CD pipeline runs all tests
4. Deployment to staging environment
5. Production deployment

## API Documentation
- Each microservice will expose OpenAPI documentation
- Service contracts will be clearly defined and versioned

## Error Handling Approach

### Custom Exception Hierarchy
1. **Base Custom Exception**
   - Root exception for all custom exceptions
   - Ensures consistent handling across the application

2. **Resource Not Found Error**
   - Raised when a requested resource doesn't exist
   - Maps to HTTP 404 in API responses

3. **Validation Error**
   - Raised for input validation failures
   - Maps to HTTP 400 in API responses

4. **External Service Error**
   - Raised when external services (Google, OpenAI) fail
   - Maps to HTTP 502 in API responses
   - Includes details about the external service and failure

5. **Authentication Error**
   - Raised for authentication failures
   - Maps to HTTP 401 in API responses

6. **Configuration Error**
   - Raised when configuration is missing or invalid
   - Maps to HTTP 500 in API responses

### Exception Handling Pattern
- Routes raise specific exception types rather than returning status codes
- Global exception handlers convert exceptions to standardized HTTP responses
- Tests verify that routes raise the correct exceptions
- Mock objects configured to raise specific exceptions in tests
- Error responses include:
  - Error type (for programmatic handling)
  - Human-readable message
  - Additional context (when available)
  - Correlation ID (for tracing)