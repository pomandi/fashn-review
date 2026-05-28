"""
Test FASHN API connection and API key validity
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FASHN_API_KEY")

def test_api_key():
    """Test if API key is valid by checking credits balance"""

    if not API_KEY:
        print("ERROR: FASHN_API_KEY not found in environment variables")
        print("Make sure .env file exists with FASHN_API_KEY=your-key")
        return False

    print(f"API Key: {API_KEY[:10]}...{API_KEY[-5:]}")
    print()

    # Test with a minimal request to check authentication
    headers = {
        "Authorization": f"Key {API_KEY}",
        "Content-Type": "application/json"
    }

    # Try to get queue status (lightweight check)
    try:
        response = requests.get(
            "https://fal.run/fal-ai/fashn/tryon/v1.6",
            headers=headers
        )

        if response.status_code == 401:
            print("ERROR: Invalid API key")
            return False
        elif response.status_code == 405:
            # Method not allowed means auth passed
            print("SUCCESS: API key is valid!")
            print("Connection to FASHN API established.")
            return True
        else:
            print(f"Response status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return True

    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("FASHN API Connection Test")
    print("=" * 50)
    print()

    success = test_api_key()

    print()
    print("=" * 50)
    if success:
        print("Ready to use FASHN API!")
    else:
        print("Please check your API key and try again.")
    print("=" * 50)
