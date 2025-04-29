import pytest
import sys
import os
from pathlib import Path

# Configure pytest-asyncio with proper event loop policy
# This is the recommended way instead of overriding the event_loop fixture
pytest_plugins = ['pytest_asyncio']

# Add service directories to Python path to fix import issues
def pytest_configure(config):
    """Configure pytest before test collection."""
    # Get the project root directory
    root_dir = Path(__file__).parent
    
    # Add services directories to Python path
    for service_dir in (root_dir / "services").glob("*_service"):
        if service_dir.is_dir():
            service_path = str(service_dir)
            if service_path not in sys.path:
                sys.path.insert(0, service_path)
    
    # Add shared module to Python path
    shared_path = str(root_dir / "shared")
    if shared_path not in sys.path:
        sys.path.insert(0, shared_path)

# Update with pathlib.Path parameter to fix deprecation warning
def pytest_collect_file(parent, file_path):
    """Custom test collection hook (currently does nothing).

    Note: Updated to use pathlib.Path instead of py.path.local per pytest deprecation warning.
    """
    # Let pytest handle the standard collection
    return None