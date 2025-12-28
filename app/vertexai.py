"""
Test script for Gemini 3 Pro Preview via GCP Vertex AI.

Prerequisites:
1. Install: pip install google-genai
2. Authenticate with GCP:
   $ gcloud auth application-default login

3. Make sure Vertex AI API is enabled in your GCP project
"""

import os
import sys


def test_gemini():
    """Test Gemini 3 Pro Preview via Vertex AI."""
    
    try:
        from google import genai
    except ImportError:
        print("❌ Error: google-genai not installed")
        print("Run: pip install google-genai")
        sys.exit(1)
    
    # Configuration
    PROJECT_ID = os.getenv("GCP_PROJECT_ID", "continuum-ai-482615")
    LOCATION = os.getenv("GCP_LOCATION", "global")
    MODEL = "gemini-3-pro-preview"
    
    print(f"🔧 Configuration:")
    print(f"   Project: {PROJECT_ID}")
    print(f"   Location: {LOCATION}")
    print(f"   Model: {MODEL}")
    print()
    
    try:
        # Initialize client
        print("🔌 Connecting to Vertex AI...")
        client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=LOCATION
        )
        
        # Test message
        print("📤 Sending test message...")
        response = client.models.generate_content(
            model=MODEL,
            contents="Hello! Say 'Connection successful!' and tell me one interesting fact."
        )
        
        # Print response
        print("✅ Success! Response:")
        print("-" * 50)
        print(response.text)
        print("-" * 50)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n🔍 Troubleshooting:")
        print("1. Run: gcloud auth application-default login")
        print("2. Check if Vertex AI API is enabled in GCP Console")
        print("3. Try different locations: global, us-central1")
        sys.exit(1)


if __name__ == "__main__":
    test_gemini()