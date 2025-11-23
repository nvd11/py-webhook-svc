import hmac
import hashlib
import json
import requests
import sys

# Configuration
SECRET = "ilovehsbc"
IP = "34.111.35.228"
HOST = "jpgcp.shop"
# 根据 HTTPRoute，/webhook 前缀被重写为 /
# 如果 server.py 监听 @app.post("/webhook")，那么请求路径到达应用时必须是 /webhook
# 所以如果在 Gateway 这一层 /webhook 被去掉了，我们需要在 URL 里再加一层 /webhook
# 即 http://jpgcp.shop/webhook/webhook -> Gateway 收到 /webhook/webhook -> Rewrite /webhook to / -> Pod 收到 /webhook
URL = f"http://{IP}/webhook/webhook"

payload = {
    "ref": "refs/heads/main",
    "before": "0000000000000000000000000000000000000000",
    "after": "1111111111111111111111111111111111111111",
    "repository": {
        "name": "test-repo",
        "full_name": "test-user/test-repo"
    },
    "pusher": {
        "name": "test-user"
    }
}

body = json.dumps(payload).encode('utf-8')

# Calculate signature
signature = hmac.new(SECRET.encode('utf-8'), body, hashlib.sha256).hexdigest()

headers = {
    "Host": HOST,
    "Content-Type": "application/json",
    "X-GitHub-Event": "push",
    "X-GitHub-Delivery": "test-delivery-id",
    "X-Hub-Signature-256": f"sha256={signature}"
}

print(f"Sending request to {URL} with Host: {HOST}")
try:
    response = requests.post(URL, data=body, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
