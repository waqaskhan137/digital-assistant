# System Patterns

## Architecture Overview
The Gmail Automation project follows a true microservices architecture, with each service having a single responsibility. Services communicate via REST APIs and message queues, ensuring loose coupling and independent scalability.

```
+----------------+       +------------------+       
|   API Gateway  | <-->  | Auth Service     |       
|                |       | (OAuth 2.0 Flow) |       
+----------------+       +------------------+       
        |                        |                  
        v                        v                  
+----------------+       +------------------+       +----------------------+       
| Classification | <-->  | Email Ingestion  | <--> | Draft Management     |
| Service        |       | Service          |       | Service             |
+----------------+       +------------------+       +----------------------+
        |                                                    ^
        v                                                    |
+------------------+                                         |
| Response Gen.    | ----------------------------------------+
| Service          |
+------------------+
```

## Email Service Component Architecture
After completing Phase 1 of the code audit refactoring, the Email Service has been restructured to follow a more modular, component-based architecture with clear separation of responsibilities:

```
+---------------+    +----------------+
| AuthClient    |--->| TokenManager  |
+---------------+    +----------------+
       |
       v
+---------------+    +-----------------+     +--------------------+
| GmailClient   |--->| GmailApiClient |---->| Rate Limiter       |
| (Facade)      |    +-----------------+     +--------------------+
+---------------+
       |
       |-----------------------------+
       |                            |
       v                            v
+---------------+    +---------------+     +--------------------+
| EmailNormalizer|-->| ContentExtractor|-->| HTML to Text Utils |
+---------------+    +---------------+     +--------------------+
       |
       v
+---------------+
| SyncStateManager
+---------------+
```

## Core Design Patterns

### 1. Microservices Architecture
- Each service has a single responsibility
- Independent deployment and scaling
- Service-specific data storage when needed
- Communication via well-defined APIs

### 2. Event-Driven Flow
- Email arrival triggers processing pipeline
- RabbitMQ for asynchronous communication between services
- Event-based coordination of workflow

### 3. Authentication & Security
- Dedicated Auth Service for OAuth 2.0 implementation
- Token management centralized in Auth Service
- Secure token storage and refresh logic
- TokenManager for separating token caching from API communication

### 4. Test-Driven Development (TDD)
- Tests written before implementation code
- Red-Green-Refactor cycle for all components
- Mocking of external dependencies for unit testing
- Integration tests for service boundaries

### 5. Component-Based Architecture
- Breaking down large classes into focused components with single responsibilities
- Clear interfaces between components
- Facade pattern to coordinate component interactions
- Utility modules for reusable functionality

### 6. Strategy Pattern for Classification
- Multiple classification strategies (rule-based, ML-based)
- Pluggable classification algorithms
- User-configurable rules

### 7. Adapter Pattern for AI Integrations
- Clean interface to abstract different AI providers
- Easily swap between OpenAI, Google Gemini, or others
- Consistent prompt and response handling

### 8. API Gateway Pattern
- Single entry point for client applications
- Request routing to appropriate microservices
- Authentication and authorization enforcement

## Code Quality Principles

### Single Responsibility & Modularity
- Each microservice has clear, focused responsibilities
- Components within services follow Single Responsibility Principle:
  - GmailClient split into multiple focused classes:
    - GmailClient: Facade that coordinates other components
    - GmailApiClient: Handles raw API interactions
    - EmailNormalizer: Converts external to internal format
    - EmailContentExtractor: Processes email content and attachments
  - SyncStateManager separated from SyncAnalytics
  - TokenManager extracted from AuthClient
- Utility functions organized into dedicated modules:
  - text_utils.py: Text processing utilities like HTML to text conversion
  - retry.py: Retry decorators for API resilience
  - token_manager.py: Token handling utilities

### DRY & KISS Principles
- Common patterns extracted into reusable components:
  - Retry decorator handles API rate limiting consistently
  - Redis operations standardized with helper methods
  - Common email querying logic extracted to helper methods
  - Token management centralized in TokenManager
- Complex logic simplified:
  - Email querying streamlined with better query construction
  - Conditional processing flows standardized
  - Token caching logic simplified with declarative approach

### SOLID Principles (In Progress)
- Interface Segregation:
  - Breaking down large interfaces into smaller, focused ones
  - Creating purpose-specific client interfaces
- Dependency Inversion:
  - Components depend on abstractions rather than concrete implementations
  - Dependency injection for easier testing and flexibility
- Open/Closed Principle:
  - Strategy pattern for extensible algorithms
  - Abstract base classes for extensible components

### Error Handling & Validation
- Standardized error handling across components
- Consistent validation approach for inputs
- Clear error messaging for debugging
- Proper propagation of errors to appropriate layers

### Testing Strategy
- Tests written before implementation code
- Red-Green-Refactor cycle for all components
- Mocking of external dependencies for unit testing
- Integration tests for service boundaries

## Design Patterns

### Facade Pattern
- GmailClient acts as a facade to coordinate:
  - GmailApiClient for API communication
  - EmailNormalizer for format conversion
  - EmailContentExtractor for content processing
- Provides a simplified interface to complex subsystems

### Decorator Pattern
- Used for cross-cutting concerns:
  - async_retry_on_rate_limit decorator handles retries consistently
  - Avoids code duplication across API methods
  - Centralizes retry logic and exponential backoff

### Strategy Pattern (In Progress)
- Being implemented for adaptive polling interval calculation
- Allows plugging in different algorithms for interval calculation
- Makes the system extensible without modifying existing code

### Repository Pattern
- Used for token storage and retrieval
- Abstracts the data storage mechanism
- Provides a clean interface for CRUD operations

### Factory Method Pattern
- Used for creating specialized handlers for different email types
- Simplifies client code by centralizing creation logic

### Template Method Pattern
- Base classes define algorithm structure
- Subclasses implement specific steps
- Ensures consistent processing flow

### Service Locator Pattern (For dependency injection)
- Being implemented to support dependency inversion
- Centralizes service instance creation and management
- Simplifies testing with mock implementations

## Service Responsibilities

1. **Auth Service**
   - OAuth 2.0 authentication flow
   - Token acquisition, storage, and refresh
   - Scope management for Gmail API

2. **Email Ingestion Service**
   - Gmail API integration
   - Email polling or webhook handling
   - Initial email normalization

3. **Classification Service**
   - Email categorization
   - Label management
   - "Needs reply" determination

4. **Response Generation Service**
   - AI provider integration
   - Prompt construction
   - Response validation

5. **Draft Management Service**
   - Draft creation in Gmail
   - Draft metadata management
   - Template handling

6. **API Gateway**
   - Request routing
   - Authentication verification
   - Rate limiting

## Email Service Component Responsibilities

1. **GmailClient (Facade)**
   - Coordinates between specialized components
   - Provides a simplified API to the rest of the Email Service
   - Manages the flow of data between components

2. **GmailApiClient**
   - Handles raw API communication with Gmail
   - Manages API authentication
   - Implements pagination and batch processing
   - Works with the Rate Limiter for quota management

3. **EmailNormalizer**
   - Converts Gmail API message format to internal EmailMessage model
   - Extracts message metadata (subject, sender, etc.)
   - Coordinates with ContentExtractor for message content

4. **EmailContentExtractor**
   - Processes MIME message payloads
   - Extracts HTML and text content
   - Identifies and extracts attachment metadata
   - Works with HTML-to-text utilities for content processing

5. **TokenManager**
   - Handles token caching and expiry tracking
   - Manages token refresh logic
   - Provides a clean interface for token operations

6. **SyncStateManager**
   - Tracks synchronization state in Redis
   - Manages resumable operations
   - Calculates optimal polling intervals based on email volume

7. **RateLimiter**
   - Implements token bucket algorithm for API rate limiting
   - Prevents quota exhaustion
   - Manages concurrent API request rates

## Data Flow
1. **Authentication**: User authenticates via Auth Service
2. **Email Ingestion**: Email Service connects to Gmail API and receives new emails
3. **Classification**: Emails sent to Classification Service for analysis
4. **Action Determination**: Classification Service decides if email needs a reply
5. **Response Generation**: For emails needing replies, sent to Response Service
6. **Persistence**: Draft Service saves responses as drafts; Classification Service applies labels

## Error Handling Strategy
- Retry logic for transient failures
- Dead-letter queues for failed processing
- Circuit breaker pattern for external service failures
- Comprehensive logging with correlation IDs

## Scalability Considerations
- Horizontal scaling for each microservice independently
- Rate limiting to respect Gmail API quotas
- Caching to reduce API calls
- Stateless services where possible

## Error Handling
- A custom exception hierarchy is defined in `shared/exceptions.py`.
- All project-specific errors should inherit from `GmailAutomationError`.
- Specific exceptions exist for common scenarios like `AuthenticationError`, `ConfigurationError`, `ValidationError`, `ExternalServiceError`, `ResourceNotFoundError`, `RateLimitError`, `EmailProcessingError`, and `SyncStateError`.
- Error handling within services should catch specific custom exceptions where possible and translate external library exceptions into appropriate custom exceptions.
- FastAPI exception handlers should be used at the API boundary to convert custom exceptions into standardized HTTP error responses.

# System Architecture & Patterns

## High-Level Architecture

Our Gmail automation project follows a microservices architecture, consisting of six discrete services:

1. **Auth Service**: Handles OAuth 2.0 authentication with Google and token management
2. **Email Service**: Manages email ingestion, communication with Gmail API, and email synchronization
3. **Classification Service**: Analyzes emails for classification and prioritization
4. **Response Service**: Generates appropriate responses using AI
5. **Draft Service**: Manages draft creation and editing
6. **API Gateway**: Provides a unified API for frontend interactions

## System Components

```mermaid
graph TD
    Client[Client Application] --> Gateway[API Gateway]
    
    Gateway --> Auth[Auth Service]
    Gateway --> Email[Email Service]
    Gateway --> Class[Classification Service]
    Gateway --> Response[Response Service]
    Gateway --> Draft[Draft Service]
    
    Auth --> Google[Google OAuth]
    Email --> GmailAPI[Gmail API]
    Email --> Auth
    Email --> MQ[RabbitMQ]
    
    MQ --> Class
    Class --> MQ
    
    MQ --> Response
    Response --> OpenAI[OpenAI API]
    Response --> MQ
    
    MQ --> Draft
    Draft --> GmailAPI
```

## Design Patterns & Technical Decisions

### 1. Authentication & Authorization

**OAuth 2.0 Flow**:
- Standard OAuth 2.0 authorization code flow with Google
- Enhanced security with state parameter
- Token storage in Redis with TTL-based expiration
- Refresh token management
- Proper exception handling with clear error responses

The Auth Service implements the following patterns:
- **Repository Pattern** for token storage
- **Factory Pattern** for creating OAuth clients
- **Dependency Injection** for better testability
- **Custom Exception Hierarchy** with specific exception types
- **Exception Handler** mapping exceptions to appropriate HTTP status codes

Key security measures:
- State parameter validation to prevent CSRF attacks
- Redis-based token storage with TTL
- Secure token exchange with Google
- Proper error handling for authentication failures

Implementing proper exception handling:
- Custom exception types in `shared/exceptions.py`
- Routes raising specific exceptions for error cases
- FastAPI exception handlers mapping exceptions to appropriate HTTP status codes
- Consistent error response format

### 2. Email Processing Pipeline

// ...existing code...

### 3. Classification System

// ...existing code...

### 4. Response Generation

// ...existing code...

### 5. Draft Management

// ...existing code...

## Cross-Cutting Concerns

### Exception Handling

We've implemented a standardized approach to error handling across services:

1. **Custom Exception Hierarchy**:
   - `BaseCustomException`: Root exception all custom exceptions inherit from
   - `ConfigurationError`: For configuration-related issues
   - `ResourceNotFoundError`: When a requested resource doesn't exist
   - `ValidationError`: For input validation failures
   - `ExternalServiceError`: For failures in external service communication
   - `AuthenticationError`: For authentication-related issues

2. **FastAPI Exception Handlers**:
   - Global exception handlers registered at application startup
   - Map specific exception types to appropriate HTTP status codes
   - Convert exceptions to consistent error response format
   - Preserve error context for better troubleshooting

3. **Exception Raising Pattern**:
   - Routes explicitly raise appropriate exception types
   - No direct status code returns in route handlers
   - Exception context includes detailed information for debugging
   - Consistent exception types across all services

4. **Exception Testing**:
   - Tests verify that routes raise the correct exceptions
   - Mock objects configured to raise specific exceptions
   - Test expectations aligned with defined exception mappings
   - Comprehensive testing of error scenarios

### Dependency Injection

// ...existing code...

### Retry & Resilience Patterns

// ...existing code...

## Testing Strategy

// ...existing code...

## Communication Patterns

// ...existing code...

## Performance Considerations

// ...existing code...

## Security Patterns

// ...existing code...

## Deployment Model

// ...existing code...

## Monitoring & Observability

// ...existing code...

## Data Flow Diagrams

// ...existing code...

## Interface Contracts

// ...existing code...

## Evolution & Extensibility

// ...existing code...