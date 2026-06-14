# config/__init__.py
"""Initialize config module and apply Python 3.14 patches"""

# Apply admin patch for Python 3.14 compatibility
from .admin_patch import apply_admin_patch
apply_admin_patch()

# Import celery app if using Celery
# from .celery import app as celery_app
# __all__ = ('celery_app',)