#!/usr/bin/env python3
"""
Fix script for investor-agent server.py
Removes the incorrect hishel.install_cache() call
"""

import sys
from pathlib import Path

def fix_server_file(file_path):
    """Fix the hishel.install_cache() issue in server.py"""
    
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return False
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Define the problematic code and the fix
    old_code = """# Configure pandas and enable HTTP caching
pd.set_option('future.no_silent_downcasting', True)
hishel.install_cache()"""
    
    new_code = """# Configure pandas
pd.set_option('future.no_silent_downcasting', True)"""
    
    # Check if the problematic code exists
    if old_code not in content:
        print("Error: Could not find the problematic code in the file.")
        print("The file may have already been fixed or modified.")
        return False
    
    # Replace the problematic code
    fixed_content = content.replace(old_code, new_code)
    
    # Backup the original file
    backup_path = file_path.with_suffix('.py.backup')
    with open(backup_path, 'w') as f:
        f.write(content)
    print(f"✓ Created backup: {backup_path}")
    
    # Write the fixed content
    with open(file_path, 'w') as f:
        f.write(fixed_content)
    print(f"✓ Fixed file: {file_path}")
    print(f"✓ Removed: hishel.install_cache() call")
    
    return True

if __name__ == "__main__":
    # Default path - adjust this to your actual path
    default_path = "investor_agent/server.py"
    
    # Get path from command line or use default
    file_path = sys.argv[1] if len(sys.argv) > 1 else default_path
    
    print(f"Fixing investor-agent server.py...")
    print(f"Target file: {file_path}\n")
    
    if fix_server_file(file_path):
        print("\n✅ SUCCESS! The file has been fixed.")
        print("\nThe investor-agent MCP server should now start without errors.")
    else:
        print("\n❌ FAILED! Could not fix the file.")
        print("\nPlease apply the fix manually:")
        print("1. Open investor_agent/server.py")
        print("2. Find line 25: hishel.install_cache()")  
        print("3. Delete that line")
        print("4. Also remove 'and enable HTTP caching' from the comment on line 24")
        sys.exit(1)
