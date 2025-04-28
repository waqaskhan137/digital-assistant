import re
import html
from typing import Optional

def html_to_text(html_content: Optional[str]) -> str:
    """
    Convert HTML content to plain text, preserving important formatting.
    
    This utility function takes HTML content and converts it to a readable
    plain text version, handling common elements like paragraphs, line breaks,
    and removing scripts and styles.
    
    Args:
        html_content: HTML content to convert
            
    Returns:
        Plain text version of the HTML content
    """
    if not html_content:
        return ""
        
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