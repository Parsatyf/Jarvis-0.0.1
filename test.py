import requests

url = "http://localhost:11434/api/chat"
payload = {
    "model": "deepseek-coder:6.7b",
    "messages": [{"role": "user", "content": "hello"}],
    "stream": False,
}

r = requests.post(url, json=payload, timeout=30, proxies={"http": None, "https": None})
print("status:", r.status_code)
print("text head:", r.text[:200])
print("json keys:", list(r.json().keys()))
