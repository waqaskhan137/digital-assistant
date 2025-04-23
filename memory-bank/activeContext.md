# Active Context

## Current Focus
- Implementing a microservices architecture with strict separation of concerns
- Applying Test-Driven Development methodology throughout the project
- ✅ **Completed and successfully tested the Auth Service implementation**
- ✅ **Successfully implemented Email Ingestion Service with Gmail API integration**
- **Working on enhancing Email Ingestion Service with testing and optimization**

## Recent Decisions
- Finalized Python with FastAPI as the technology stack for all microservices
- Chosen to follow a pure microservices approach with single responsibility per service
- Decided to implement TDD as the core development methodology
- Selected RabbitMQ for asynchronous communication between services
- Defined a clear microservice boundary for each component
- **Updated FastAPI implementations to use modern lifespan handlers instead of deprecated on_event patterns**
- **Enhanced Auth Service with improved OAuth flow including state parameter support for secure authentication**
- **Implemented comprehensive Email Ingestion Service with Gmail API integration**
- **Added support for HTML to text conversion and attachment handling**
- **Implemented resumable sync mechanism with Redis state tracking**
- **Set up RabbitMQ integration for message publishing to downstream services**

## Resolved Questions
- Language/framework: Python/FastAPI for all microservices
- Email ingestion: Implemented polling with adaptive intervals based on email volume
- AI provider: Will use OpenAI GPT initially with adapter pattern for flexibility
- Database approach: Service-specific data stores with shared PostgreSQL for user preferences
- Deployment: Docker Compose for development, Kubernetes for production
- **Auth Service implementation: Successfully completed with OAuth 2.0 flow and token management**
- **Docker containerization: Successfully implemented with proper context and shared module access**
- **Email Ingestion Service implementation: Completed with Gmail API integration and content processing**
- **Gmail API integration: Resolved userId handling by using "me" special value for authenticated user**
- **Inter-service authentication: Email Service successfully retrieves tokens from Auth Service**
- **Email content extraction: Implemented with support for different MIME types and HTML conversion**
- **State management: Implemented Redis-based sync state tracking for resumable operations**

## Current Priorities
1. ✅ Set up project structure following microservices architecture
2. ✅ Establish TDD workflow and testing frameworks
3. ✅ Implement Auth Service with OAuth 2.0 flow
4. ✅ Manually test Auth Service to verify OAuth flow and token storage
5. ✅ Create Email Ingestion Service with Gmail API integration
6. **Enhance Email Ingestion Service with testing and optimization:**
   - Add comprehensive unit and integration tests
   - Implement monitoring and metrics
   - Optimize performance for large email volumes
7. Develop Classification Service
8. Build Response Generation Service
9. Implement Draft Management Service
10. Create API Gateway for service coordination

## Implementation Insights
- Each microservice will be developed independently following TDD
- Service contracts must be clearly defined before implementation
- Mock external dependencies (Gmail API, OpenAI) for testing
- Use Docker Compose to orchestrate services locally during development
- Implement correlation IDs for request tracing across services
- **FastAPI's lifespan handlers provide a cleaner approach to application startup/shutdown events**
- **Redis provides effective token storage with appropriate serialization/deserialization**
- **Docker containerization requires careful management of build context and shared modules**
- **OAuth flow requires proper state parameter handling for security and user identification**
- **Email Ingestion requires careful rate limiting to stay within Gmail API quotas**
- **Adaptive polling frequency can optimize email processing based on user email volume**
- **When working with Gmail API, use "me" as userId rather than internal user IDs**
- **Inter-service authentication via token retrieval works well with the microservices architecture**
- **The GmailClient class effectively abstracts Gmail API complexity from the rest of the Email Service**
- **HTML to text conversion requires careful handling to preserve important formatting**
- **Batch processing with proper rate limiting is essential for Gmail API quota management**
- **Redis-based state tracking enables reliable resumable operations**

## Email Ingestion Service Parameters
- **Batch Size**: 100 emails per request (default), configurable between 10-500
- **Time Period**: 
  - Initial sync: 30 days by default (configurable 7-90 days)
  - Incremental updates: Since last successful sync timestamp
- **Polling Frequency**:
  - Default: Every 5 minutes
  - Adaptive based on volume: 2 min (high), 5 min (medium), 15 min (low)
  - Configurable range: 1-60 minutes
- **Rate Limiting**:
  - Limit to 200 quota units per second (under Gmail's 250 limit)
  - Implement Redis-based token bucket algorithm
  - Exponential backoff for 429 responses
  - Circuit breaker pattern for repeated failures
- **Error Handling**:
  - Retry up to 3 times with exponential backoff
  - Dead-letter queue for repeatedly failed processing
  - Store last successful email ID for resuming interrupted syncs
- **Gmail API Integration**:
  - Use "me" as userId for all Gmail API requests
  - Use internal user IDs only for token retrieval from Auth Service
  - Maintain clear separation between internal and external identifiers
- **Content Processing**:
  - Support for multiple MIME types
  - HTML to text conversion with formatting preservation
  - Attachment handling and metadata extraction
  - Email normalization for consistent processing

## TDD Implementation Approach
- Start with test suite setup for each microservice
- Define clear test cases before writing implementation code
- Use pytest fixtures to mock external dependencies
- Aim for high test coverage (minimum 80%)
- Implement continuous integration to run tests automatically

## User Preferences
- System should prioritize transparency in how emails are processed
- Users should maintain full control over sent communications
- Interface should be intuitive and require minimal configuration
- Clear visibility into the classification and response generation process

## Technical Considerations
- Security and privacy are paramount given the sensitive nature of email data
- Performance optimization needed for real-time email processing
- Service boundaries must be well-defined to maintain clear separation of concerns
- Error handling must be robust with proper fallback mechanisms
- Monitoring and observability across services essential for production deployment
- OAuth flow must include state parameter for security and proper user identification
- Email ingestion must implement adaptive rate control and quota management
- Proper authentication handling between microservices is essential for security
- Content processing must handle various email formats and encodings
- State management must be reliable for resumable operations