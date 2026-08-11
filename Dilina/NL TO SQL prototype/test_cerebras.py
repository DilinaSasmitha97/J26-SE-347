from openai import OpenAI

key = "csk-e36v9t4wf33wd86885ymd6myetev54949h2k4xxvetr5mjk4"
client = OpenAI(api_key=key, base_url="https://api.cerebras.ai/v1")

candidates = [
    "gemma-4-31b",
    "gemma-4",
    "gemma4",
    "gpt-oss",
    "glm-4.7",
    "llama-3.3-70b",
    "llama3.1-8b",
    "llama-3.1-8b"
]

print("=== Testing Cerebras Cloud Model IDs ===")
for m in candidates:
    try:
        res = client.chat.completions.create(
            model=m,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print(f"[SUCCESS] MODEL VALID: '{m}' => {res.choices[0].message.content.strip()}")
    except Exception as e:
        print(f"[FAILED] MODEL FAILED: '{m}' => {e}")
