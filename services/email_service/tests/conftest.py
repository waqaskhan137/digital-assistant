"""Test configuration for Email Service."""
import sys
import os
from pathlib import Path
import pytest
import asyncio

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Add the email_service directory to the Python path
EMAIL_SERVICE_DIR = Path(__file__).parent.parent
sys.path.append(str(EMAIL_SERVICE_DIR))

# Make this tests module importable as 'services.email_service.tests'
# instead of just 'tests' to avoid conflicts
SERVICE_TESTS_DIR = Path(__file__).parent
module_name = 'services.email_service.tests'
if module_name not in sys.modules:
    sys.modules[module_name] = type(sys)(module_name)
    sys.modules[module_name].__path__ = [str(SERVICE_TESTS_DIR)]

# The pytest_plugins line has been moved to the top-level conftest.py
# This file is now specific to email_service tests

@pytest.fixture(scope="session")
def event_loop_policy():
    """Create a custom event loop policy for all tests."""
    return asyncio.DefaultEventLoopPolicy()