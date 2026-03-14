#!/usr/bin/env python3
"""
Patch OpenTelemetry propagate module to skip missing propagators.
This fixes the "Propagator tracecontext not found" error.

Enhanced version that:
1. Searches for exact pattern in OpenTelemetry propagate module
2. Replaces ValueError raise with try-except block that logs warning and continues
3. Verifies the patch was applied successfully
"""
import sys
import re

def patch_opentelemetry_propagate(file_path):
    """
    Patch the opentelemetry propagate __init__.py file.
    
    The patch modifies the propagator loading logic to gracefully handle
    missing propagators instead of raising ValueError. This is necessary
    for Lambda environments where some propagators may not be available.
    
    The patch targets the specific pattern in OpenTelemetry 1.20.0+:
        except StopIteration:
            raise ValueError(
                f"Propagator {propagator} not found..."
            )
    
    And replaces it with:
        except StopIteration:
            # Patched: skip missing propagators in Lambda
            logger.warning(
                f"Propagator {propagator} not found, skipping. "
                f"This is expected in Lambda environments."
            )
            continue
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Primary strategy: Target the exact pattern from OpenTelemetry propagate module
        # This handles the StopIteration -> ValueError pattern when propagators are not found
        # Pattern matches:
        #     except StopIteration:
        #         raise ValueError(
        #             f"Propagator {propagator} not found. It is either misspelled or not installed."
        #         )
        
        pattern = re.compile(
            r'(\s+)except StopIteration:\s*\n'
            r'\s+raise ValueError\(\s*\n'
            r'\s+f["\']Propagator \{propagator\}[^)]+\)\s*\n',
            re.MULTILINE
        )
        
        # Check if pattern exists
        if pattern.search(content):
            # Replace with warning and continue
            replacement = (
                r'\1except StopIteration:\n'
                r'\1    # Patched: skip missing propagators in Lambda\n'
                r'\1    logger.warning(\n'
                r'\1        f"Propagator {propagator} not found, skipping. "\n'
                r'\1        f"This is expected in Lambda environments where some propagators may not be available."\n'
                r'\1    )\n'
                r'\1    continue\n'
            )
            
            content = pattern.sub(replacement, content)
        else:
            # Fallback: Try simpler pattern for single-line ValueError
            pattern_simple = re.compile(
                r'(\s+)except StopIteration:\s*\n'
                r'(\s+)raise ValueError\([^)]+\)',
                re.MULTILINE
            )
            
            if pattern_simple.search(content):
                replacement_simple = (
                    r'\1except StopIteration:\n'
                    r'\2# Patched: skip missing propagators in Lambda\n'
                    r'\2logger.warning(f"Propagator {propagator} not found, skipping")\n'
                    r'\2continue'
                )
                
                content = pattern_simple.sub(replacement_simple, content)
        
        # Check if any patch was applied
        if content != original_content:
            # Verify the patch contains our marker
            if '# Patched: skip missing propagators in Lambda' in content:
                with open(file_path, 'w') as f:
                    f.write(content)
                print(f"✓ Successfully patched {file_path}")
                print(f"  Applied patch to handle missing propagators gracefully")
                return True
            else:
                print(f"✗ Patch applied but marker not found in {file_path}")
                return False
        else:
            # No patch applied - check if already patched
            if '# Patched: skip missing propagators in Lambda' in content:
                print(f"✓ {file_path} already patched")
                return True
            else:
                print(f"✗ Could not find patch location in {file_path}")
                print(f"  The OpenTelemetry propagate module may have a different structure")
                print(f"  than expected. Manual inspection may be required.")
                return False
            
    except Exception as e:
        print(f"✗ Error patching {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: patch_opentelemetry_propagate.py <path_to_opentelemetry_propagate_init.py>")
        sys.exit(1)
    
    success = patch_opentelemetry_propagate(sys.argv[1])
    sys.exit(0 if success else 1)

