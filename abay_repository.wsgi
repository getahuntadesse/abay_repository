"""
WSGI file for abay_repository project.
This file is used by Apache mod_wsgi.
File: abay_repository.wsgi
"""

import os
import sys

# Add the project directory to Python path
project_path = r'C:\abay_repository'
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abay_repository.settings')

# Import the WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

# Optional: For debugging
def application(environ, start_response):
    """
    Wrapper function that can help with debugging.
    """
    # Ensure settings are loaded
    if not os.environ.get('DJANGO_SETTINGS_MODULE'):
        os.environ['DJANGO_SETTINGS_MODULE'] = 'abay_repository.settings'
    
    from django.core.wsgi import get_wsgi_application
    _application = get_wsgi_application()
    
    return _application(environ, start_response)