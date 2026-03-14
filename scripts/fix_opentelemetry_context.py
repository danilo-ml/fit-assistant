#!/usr/bin/env python3
"""
Fix OpenTelemetry context module for Python 3.12 Lambda compatibility.
Wraps _load_runtime_context in try-except to catch StopIteration.
"""
import sys
import re

def fix_opentelemetry_context(file_path):
    """Fix the opentelemetry context __init__.py file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find the _load_runtime_context function
        # Replace the entire function with a wrapped version
        pattern = r'def _load_runtime_context\(\) -> _RuntimeContext:.*?(?=\n_RUNTIME_CONTEXT|\ndef [a-z_]|\Z)'
        
        replacement = '''def _load_runtime_context() -> _RuntimeContext:
    """Load runtime context - patched for Python 3.12 compatibility."""
    try:
        from os import environ
        from opentelemetry.environment_variables import OTEL_PYTHON_CONTEXT
        
        default_context = "contextvars_context"
        configured_context = environ.get(OTEL_PYTHON_CONTEXT, default_context)
        
        try:
            from importlib.metadata import entry_points
            eps = entry_points(group="opentelemetry_context", name=configured_context)
            for ep in eps:
                return ep.load()()
        except Exception:
            pass
        
        # Fallback to default
        from opentelemetry.context.contextvars_context import ContextVarsRuntimeContext
        return ContextVarsRuntimeContext()
    except Exception:
        # Ultimate fallback
        from opentelemetry.context.contextvars_context import ContextVarsRuntimeContext
        return ContextVarsRuntimeContext()
'''
        
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"✓ Successfully fixed {file_path}")
        return True
            
    except Exception as e:
        print(f"✗ Error fixing {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: fix_opentelemetry_context.py <path_to_opentelemetry_context_init.py>")
        sys.exit(1)
    
    success = fix_opentelemetry_context(sys.argv[1])
    sys.exit(0 if success else 1)
