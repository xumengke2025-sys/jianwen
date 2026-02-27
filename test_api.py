import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("LLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL")
model_name = os.getenv("LLM_MODEL_NAME")

print(f"Testing API Key: {api_key[:5]}...{api_key[-5:]}")
print(f"Base URL: {base_url}")
print(f"Model: {model_name}")

client = OpenAI(api_key=api_key, base_url=base_url)

try:
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "user", "content": "Hello, are you working?"}
        ]
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
