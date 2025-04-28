import pytest
import base64
from services.email_service.src.content_extractor import EmailContentExtractor

class TestEmailContentExtractor:
    """Test cases for the EmailContentExtractor class."""
    
    @pytest.fixture
    def content_extractor(self):
        return EmailContentExtractor()
    
    def test_extract_body_html_only(self, content_extractor):
        """Test extracting body from a payload with only HTML content."""
        # Create a test payload with HTML content
        html_content = "<html><body><h1>Test Email</h1><p>This is a test.</p></body></html>"
        encoded_html = base64.urlsafe_b64encode(html_content.encode()).decode()
        
        payload = {
            "mimeType": "text/html",
            "body": {
                "data": encoded_html
            }
        }
        
        # Extract body
        html_body, text_body = content_extractor.extract_body(payload)
        
        # Verify results
        assert html_body == html_content
        assert "Test Email" in text_body
        assert "This is a test." in text_body
    
    def test_extract_body_text_only(self, content_extractor):
        """Test extracting body from a payload with only text content."""
        # Create a test payload with text content
        text_content = "This is a plain text email."
        encoded_text = base64.urlsafe_b64encode(text_content.encode()).decode()
        
        payload = {
            "mimeType": "text/plain",
            "body": {
                "data": encoded_text
            }
        }
        
        # Extract body
        html_body, text_body = content_extractor.extract_body(payload)
        
        # Verify results
        assert html_body == ""
        assert text_body == text_content
    
    def test_extract_body_with_parts(self, content_extractor):
        """Test extracting body from a payload with multiple parts."""
        # Create a test payload with both HTML and text parts
        html_content = "<html><body><h1>Test Email</h1><p>This is a test.</p></body></html>"
        text_content = "This is a plain text email."
        
        encoded_html = base64.urlsafe_b64encode(html_content.encode()).decode()
        encoded_text = base64.urlsafe_b64encode(text_content.encode()).decode()
        
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": encoded_text
                    }
                },
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": encoded_html
                    }
                }
            ]
        }
        
        # Extract body
        html_body, text_body = content_extractor.extract_body(payload)
        
        # Verify results
        assert html_body == html_content
        assert text_body == text_content
    
    def test_get_attachments(self, content_extractor):
        """Test getting attachment metadata from a payload."""
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": "test"
                    }
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "test.pdf",
                    "body": {
                        "attachmentId": "attachment123",
                        "size": 12345
                    }
                }
            ]
        }
        
        # Get attachments
        attachments = content_extractor.get_attachments(payload)
        
        # Verify results
        assert len(attachments) == 1
        assert attachments[0]['id'] == "attachment123"
        assert attachments[0]['filename'] == "test.pdf"
        assert attachments[0]['mime_type'] == "application/pdf"
        assert attachments[0]['size'] == 12345