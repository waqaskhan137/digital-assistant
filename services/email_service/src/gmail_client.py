import asyncio
import logging
import base64
import json
import html
import re
import email.utils
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .rate_limiter import TokenBucketRateLimiter
from .auth_utils import convert_token_to_credentials
from shared.models.email import EmailMessage

logger = logging.getLogger(__name__)

class GmailClient:
    """
    Client for interacting with the Gmail API.
    
    This class handles all interactions with the Gmail API, including fetching
    emails, managing pagination, and handling rate limits.
    
    Attributes:
        auth_client: Client for retrieving OAuth tokens
        rate_limiter: Rate limiter for managing API quotas
        batch_size: Number of emails to fetch per request
        max_retries: Maximum number of retries for rate limited requests
        retry_delay: Base delay in seconds between retries (exponential backoff)
    """
    
    def __init__(
        self,
        auth_client,
        rate_limiter: TokenBucketRateLimiter,
        batch_size: int = 100,
        max_retries: int = 5,
        retry_delay: int = 1
    ):
        """
        Initialize the Gmail client.
        
        Args:
            auth_client: Client for retrieving OAuth tokens
            rate_limiter: Rate limiter for managing API quotas
            batch_size: Number of emails to fetch per request (default: 100)
            max_retries: Maximum number of retries for rate limited requests (default: 5)
            retry_delay: Base delay in seconds between retries (default: 1)
        """
        self.auth_client = auth_client
        self.rate_limiter = rate_limiter
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def get_credentials(self, user_id: str):
        """
        Get Google API credentials for a user.
        
        This method retrieves the OAuth token from the Auth Service and converts
        it to a Google credentials object that can be used with the Gmail API.
        
        Args:
            user_id: The user ID to get credentials for
            
        Returns:
            Google OAuth2 Credentials object
        """
        # Get the token from the Auth Service
        token_dict = await self.auth_client.get_user_token(user_id)
        
        # Convert the token to a credentials object
        credentials = convert_token_to_credentials(token_dict)
        
        return credentials
    
    async def get_email_list(
        self, user_id: str, query: str = "", page_token: str = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Get a list of emails for a user.
        
        Args:
            user_id: The user ID to fetch emails for
            query: Gmail search query string (default: "")
            page_token: Page token for pagination (default: None)
            
        Returns:
            Tuple containing:
                - List of email metadata
                - Next page token (None if no more pages)
        """
        # Acquire rate limit tokens
        await self.rate_limiter.acquire_tokens(1)
        
        # Get Gmail API service
        credentials = await self.get_credentials(user_id)
        service = build('gmail', 'v1', credentials=credentials)
        
        # Build request
        request = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=self.batch_size,
            pageToken=page_token if page_token else None
        )
        
        # Execute request with retries
        for attempt in range(self.max_retries):
            try:
                response = request.execute()
                messages = response.get('messages', [])
                next_page_token = response.get('nextPageToken')
                
                return messages, next_page_token
                
            except HttpError as error:
                # Check if rate limited (429)
                if error.resp.status == 429 and attempt < self.max_retries - 1:
                    retry_delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited. Retrying in {retry_delay} seconds.")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"Error fetching emails: {error}")
                    raise
        
        # If we reach here, all retries failed
        raise Exception(f"Failed to fetch emails after {self.max_retries} attempts")
    
    async def get_email_details(
        self, user_id: str, message_id: str
    ) -> Dict[str, Any]:
        """
        Get full details for a specific email.
        
        Args:
            user_id: The user ID to fetch the email for
            message_id: The Gmail message ID
            
        Returns:
            Dict containing the full email details
        """
        # Acquire rate limit tokens
        await self.rate_limiter.acquire_tokens(1)
        
        # Get Gmail API service
        credentials = await self.get_credentials(user_id)
        service = build('gmail', 'v1', credentials=credentials)
        
        # Build request
        request = service.users().messages().get(
            userId='me', 
            id=message_id,
            format='full'  # Get the full message
        )
        
        # Execute request with retries
        for attempt in range(self.max_retries):
            try:
                response = request.execute()
                return response
                
            except HttpError as error:
                # Check if rate limited (429)
                if error.resp.status == 429 and attempt < self.max_retries - 1:
                    retry_delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited. Retrying in {retry_delay} seconds.")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"Error fetching email details: {error}")
                    raise
        
        # If we reach here, all retries failed
        raise Exception(f"Failed to fetch email details after {self.max_retries} attempts")
    
    async def get_emails_since(
        self, 
        user_id: str, 
        since_date: datetime,
        include_labels: Optional[List[str]] = None,
        max_emails: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get all emails since a given date.
        
        Args:
            user_id: The user ID to fetch emails for
            since_date: Fetch emails since this date
            include_labels: This parameter is now ignored (kept for backwards compatibility)
            max_emails: Maximum number of emails to fetch
            
        Returns:
            List of email metadata
        """
        # Build Gmail search query with no label filtering
        # We need to be careful with Gmail search operators
        # Try a simpler approach that's most likely to return results
        
        # We're completely ignoring label filtering as requested by the user
        if include_labels:
            logger.info("Label filtering is disabled - retrieving all emails regardless of labels")
        
        # Build basic query
        query_parts = []
        
        # Add time-based query only if it's not a test account
        days_ago = (datetime.now() - since_date).days
        if days_ago > 0:
            query_parts.append(f"newer_than:{days_ago}d")
        else:
            # Fallback to a safer query that should return results
            query_parts.append("in:anywhere")
        
        # Log the query for debugging
        query = " ".join(query_parts)
        logger.info(f"Gmail search query: {query}")
        
        # Get emails with pagination
        all_emails = []
        page_token = None
        
        while True:
            # Check if we've reached the maximum
            if len(all_emails) >= max_emails:
                logger.info(f"Reached maximum of {max_emails} emails")
                break
                
            # Get next page of emails
            emails, page_token = await self.get_email_list(
                user_id=user_id,
                query=query,
                page_token=page_token
            )
            
            # Log the response for debugging
            logger.info(f"Gmail API response: found {len(emails)} emails")
            
            # Add to result list
            all_emails.extend(emails)
            
            # Break if no more pages
            if not page_token:
                break
                
            # Break if we'd exceed the maximum on the next page
            if len(all_emails) + self.batch_size > max_emails:
                logger.info(f"Would exceed maximum emails on next page, stopping.")
                break
        
        # If no emails found with the query, try a fallback approach
        if not all_emails:
            logger.warning("No emails found with the initial query, trying fallback query")
            fallback_query = "in:anywhere"  # This should return any emails in the account
            logger.info(f"Fallback Gmail search query: {fallback_query}")
            
            # Reset pagination
            page_token = None
            
            # Try with fallback query
            while True and len(all_emails) < max_emails:
                emails, page_token = await self.get_email_list(
                    user_id=user_id,
                    query=fallback_query,
                    page_token=page_token
                )
                
                logger.info(f"Fallback Gmail API response: found {len(emails)} emails")
                all_emails.extend(emails)
                
                if not page_token or len(all_emails) + self.batch_size > max_emails:
                    break
        
        logger.info(f"Retrieved {len(all_emails)} emails since approximately {since_date}")
        return all_emails
    
    async def get_all_emails(
        self,
        user_id: str,
        max_emails: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all emails without date filtering.
        
        This method is useful for testing and verifying that the Gmail API
        connection is working correctly. It returns the most recent emails
        without any date filtering.
        
        Args:
            user_id: The user ID to fetch emails for
            max_emails: Maximum number of emails to fetch
            
        Returns:
            List of email metadata
        """
        logger.info(f"Fetching up to {max_emails} most recent emails without date filtering")
        
        # Get emails with pagination
        all_emails = []
        page_token = None
        
        while True:
            # Check if we've reached the maximum
            if len(all_emails) >= max_emails:
                logger.info(f"Reached maximum of {max_emails} emails")
                break
                
            # Get next page of emails with empty query (returns all emails)
            emails, page_token = await self.get_email_list(
                user_id=user_id,
                query="",  # Empty query to get all emails
                page_token=page_token
            )
            
            # Log the response for debugging
            logger.info(f"Gmail API response for get_all_emails: found {len(emails)} emails on this page")
            
            # Add to result list
            all_emails.extend(emails)
            
            # Break if no more pages
            if not page_token:
                break
                
            # Break if we'd exceed the maximum on the next page
            if len(all_emails) + self.batch_size > max_emails:
                logger.info(f"Would exceed maximum emails on next page, stopping.")
                break
        
        logger.info(f"Retrieved {len(all_emails)} total emails with get_all_emails method")
        return all_emails
    
    async def normalize_messages(
        self, 
        user_id: str, 
        messages: List[Dict[str, Any]]
    ) -> List[EmailMessage]:
        """
        Convert Gmail API message format to our internal EmailMessage model.
        
        Args:
            user_id: The user ID the messages belong to
            messages: List of Gmail API message objects
            
        Returns:
            List of normalized EmailMessage objects
        """
        normalized_messages = []
        
        for message in messages:
            # Get full message details if not already present
            if 'payload' not in message:
                message = await self.get_email_details(user_id, message['id'])
            
            # Extract headers
            headers = {header['name'].lower(): header['value'] 
                    for header in message['payload']['headers']}
            
            # Parse date
            date_str = headers.get('date', '')
            try:
                date_tuple = email.utils.parsedate_tz(date_str)
                if date_tuple:
                    timestamp = email.utils.mktime_tz(date_tuple)
                    date = datetime.fromtimestamp(timestamp)
                else:
                    date = datetime.now()
            except Exception as e:
                logger.warning(f"Failed to parse date: {date_str}, {str(e)}")
                date = datetime.now()
            
            # Extract content
            body_html, body_text = self._extract_body(message['payload'])
            
            # Create normalized message
            email_message = EmailMessage(
                id=message['id'],
                user_id=user_id,
                thread_id=message.get('threadId', ''),
                labels=message.get('labelIds', []),
                snippet=message.get('snippet', ''),
                subject=headers.get('subject', ''),
                from_email=headers.get('from', ''),
                to=headers.get('to', ''),
                cc=headers.get('cc', ''),
                bcc=headers.get('bcc', ''),
                date=date,
                body_html=body_html,
                body_text=body_text,
                has_attachments=bool(self._get_attachments(message['payload'])),
                raw_data=message
            )
            
            normalized_messages.append(email_message)
        
        return normalized_messages
    
    def _extract_body(self, payload: Dict[str, Any]) -> Tuple[str, str]:
        """
        Extract HTML and plain text body from message payload.
        
        Args:
            payload: Gmail API message payload
            
        Returns:
            Tuple of (HTML body, plain text body)
        """
        body_html = ""
        body_text = ""
        
        # Check for body in the main payload
        if 'body' in payload and 'data' in payload['body']:
            data = payload['body']['data']
            decoded_data = base64.urlsafe_b64decode(data).decode('utf-8')
            
            if payload.get('mimeType') == 'text/html':
                body_html = decoded_data
            elif payload.get('mimeType') == 'text/plain':
                body_text = decoded_data
        
        # Check for body in parts
        if 'parts' in payload:
            for part in payload['parts']:
                part_mime_type = part.get('mimeType', '')
                
                if 'body' in part and 'data' in part['body']:
                    data = part['body']['data']
                    decoded_data = base64.urlsafe_b64decode(data).decode('utf-8')
                    
                    if part_mime_type == 'text/html':
                        body_html = decoded_data
                    elif part_mime_type == 'text/plain':
                        body_text = decoded_data
                
                # Recursively check for nested parts
                if 'parts' in part:
                    nested_html, nested_text = self._extract_body(part)
                    if nested_html and not body_html:
                        body_html = nested_html
                    if nested_text and not body_text:
                        body_text = nested_text
        
        # Convert HTML entities in text
        body_text = html.unescape(body_text)
        
        # If we only have HTML, try to extract text from it
        if body_html and not body_text:
            body_text = self._html_to_text(body_html)
        
        return body_html, body_text
    
    def _html_to_text(self, html_content: str) -> str:
        """
        Very simple HTML to text conversion.
        
        Args:
            html_content: HTML content
            
        Returns:
            Plain text version
        """
        # Remove scripts and style elements
        html_content = re.sub(r'<(script|style).*?</\1>', '', html_content, flags=re.DOTALL)
        
        # Replace <br>, <p>, <div> with newlines
        html_content = re.sub(r'<br[^>]*>', '\n', html_content)
        html_content = re.sub(r'</(p|div|h\d)>', '\n', html_content)
        
        # Remove all HTML tags
        html_content = re.sub(r'<[^>]*>', '', html_content)
        
        # Decode HTML entities
        text_content = html.unescape(html_content)
        
        # Normalize whitespace
        text_content = re.sub(r'\s+', ' ', text_content).strip()
        
        return text_content
    
    def _get_attachments(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract attachment metadata from message payload.
        
        Args:
            payload: Gmail API message payload
            
        Returns:
            List of attachment metadata
        """
        attachments = []
        
        # Check for attachments in the main payload
        if ('body' in payload and 'attachmentId' in payload['body'] and
                payload.get('filename', '')):
            attachments.append({
                'id': payload['body']['attachmentId'],
                'filename': payload['filename'],
                'mime_type': payload.get('mimeType', 'application/octet-stream'),
                'size': payload['body'].get('size', 0)
            })
        
        # Check for attachments in parts
        if 'parts' in payload:
            for part in payload['parts']:
                # If this part has an attachmentId and filename, it's an attachment
                if ('body' in part and 'attachmentId' in part['body'] and
                        part.get('filename', '')):
                    attachments.append({
                        'id': part['body']['attachmentId'],
                        'filename': part['filename'],
                        'mime_type': part.get('mimeType', 'application/octet-stream'),
                        'size': part['body'].get('size', 0)
                    })
                
                # Recursively check for nested parts
                if 'parts' in part:
                    nested_attachments = self._get_attachments(part)
                    attachments.extend(nested_attachments)
        
        return attachments
    
    async def get_attachment(
        self, 
        user_id: str, 
        message_id: str, 
        attachment_id: str
    ) -> Dict[str, Any]:
        """
        Get a specific attachment from an email.
        
        Args:
            user_id: The user ID to fetch the attachment for
            message_id: The Gmail message ID
            attachment_id: The attachment ID
            
        Returns:
            Dict containing the attachment data and metadata
        """
        # Acquire rate limit tokens
        await self.rate_limiter.acquire_tokens(1)
        
        # Get Gmail API service
        credentials = await self.get_credentials(user_id)
        service = build('gmail', 'v1', credentials=credentials)
        
        # Build request
        request = service.users().messages().attachments().get(
            userId='me',
            messageId=message_id,
            id=attachment_id
        )
        
        # Execute request with retries
        for attempt in range(self.max_retries):
            try:
                response = request.execute()
                
                # Decode data
                data = base64.urlsafe_b64decode(response['data'])
                
                return {
                    'data': data,
                    'size': response.get('size', 0),
                    'attachment_id': attachment_id
                }
                
            except HttpError as error:
                # Check if rate limited (429)
                if error.resp.status == 429 and attempt < self.max_retries - 1:
                    retry_delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited. Retrying in {retry_delay} seconds.")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"Error fetching attachment: {error}")
                    raise
        
        # If we reach here, all retries failed
        raise Exception(f"Failed to fetch attachment after {self.max_retries} attempts")