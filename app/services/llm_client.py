import os
import requests

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

def call_llm(prompt: str) -> str:
    if LLM_PROVIDER == "groq":
        return call_groq(prompt)
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")

def call_groq(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=data,
    )

    if response.status_code != 200:
        print(f"Groq API Error: {response.status_code}")
        print(f"Response: {response.text}")

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
