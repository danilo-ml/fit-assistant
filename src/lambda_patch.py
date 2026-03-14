"""
Lambda environment patches for compatibility issues.
This module should be imported at the very beginning of Lambda handlers.
"""
import sys
import os
import warnings

# Patch OpenTelemetry context loading issue in Python 3.12
def patch_opentelemetry_context():
    """
    Fix for OpenTelemetry StopIteration error in Python 3.12 Lambda runtime.
    This patches the context loading to use contextvars_context directly.
    """
    try:
        # Set environment variable before opentelemetry imports
        os.environ.setdefault('OTEL_PYTHON_CONTEXT', 'contextvars_context')
        
        # Monkey-patch the _load_runtime_context function before it's called
        import opentelemetry.context
        
        # Create the context directly
        from opentelemetry.context.contextvars_context import ContextVarsRuntimeContext
        
        # Replace the broken _load_runtime_context function
        def _fixed_load_runtime_context():
            return ContextVarsRuntimeContext()
        
        opentelemetry.context._load_runtime_context = _fixed_load_runtime_context
        
        # Set the runtime context directly if not already set
        if not hasattr(opentelemetry.context, '_RUNTIME_CONTEXT') or opentelemetry.context._RUNTIME_CONTEXT is None:
            opentelemetry.context._RUNTIME_CONTEXT = ContextVarsRuntimeContext()
            
    except Exception as e:
        # If patching fails, log but don't crash
        print(f"Warning: Failed to patch OpenTelemetry context: {e}")


def patch_opentelemetry_propagators():
    """
    Fix for OpenTelemetry propagator loading failures in Lambda runtime.
    
    This patches the propagate module to gracefully handle missing propagators
    instead of raising ValueError. This is a runtime fallback in case the
    package-time patch (scripts/patch_opentelemetry_propagate.py) didn't work.
    """
    try:
        import opentelemetry.propagate
        
        # Store original get_global_textmap function
        original_get_global_textmap = getattr(
            opentelemetry.propagate, 
            'get_global_textmap', 
            None
        )
        
        if original_get_global_textmap:
            # Wrap the function to catch ValueError from missing propagators
            def safe_get_global_textmap(*args, **kwargs):
                try:
                    return original_get_global_textmap(*args, **kwargs)
                except ValueError as e:
                    if 'Propagator' in str(e) and 'not found' in str(e):
                        # Missing propagator - log warning and return a no-op propagator
                        warnings.warn(
                            f"OpenTelemetry propagator not found: {e}. "
                            f"Continuing with degraded tracing functionality.",
                            RuntimeWarning
                        )
                        # Return a minimal composite propagator
                        from opentelemetry.propagate import CompositePropagator
                        return CompositePropagator([])
                    else:
                        # Different ValueError - re-raise
                        raise
            
            # Replace the function
            opentelemetry.propagate.get_global_textmap = safe_get_global_textmap
            
    except ImportError:
        # OpenTelemetry not installed - skip patch
        pass
    except Exception as e:
        # If patching fails, log but don't crash
        print(f"Warning: Failed to patch OpenTelemetry propagators: {e}")


# Apply patches immediately when this module is imported
patch_opentelemetry_context()
patch_opentelemetry_propagators()

