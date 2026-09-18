import requests

# Test chat completion with new supported model
print("Testing chat completion with groq/compound...")
chat_response = requests.post(
    'https://api.groq.com/openai/v1/chat/completions',
    headers={
        'Authorization': 'Bearer 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',
        'Content-Type': 'application/json'
    },
    json={
        "model": "groq/compound",
        "messages": [{"role": "user", "content": "Say hello in one sentence."}],
        "temperature": 0.4,
        "max_tokens": 50,
        "stream": False
    }
)
print(f"Chat completion status: {chat_response.status_code}")
if chat_response.status_code == 200:
    result = chat_response.json()
    print("Response received successfully")
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    print(f"Content: {content}")
else:
    print(f"Error: {chat_response.text}")

# Test with Persian message
print("\nTesting with Persian message...")
persian_response = requests.post(
    'https://api.groq.com/openai/v1/chat/completions',
    headers={
        'Authorization': 'Bearer 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',
        'Content-Type': 'application/json'
    },
    json={
        "model": "groq/compound",
        "messages": [{"role": "user", "content": "همچنان پوستم خارش دارد"}],
        "temperature": 0.4,
        "max_tokens": 200,
        "stream": False
    }
)
print(f"Persian message status: {persian_response.status_code}")
if persian_response.status_code == 200:
    result = persian_response.json()
    print("Persian response received successfully")
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    print(f"Content: {content}")
else:
    print(f"Error: {persian_response.text}")
