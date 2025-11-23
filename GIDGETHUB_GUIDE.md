# Gidgethub 使用指南

Gidgethub 是一个现代化的、异步的 GitHub API 封装库。它的设计理念是 **Sans-I/O**（与 I/O 无关），这意味着它不强制绑定特定的网络库（如 requests 或 aiohttp），但官方提供了对 `aiohttp`、`httpx` 和 `Tornado` 的一流支持。

本项目 (`py-webhook-svc`) 已经集成了 `gidgethub` 和 `aiohttp`，非常适合构建高性能的 GitHub App 或 Webhook 服务。

## 目录

1. [安装](#1-安装)
2. [核心概念](#2-核心概念)
3. [场景一：调用 GitHub API](#3-场景一调用-github-api)
4. [场景二：处理 Webhook 事件 (FastAPI 集成)](#4-场景二处理-webhook-事件-fastapi-集成)
5. [场景三：GitHub App 认证](#5-场景三github-app-认证)
6. [常见问题](#6-常见问题)

---

## 1. 安装

本项目 `requirements.txt` 中已包含必要依赖：

```bash
pip install gidgethub aiohttp
```

如果你需要进行 GitHub App 的 JWT 签名（用于获取安装 Token），还需要安装 `PyJWT` 和 `cryptography`（项目中也已包含）。

---

## 2. 核心概念

在使用 Gidgethub 前，了解以下几个核心组件非常有帮助：

- **`gidgethub.aiohttp.GitHubAPI`**: 这是我们在 `aiohttp` 环境下使用的主要客户端类，用于发送请求。
- **`gidgethub.routing.Router`**: 用于将不同的 Webhook 事件（如 `issues`, `pull_request`）分发到对应的处理函数。
- **`gidgethub.sansio.Event`**: 代表一个 GitHub Webhook 事件，包含事件类型、Payload 数据等。
- **`gidgethub.apps`**: 提供获取 GitHub App 安装 Token 的工具函数。

---

## 3. 场景一：调用 GitHub API

最简单的用法是使用 Personal Access Token (PAT) 来调用 API。

### 示例代码：获取用户信息

```python
import asyncio
import aiohttp
import os
from gidgethub.aiohttp import GitHubAPI

async def main():
    username = "your_username" # 替换为你的 GitHub 用户名或项目名作为 User-Agent
    token = os.getenv("GITHUB_TOKEN") # 从环境变量获取 Token

    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, username, oauth_token=token)
        
        # 调用 GET /user 接口
        data = await gh.getitem("/user")
        print(f"当前登录用户: {data['login']}")
        
        # 调用 GET /repos/{owner}/{repo}
        # data = await gh.getitem("/repos/gidgethub/gidgethub")
        # print(data)

if __name__ == "__main__":
    asyncio.run(main())
```

**常用方法：**
- `gh.getitem(url)`: 发送 GET 请求获取单个对象。
- `gh.getiter(url)`: 发送 GET 请求获取列表（自动处理分页）。
- `gh.post(url, data)`: 发送 POST 请求。
- `gh.patch(url, data)`: 发送 PATCH 请求。
- `gh.put(url, data)`: 发送 PUT 请求.
- `gh.delete(url)`: 发送 DELETE 请求。

---

## 4. 场景二：处理 Webhook 事件 (FastAPI 集成)

这是 Gidgethub 最强大的功能之一：**路由系统**。它可以让你像写 Web 路由一样处理 GitHub 事件。

### 示例代码：FastAPI Webhook 服务

假设我们要创建一个服务，当有人在 Issue 中评论时，自动回复 "Thank you!"。

```python
# main.py
from fastapi import FastAPI, Request, Response
from gidgethub import routing, sansio
from gidgethub.aiohttp import GitHubAPI
import aiohttp
import os

app = FastAPI()
router = routing.Router() # 创建 Gidgethub 路由

# 注册事件处理器：监听 Issue Comment 的创建事件
@router.register("issue_comment", action="created")
async def issue_comment_event(event, gh, *args, **kwargs):
    """
    当 issue_comment 被创建时触发
    event: 包含 webhook 数据的对象
    gh: GitHubAPI 客户端实例
    """
    url = event.data["issue"]["comments_url"]
    author = event.data["comment"]["user"]["login"]
    
    message = f"Hello @{author}, thanks for the comment!"
    
    # 调用 GitHub API 回复评论
    await gh.post(url, data={"body": message})
    print(f"Replied to {author}")

@app.post("/webhook")
async def webhook(request: Request):
    """
    FastAPI 的入口端点
    """
    # 1. 读取 Headers 和 Body
    body = await request.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    
    # 2. 构建 Event 对象 (会自动验证签名)
    event = sansio.Event.from_http(request.headers, body, secret=secret)
    
    # 3. 初始化 GitHubAPI 客户端
    # 注意：实际生产中通常需要根据 event.data['installation']['id'] 获取对应的 Installation Token
    # 这里为了演示简化，直接使用环境变量中的 PAT
    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "my-bot", oauth_token=os.getenv("GITHUB_TOKEN"))
        
        # 4. 将事件分发给 router
        # router 会查找匹配 @router.register 的函数并执行
        await router.dispatch(event, gh)
        
    return Response(status_code=200)
```

**关键点：**
1. **`@router.register("event_name", action="action_type")`**: 装饰器用于绑定处理函数。
2. **`sansio.Event.from_http`**: 自动处理 Header 解析和 HMAC 签名验证（如果提供了 secret）。
3. **`router.dispatch`**: 负责调用对应的处理函数。

---

## 5. 场景三：GitHub App 认证

对于正式的 GitHub App，推荐使用 **Installation Token** 而不是 Personal Access Token。因为 Installation Token 权限更细粒度，且是短期的。

你需要：
1. **App ID**
2. **Private Key** (PEM 格式)
3. **Webhook Payload 中的 Installation ID**

### 示例代码：获取 Installation Token

```python
import time
import jwt
from gidgethub import apps

def get_jwt(app_id: str, private_key: str) -> str:
    """
    生成用于作为 GitHub App 身份验证的 JWT
    """
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")

# 在 Webhook 处理逻辑中：
@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    event = sansio.Event.from_http(request.headers, body, secret=secret)
    
    app_id = os.getenv("GITHUB_APP_ID")
    private_key = os.getenv("GITHUB_PRIVATE_KEY")
    
    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "my-app")
        
        # 1. 获取 installation_id
        if "installation" in event.data:
            installation_id = event.data["installation"]["id"]
            
            # 2. 使用 apps.get_installation_access_token 获取 Token
            # 注意：这需要先用 JWT 身份调用
            token_data = await apps.get_installation_access_token(
                gh,
                installation_id=installation_id,
                app_id=app_id,
                private_key=private_key
            )
            token = token_data["token"]
            
            # 3. 使用新的 token 重新实例化 gh 客户端（或者更新 token）
            gh_app = GitHubAPI(session, "my-app", oauth_token=token)
            
            # 4. 使用带有权限的 gh_app 分发事件
            await router.dispatch(event, gh_app)
            
    return Response(status_code=200)
```

---

## 6. 常见问题

**Q: 为什么我收不到 Webhook 事件？**
A: 
1. 确保你的服务公网可达（开发时推荐使用 `smee.io` 或 `ngrok`）。
2. 确保在 GitHub Repo 或 App 设置中勾选了对应的事件类型（如 `Issues`, `Pull requests`）。
3. 检查 `Content-Type` 是否设置为 `application/json`。

**Q: 如何处理分页数据？**
A: 使用 `gh.getiter()` 而不是 `gh.getitem()`。
```python
async for repo in gh.getiter("/user/repos"):
    print(repo["name"])
```

**Q: 什么是 Rate Limit？**
A: GitHub API 有速率限制。Gidgethub 会自动读取响应头中的 `X-RateLimit-Remaining` 等信息。如果触发限制，可能会抛出 `gidgethub.RateLimitExceeded` 异常，建议在生产环境中捕获并处理。

