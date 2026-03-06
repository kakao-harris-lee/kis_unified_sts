"""Pytest configuration for test discovery and fixtures.

Adds project root to sys.path for module imports.
"""
import sys
from pathlib import Path

# Add project root to Python path immediately at module load time
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))


def pytest_configure(config):
    """Configure pytest before test collection.

    This hook runs before test collection, ensuring sys.path is set up correctly
    for importing project modules in fixtures and tests.
    """
    # Ensure project root is at the beginning of sys.path
    project_root_str = str(project_root)
    if project_root_str in sys.path:
        sys.path.remove(project_root_str)
    sys.path.insert(0, project_root_str)
