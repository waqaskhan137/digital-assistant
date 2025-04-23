import pytest
import asyncio

# Configure pytest-asyncio with proper event loop policy
# This is the recommended way instead of overriding the event_loop fixture
pytest_plugins = ['pytest_asyncio']

@pytest.fixture(scope="session")
def event_loop_policy():
    """Create a custom event loop policy for all tests."""
    return asyncio.DefaultEventLoopPolicy()