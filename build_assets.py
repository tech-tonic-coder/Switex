"""
Switex — Build Assets Helper (Updated with Transparent Background Support)
Automatically handles generation and cleanup of the grayscale icon during build time.
"""
import os
import sys
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COLOR_ICON = os.path.join(BASE_DIR, 'switex.ico')
GRAY_ICON = os.path.join(BASE_DIR, 'switex_gray.ico')

def generate_gray_icon():
    """Generates the grayscale icon dynamically with transparent background support."""
    if not os.path.exists(COLOR_ICON):
        print(f"[-] Error: Base icon '{COLOR_ICON}' not found. Cannot generate grayscale asset.")
        sys.exit(1)
        
    try:
        print("[+] Generating temporary grayscale icon (with transparent background)...")
        with Image.open(COLOR_ICON) as img:
            # Handle possible transparency channel
            if img.mode == 'RGBA':
                # Convert the RGB channels to grayscale, keep the Alpha channel
                alpha = img.split()[-1]
                # Combine original alpha with modified RGB channels
                gray_img = img.convert('L').convert('RGBA')
                gray_img.putalpha(alpha)
            else:
                # If no transparency, just convert to grayscale
                gray_img = img.convert('L')
            
            gray_img.save(GRAY_ICON, format='ICO')
        print("[+] Temporary grayscale icon created successfully.")
    except Exception as e:
        print(f"[-] Failed to generate grayscale icon: {e}")
        sys.exit(1)

def cleanup_gray_icon():
    """Removes the temporary grayscale icon from the workspace after compilation."""
    if os.path.exists(GRAY_ICON):
        try:
            print("[+] Cleaning up temporary grayscale icon from project directory...")
            os.remove(GRAY_ICON)
            print("[+] Project directory cleaned.")
        except Exception as e:
            print(f"[-] Warning: Failed to delete temporary icon: {e}")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--cleanup':
        cleanup_gray_icon()
    else:
        generate_gray_icon()