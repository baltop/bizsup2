#!/usr/bin/env python3
"""
Fix URL-encoded filenames in GIBAMONEY output directory
"""
import os
import shutil
from urllib.parse import unquote

def fix_filenames(directory):
    """Fix URL-encoded filenames in directory recursively"""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if '%' in file:
                old_path = os.path.join(root, file)
                try:
                    # Decode URL-encoded filename
                    decoded_filename = unquote(file)
                    new_path = os.path.join(root, decoded_filename)
                    
                    # Rename file
                    print(f"Renaming: {file} -> {decoded_filename}")
                    shutil.move(old_path, new_path)
                except Exception as e:
                    print(f"Error renaming {file}: {e}")

if __name__ == "__main__":
    fix_filenames("output/gibamoney")
    print("Filename fixing completed!")