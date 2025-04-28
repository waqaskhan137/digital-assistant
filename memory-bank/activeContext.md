# Active Context

## Current Focus
- Implementing a microservices architecture with strict separation of concerns
- Applying Test-Driven Development methodology throughout the project
- ✅ **Completed and successfully tested the Auth Service implementation**
- ✅ **Successfully implemented Email Ingestion Service with Gmail API integration**
- ✅ **Successfully implemented Phase 1 of code audit refactoring**
- ⚠️ **Partially completed testing for Email Ingestion Service (unit tests only)**
- **Completing comprehensive testing for the Email Ingestion Service**
- **Beginning implementation of Classification Service with TDD approach**

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
- **Created a three-tiered testing approach for Email Service (unit, integration, performance)**
- **Implemented test organization pattern with shared fixtures in conftest.py**
- **Established performance benchmarks for email processing operations**
- **Completed Phase 1 of the code audit refactoring, focusing on Single Responsibility and Meaningful Naming**
- **Refactored GmailClient into smaller, focused classes following SRP**
- **Created TokenManager to separate token management from authentication logic**
- **Improved naming consistency across the codebase**
- **Created focused utility modules for reusable functionality**

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
- **Email Service testing methodology: Comprehensive testing with multiple test types**
- **Test mocking approach: Using pytest-mock for dependency mocking**
- **Performance requirements: Email Service can process 5000+ emails efficiently**

## Current Priorities
1. ✅ Set up project structure following microservices architecture
2. ✅ Establish TDD workflow and testing frameworks
3. ✅ Implement Auth Service with OAuth 2.0 flow
4. ✅ Manually test Auth Service to verify OAuth flow and token storage
5. ✅ Create Email Ingestion Service with Gmail API integration
6. ✅ Implement Phase 1 of code audit refactoring (Single Responsibility & Meaningful Naming)
7. ⚠️ Enhance Email Ingestion Service with testing and optimization:
   - ✅ Add unit tests for key components (GmailClient, Rate Limiter)
   - ✅ Add unit tests for refactored components (EmailContentExtractor, GmailApiClient, etc.)
   - ❌ Implement integration tests for end-to-end flows
   - ❌ Add performance tests for large volumes
   - ❌ Optimize batch processing capabilities
   - ❌ Achieve >80% test coverage
8. 🔄 Implement Phase 2 of code audit refactoring (DRY & KISS Principles)
9. **Develop Classification Service:**
   - Create test suite for classification functionality
   - Implement rule-based classification engine
   - Add ML-based classification capabilities (future)
10. Build Response Generation Service
11. Implement Draft Management Service
12. Create API Gateway for service coordination

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
- **Separation of test types (unit, integration, performance) improves test organization and maintenance**
- **Shared test fixtures reduce code duplication and improve test clarity**
- **Parametrized testing in pytest allows for comprehensive test coverage with minimal code**
- **Performance testing with large datasets is essential for services that handle high volume data**
- **Mock objects must be configured to represent realistic scenarios for effective testing**
- **Integration tests provide confidence in end-to-end functionality that unit tests cannot**
- **Refactoring for Single Responsibility Principle greatly improved code organization**
- **Breaking down large classes into smaller, focused components enhances maintainability**
- **Creating dedicated utility modules increases code reuse across services**
- **TokenManager separation simplified Auth functionality and improved testing**
- **Consistent naming conventions reduce cognitive load and improve code readability**
- **Explicit method names that include return value units improve API clarity**
- **Gmail API client functionality is cleaner when split into focused responsibilities**
- **Test coverage for refactored components confirms functionality is preserved**
- **Following SRP makes unit testing simpler and more focused**

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
- **Testing Parameters**:
  - Unit test coverage: >80% for each component
  - Integration test coverage: All critical paths tested
  - Performance benchmarks: Process 5000+ emails efficiently
  - Concurrent user simulation: 5+ simultaneous users

## TDD Implementation Approach
- Start with test suite setup for each microservice
- Define clear test cases before writing implementation code
- Use pytest fixtures to mock external dependencies
- Aim for high test coverage (minimum 80%)
- Implement continuous integration to run tests automatically
- Organize tests by type (unit, integration, performance)
- Use shared fixtures for common test setup
- Implement performance benchmarks for critical operations

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
- Testing must cover all critical functionality and edge cases
- Performance testing must validate behavior under real-world conditions