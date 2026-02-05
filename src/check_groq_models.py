
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

def list_models():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        print("Error: GROQ_API_KEY not found in .env")
        return

    client = Groq(api_key=key)
    try:
        models = client.models.list()
        print("\n--- Available Groq Models ---")
        for m in models.data:
            print(f"- {m.id}")
            
    except Exception as e:
        print(f"Error fetching models: {e}")

if __name__ == "__main__":
    list_models()
