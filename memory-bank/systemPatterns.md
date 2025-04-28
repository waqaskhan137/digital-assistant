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