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
    # Root directory of the project
    root_dir = Path(__file__).parent
    
    # Add service directories to Python path with explicit service prefixes
    for service_dir in (root_dir / 'services').glob('*_service'):
        service_name = service_dir.name
        
        # Add the service directory itself to the path
        sys.path.insert(0, str(service_dir))
        
        # Add the src directory with explicit module naming
        src_dir = service_dir / 'src'
        if src_dir.exists():
            sys.path.insert(0, str(src_dir))
        
        # Each test directory should have a unique Python package name
        tests_dir = service_dir / 'tests'
        if tests_dir.exists():
            sys.path.insert(0, str(tests_dir))
            
            # Create a mapping from test directory paths to service names
            # This will be used in pytest_collect_module to avoid naming conflicts
            if not hasattr(pytest, "_service_test_dirs"):
                pytest._service_test_dirs = {}
            pytest._service_test_dirs[str(tests_dir)] = service_name

# Update with pathlib.Path parameter to fix deprecation warning
def pytest_collect_file(parent, file_path):
    """Custom test collection to handle service-specific test directories.
    
    Note: Updated to use pathlib.Path instead of py.path.local per pytest deprecation warning.
    """
    # Let pytest handle the standard collection
    return None

# Add a function to avoid import conflicts between services' conftest.py files
def pytest_ignore_collect(collection_path, config):
    """
    Determine if a potential collection directory should be ignored.
    
    This function helps us control the test collection to avoid import conflicts
    between services.
    """
    # When running all tests together, only collect auth_service tests
    # The email_service tests will be run separately via the run_tests.sh script
    if config.getoption('collectall', True):
        collection_str = str(collection_path)
        if 'email_service/tests' in collection_str and 'auth_service/tests' not in collection_str:
            return True
    
    return False