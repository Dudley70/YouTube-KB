#!/usr/bin/env python3
"""Test raw API response"""

import os
from anthropic import Anthropic

api_key = os.environ.get('ANTHROPIC_API_KEY')
print(f"API key: {api_key[:20]}...{api_key[-10:]}")

client = Anthropic(api_key=api_key)

response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1000,
    messages=[{
        "role": "user",
        "content": "Return JSON: {\"test\": \"hello\"}"
    }]
)

print(f"\nResponse type: {type(response)}")
print(f"Response: {response}")
print(f"\nContent: {response.content}")
print(f"Content[0]: {response.content[0]}")
print(f"Text: {response.content[0].text}")
