import sys
from unittest.mock import MagicMock
from datetime import datetime
from typing import List, Dict, Any, Optional

# Create mock for the shared.models.email module to handle import issue
class MockEmailMessage:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def model_dump(self):
        return {k: v for k, v in self.__dict__.items()}

# Add more fields and methods needed by Gmail Client
class MockGmailMessagePart:
    def __init__(self, body=None, filename=None, headers=None, parts=None, mime_type=None):
        self.body = body or {"data": "", "size": 0}
        self.filename = filename
        self.headers = headers or []
        self.parts = parts or []
        self.mime_type = mime_type or "text/plain"

class MockGmailMessage:
    def __init__(self, id=None, thread_id=None, label_ids=None, snippet=None, 
                 payload=None, internal_date=None, history_id=None):
        self.id = id or "msg_123"
        self.thread_id = thread_id or "thread_123"
        self.label_ids = label_ids or ["INBOX"]
        self.snippet = snippet or "Test email snippet"
        self.payload = payload or MockGmailMessagePart(
            headers=[
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Fri, 24 Apr 2025 10:00:00 -0700"}
            ],
            mime_type="multipart/alternative",
            parts=[
                MockGmailMessagePart(mime_type="text/plain", body={"data": "VGVzdCBlbWFpbCBib2R5", "size": 15}),
                MockGmailMessagePart(mime_type="text/html", body={"data": "PHA+VGVzdCBlbWFpbCBib2R5PC9wPg==", "size": 25})
            ]
        )
        self.internal_date = internal_date or "1619280000000"  # April 24, 2025
        self.history_id = history_id or "12345"

# Create HttpError mock for googleapiclient.errors
class MockHttpError(Exception):
    def __init__(self, resp=None, content=None, uri=None):
        self.resp = resp or {'status': '404'}
        self.content = content or b'{"error": {"message": "Not Found"}}'
        self.uri = uri or 'https://gmail.googleapis.com/api'
        super().__init__(f"HttpError: {self.resp}, {self.content}, {self.uri}")

# Create a mock module for shared.models.email
mock_email_module = MagicMock()
mock_email_module.EmailMessage = MockEmailMessage

# Create a mock module for shared.models
mock_models_module = MagicMock()
mock_models_module.email = mock_email_module

# Create a mock module for shared
mock_shared_module = MagicMock()
mock_shared_module.models = mock_models_module

# Add the mock module to sys.modules
sys.modules['shared'] = mock_shared_module
sys.modules['shared.models'] = mock_models_module
sys.modules['shared.models.email'] = mock_email_module

# Add Google API Client mocks
mock_googleapiclient = MagicMock()
mock_googleapiclient.discovery = MagicMock()
mock_googleapiclient.discovery.build = MagicMock()

# Add errors module with HttpError
mock_errors_module = MagicMock()
mock_errors_module.HttpError = MockHttpError

# Add errors to googleapiclient
mock_googleapiclient.errors = mock_errors_module

sys.modules['googleapiclient'] = mock_googleapiclient
sys.modules['googleapiclient.discovery'] = mock_googleapiclient.discovery
sys.modules['googleapiclient.errors'] = mock_errors_module

# Add Google Auth mocks
mock_google_auth = MagicMock()
mock_google_auth.transport = MagicMock()
mock_google_auth.transport.requests = MagicMock()
mock_google_auth.transport.requests.Request = MagicMock()

mock_google_auth_oauthlib = MagicMock()
mock_google_auth_oauthlib.flow = MagicMock()
mock_google_auth_oauthlib.flow.Flow = MagicMock()

sys.modules['google.auth'] = mock_google_auth
sys.modules['google.auth.transport'] = mock_google_auth.transport
sys.modules['google.auth.transport.requests'] = mock_google_auth.transport.requests
sys.modules['google_auth_oauthlib'] = mock_google_auth_oauthlib
sys.modules['google_auth_oauthlib.flow'] = mock_google_auth_oauthlib.flow