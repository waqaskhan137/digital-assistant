# Classification Service Implementation Plan

This document outlines the planned steps for implementing the `classification_service`.

**Phase 1: Basic Service Setup & RabbitMQ Integration**

1.  **Project Structure:**
    *   *(Existing)* `services/classification_service/src/`
    *   *(Existing)* `services/classification_service/tests/`
    *   Create standard FastAPI files within `src/`:
        *   `main.py`: FastAPI app setup, lifespan events.
        *   `config.py`: Configuration loading (RabbitMQ URL, etc.).
        *   `consumer.py`: RabbitMQ message consumption logic.
        *   `models.py`: Service-specific Pydantic models (e.g., `ClassificationResult`).
        *   `routes/`: (Optional for now, maybe for health checks later).
    *   Create `core/` directory within `src/` for classification logic.
    *   Create standard test structure within `tests/` (e.g., `unit/`, `integration/`, `conftest.py`).
    *   Create `services/classification_service/requirements.txt`.
    *   Create `services/classification_service/Dockerfile`.

2.  **Dependencies:**
    *   Add `fastapi`, `uvicorn`, `pydantic`, `aio_pika` to `requirements.txt`.
    *   Ensure shared modules (`shared/models/email.py`, `shared/exceptions.py`) are accessible.

3.  **Configuration:**
    *   Implement `config.py` to load RabbitMQ connection details and queue names from environment variables.

4.  **RabbitMQ Consumer (Initial):**
    *   *(Test)* Write a test for the consumer setup (mocking `aio_pika`).
    *   Implement `consumer.py` with a function to connect to RabbitMQ during application startup (using FastAPI lifespan).
    *   Implement a basic message handler function that:
        *   Accepts a message.
        *   Deserializes the message body into the `shared.models.email.EmailMessage` model.
        *   Logs the received email subject (for initial verification).
        *   Acknowledges the message.
    *   Handle potential deserialization errors.

5.  **FastAPI App:**
    *   Set up the basic FastAPI app in `main.py`.
    *   Use the lifespan manager to start/stop the RabbitMQ consumer connection.
    *   Integrate shared exception handlers (from Phase 5 refactoring).

6.  **Dockerfile & Docker Compose:**
    *   Create a basic `Dockerfile` for the service.
    *   Add the `classification_service` to `docker-compose.yml`, ensuring it depends on RabbitMQ.

**Phase 2: Rule-Based Classification Logic (MVP)**

1.  **Models:**
    *   Define `ClassificationResult` model in `src/models.py` (e.g., `category: str`, `needs_reply: bool`, `confidence: float`).

2.  **Classifier Interface (Strategy Pattern Prep):**
    *   *(Test)* Define tests for a classifier interface/base class.
    *   Define an abstract base class `BaseClassifier` in `src/core/classifier_abc.py` with an `classify(email: EmailMessage) -> ClassificationResult` method.

3.  **Rule-Based Classifier Implementation:**
    *   *(Test)* Write unit tests for simple classification rules (e.g., sender domain match, subject keyword match).
    *   Implement `RuleBasedClassifier(BaseClassifier)` in `src/core/rule_classifier.py`.
    *   Start with hardcoded rules (e.g., a list of dictionaries defining rule conditions and outcomes like category and `needs_reply`).
    *   The `classify` method should iterate through rules and return the first matching `ClassificationResult`.

4.  **Integration in Consumer:**
    *   *(Test)* Update consumer tests to check if the classifier is called.
    *   Instantiate `RuleBasedClassifier` in `consumer.py`.
    *   Modify the message handler to:
        *   Call the classifier with the deserialized `EmailMessage`.
        *   Log the `ClassificationResult`.
        *   (Future: Publish result to another queue).

**Phase 3: Testing & Refinement**

1.  **Integration Testing:**
    *   Write integration tests using `pytest` and potentially `TestContainers` (if not already done) to verify:
        *   Message consumption from a real (test) RabbitMQ instance.
        *   Correct deserialization and classification flow.
        *   Error handling scenarios.
2.  **Refactor & Clean Code:**
    *   Review code against Clean Code Principles (`.github/core.md`).
    *   Ensure proper error handling using the shared exceptions.
    *   Add logging throughout the service.
3.  **Documentation:**
    *   Add basic docstrings.
    *   Update `memory-bank/progress.md` to reflect the completed implementation and any new decisions or issues.
    *   Update `memory-bank/activeContext.md` with the focus shift and learnings.
