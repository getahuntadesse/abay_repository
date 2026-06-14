# config/admin_patch.py
"""Patch for Django admin to work with Python 3.14"""
import copy
import sys

def apply_admin_patch():
    """Apply monkey patches to fix Django admin for Python 3.14"""
    
    # Only apply for Python 3.14+
    if sys.version_info < (3, 14):
        return
    
    try:
        from django.template import context
        
        # Save original classes
        original_context = context.Context
        
        # Create patched Context class
        class PatchedContext(original_context):
            def __copy__(self):
                try:
                    # Try the normal Django way
                    c = copy.copy(self.dicts[0])
                    c.dicts = self.dicts[1:]
                    return c
                except (AttributeError, TypeError):
                    # Fallback for Python 3.14
                    c = object.__new__(type(self))
                    if hasattr(self, 'dicts'):
                        c.dicts = self.dicts.copy()
                    else:
                        c.dicts = []
                    return c
            
            def __init__(self, dicts=None, **kwargs):
                if dicts is None:
                    dicts = []
                super().__init__(dicts, **kwargs)
        
        # Replace the Context class
        context.Context = PatchedContext
        
        # Also patch RequestContext if it exists
        if hasattr(context, 'RequestContext'):
            original_request_context = context.RequestContext
            
            class PatchedRequestContext(original_request_context, PatchedContext):
                pass
            
            context.RequestContext = PatchedRequestContext
        
        print("✓ Django admin patch applied for Python 3.14")
        
    except ImportError as e:
        print(f"Warning: Could not patch Django admin: {e}")
    except Exception as e:
        print(f"Warning: Error applying admin patch: {e}")


# Apply the patch immediately when this module is imported
apply_admin_patch()