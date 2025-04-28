"""Test configuration for Auth Service."""
import sys
import os
from pathlib import Path

# Define the module namespace as services.auth_service.tests
# This ensures this conftest is imported as services.auth_service.tests.conftest
# instead of just tests.conftest, avoiding the import conflict

# Add the service directory to Python path
SERVICE_DIR = Path(__file__).parent.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

# Add the project root to the path for shared modules
PROJECT_ROOT = SERVICE_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))