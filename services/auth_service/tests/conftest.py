"""Test configuration for Auth Service."""
import sys
import os
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Add the auth_service directory to the Python path
AUTH_SERVICE_DIR = Path(__file__).parent.parent
sys.path.append(str(AUTH_SERVICE_DIR))