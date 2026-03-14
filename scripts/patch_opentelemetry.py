#!/usr/bin/env python3
"""
Patch OpenTelemetry context module for Python 3.12 Lambda compatibility.
This fixes the StopIteration error in _load_runtime_context().
"""
import sys

def patch_opentelemetry_context(file_path):
    """Patch the opentelemetry context __init__.py file."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        patched_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Look for the next() calls that need wrapping
            if 'return next(  # type: ignore' in line:
                # Get the indentation
                indent = len(line) - len(line.lstrip())
                indent_str = ' ' * indent
                
                # Add try block
                patched_lines.append(f'{indent_str}try:\n')
                patched_lines.append(line)
                
                # Find the closing parenthesis (could be on next lines)
                j = i + 1
                while j < len(lines) and ')' not in lines[j]:
                    patched_lines.append(lines[j])
                    j += 1
                
                # Add the line with closing parenthesis
                if j < len(lines):
                    patched_lines.append(lines[j])
                
                # Add except block
                patched_lines.append(f'{indent_str}except StopIteration:\n')
                patched_lines.append(f'{indent_str}    from opentelemetry.context.contextvars_context import ContextVarsRuntimeContext\n')
                patched_lines.append(f'{indent_str}    return ContextVarsRuntimeContext()\n')
                
                i = j + 1
            else:
                patched_lines.append(line)
                i += 1
        
        with open(file_path, 'w') as f:
            f.writelines(patched_lines)
        
        print(f"✓ Successfully patched {file_path}")
        return True
            
    except Exception as e:
        print(f"✗ Error patching {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: patch_opentelemetry.py <path_to_opentelemetry_context_init.py>")
        sys.exit(1)
    
    success = patch_opentelemetry_context(sys.argv[1])
    sys.exit(0 if success else 1)
