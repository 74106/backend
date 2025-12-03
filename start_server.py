#!/usr/bin/env python
"""
Startup script for Waitress WSGI server.
This ensures the Python path is set correctly before starting the server.
Works with both local development and Render deployment (src/ directory structure).
"""
import os
import sys

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add the script directory to Python path (for local development)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Handle Render deployment structure: /opt/render/project/src/
# If we're in a src/ subdirectory, add parent to path
if script_dir.endswith('/src') or script_dir.endswith('\\src'):
    parent_dir = os.path.dirname(script_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    # Also add src directory itself
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
elif 'src' in script_dir:
    # If src is somewhere in the path, ensure both src and parent are in path
    parts = script_dir.split(os.sep)
    if 'src' in parts:
        src_idx = parts.index('src')
        src_dir = os.sep.join(parts[:src_idx + 1])
        parent_dir = os.sep.join(parts[:src_idx])
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

# Import app after path is set
try:
    from app import app
except ImportError as e:
    # Try alternative import paths for Render deployment
    try:
        import sys
        # Try importing from src.app if we're in a src directory
        if 'src' in script_dir:
            sys.path.insert(0, script_dir)
        from app import app
    except ImportError:
        raise ImportError(f"Could not import app. Current sys.path: {sys.path}") from e

# Export app for waitress
__all__ = ['app']

