import os
import base64
from dotenv import load_dotenv
from anthropic import Anthropic
from PIL import ImageGrab

def capture_screenshot():
    """Capture a screenshot and convert it to base64"""
    # Capture the full screen
    screenshot = ImageGrab.grab()
    
    # Save temporarily and convert to base64
    temp_path = "temp_screenshot.png"
    screenshot.save(temp_path)
    
    with open(temp_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    
    # Keep the temporary screenshot file for reference
    print(f"Screenshot saved as: {temp_path}")
    return base64_image

def get_computer_use_command(api_key, screenshot_base64):
    """Get command suggestion from Claude using Computer Use"""
    client = Anthropic(api_key=api_key)
    
    message = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot_base64
                    }
                },
                {
                    "type": "text",
                    "text": "What command should I run based on what you see in this screenshot?"
                }
            ]
        }]
    )
    
    return message.content[0].text

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("Please set ANTHROPIC_API_KEY in environment variables or .env file")
    
    print("Capturing screenshot...")
    screenshot = capture_screenshot()
    
    print("Getting command suggestion from Claude...")
    command = get_computer_use_command(api_key, screenshot)
    
    print("\nClaude suggests running:")
    print(command)

if __name__ == "__main__":
    main()
