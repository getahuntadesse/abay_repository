# config/__init__.py
"""Initialize config module and apply Python 3.14 patches if present."""

try:
    from .admin_patch import apply_admin_patch
    apply_admin_patch()
except ImportError:
    pass
