# 如何构建一个 GitHub App (FastAPI 版)

本文档将手把手教你如何从零开始构建一个 **GitHub App**。与使用 Personal Access Token (PAT) 的脚本不同，GitHub App 是官方推荐的集成方式，拥有更细粒度的权限控制和更安全的认证机制。

## 流程概览

1.  **准备环境**：配置 Webhook 代理 (Smee.io)。
2.  **注册 App**：在 GitHub 上创建并配置 App。
3.  **开发服务**：使用 FastAPI + Gidgethub 实现逻辑。
4.  **安装测试**：将 App 安装到你的仓库并测试。

---

## 第一步：配置 Webhook 代理 (Smee.io)

在本地开发时，GitHub 无法直接访问你的 `localhost:8000`。你需要一个公网代理。

1.  访问 [smee.io](https://smee.io/)。
2.  点击 **"Start a new channel"**。
3.  复制生成的 **Webhook Proxy URL** (例如 `https://smee.io/XyZ123...`)。

> **提示**：保持这个页面打开，之后你需要用它来接收 GitHub 发送的事件，也可以在这里实时查看 Payload 格式。

---

## 第二步：在 GitHub 上注册 App

1.  进入你的 GitHub 账号 settings -> **Developer settings** -> **GitHub Apps**。
2.  点击 **"New GitHub App"**。
3.  **配置表单**：
    *   **GitHub App name**: 给你的 App 起个名字（必须全局唯一，例如 `my-python-webhook-bot-YOURNAME`）。
    *   **Homepage URL**: 填写你的项目主页或任意 URL (如 `https://github.com`).
    *   **Webhook URL**: 粘贴刚才在 **Smee.io** 生成的 URL。
    *   **Webhook secret**: 设置一个随机字符串（例如 `my_secret_123`），**务必记住它**。
4.  **Permissions (权限设置)**：
    *   点击 *Repository permissions*。
    *   找到 **Issues**，选择 `Access: Read and write`。
    *   找到 **Metadata**，选择 `Access: Read-only` (通常默认选中)。
5.  **Subscribe to events (订阅事件)**：
    *   勾选 **Issue comment** (用于监听评论)。
    *   勾选 **Issues** (用于监听 Issue 创建/关闭)。
6.  点击 **"Create GitHub App"**。

### 关键凭证获取
创建成功后，你需要保存以下信息：
1.  **App ID**: 页面顶部显示的数字（例如 `123456`）。
2.  **Private Key**: 滚动到底部，点击 **"Generate a private key"**。这会下载一个 `.pem` 文件。

---

## 第三步：项目配置

### 1. 准备 `.env` 文件
在项目根目录创建或修改 `.env` 文件，填入刚才获取的信息：

```bash
# GitHub App 配置
GITHUB_APP_ID=123456
GITHUB_WEBHOOK_SECRET=my_secret_123

# 下载的 PEM 文件内容的路径，或者直接把内容作为字符串处理（注意换行）
# 建议开发时直接把 .pem 文件放在根目录
GITHUB_PRIVATE_KEY_PATH=./my-app-private-key.pem
```

### 2. 确认依赖
确保 `requirements.txt` 中包含以下库（你的项目目前已包含）：
*   `gidgethub`
*   `fastapi`
*   `uvicorn`
*   `aiohttp`
*   `PyJWT` (用于生成 JWT 认证)
*   `cryptography`

---

## 第四步：编写代码 (main.py)

GitHub App 的认证流程比个人 Token 稍微复杂一点：
1.  接收 Webhook。
2.  使用 **Private Key** 生成 JWT。
3.  使用 JWT 获取该仓库的 **Installation Access Token**。
4.  使用 Access Token 操作 API。

创建一个新的文件 `app_server.py` (或集成到你现有的 `server.py`)：

```python
import os
import aiohttp
import sys
from fastapi import FastAPI, Request, HTTPException
from gidgethub import routing, sansio
from gidgethub import apps
from gidgethub.aiohttp import GitHubAPI

# 初始化 FastAPI
app = FastAPI()
router = routing.Router()

# 读取配置
APP_ID = os.getenv("GITHUB_APP_ID")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH")

# 读取 Private Key 内容
try:
    with open(PRIVATE_KEY_PATH, "r") as f:
        PRIVATE_KEY = f.read()
except Exception as e:
    print(f"Error reading private key: {e}")
    sys.exit(1)

# --- 事件处理逻辑 ---

@router.register("issue_comment", action="created")
async def issue_comment_created(event, gh, *args, **kwargs):
    """
    当有新评论时触发
    """
    author = event.data["comment"]["user"]["login"]
    comment_body = event.data["comment"]["body"]
    issue_url = event.data["issue"]["comments_url"]

    # 忽略机器人自己的评论，防止无限循环
    if author == "my-python-webhook-bot[bot]": # 替换为你的 Bot 名字
        return

    print(f"User {author} commented: {comment_body}")

    # 回复评论
    message = f"你好 @{author}! 我是一个 GitHub App，我收到了你的消息。"
    await gh.post(issue_url, data={"body": message})


# --- Webhook 入口 ---

@app.post("/webhook")
async def webhook(request: Request):
    try:
        # 1. 读取 Body 和 Headers
        body = await request.body()
        secret = WEBHOOK_SECRET
        
        # 2. 解析事件并验证签名
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        
        # 3. 异步处理
        async with aiohttp.ClientSession() as session:
            # 3.1 获取 Installation ID (必须)
            # GitHub App 是安装在某个账号或仓库下的，每个安装都有唯一的 ID
            installation_id = event.data["installation"]["id"]
            
            # 3.2 获取 Access Token
            # 使用 App ID 和 Private Key 换取当前安装的 Token
            token_data = await apps.get_installation_access_token(
                GitHubAPI(session, "dummy-requester"),
                installation_id=installation_id,
                app_id=APP_ID,
                private_key=PRIVATE_KEY
            )
            token = token_data["token"]
            
            # 3.3 实例化真正的 API 客户端
            gh = GitHubAPI(session, "my-app-name", oauth_token=token)
            
            # 3.4 分发事件给 router 处理
            await router.dispatch(event, gh)
            
        return {"status": "ok"}
        
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # 启动服务
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 第五步：运行与本地转发

### 1. 启动 Smee 客户端 (转发流量)
你需要把 Smee 收到的流量转发到本地 8000 端口。你需要安装 `smee-client` (Node.js) 或者直接使用 Python 脚本转发（不推荐），最简单的是使用刚才网页上的 CLI 命令：

如果你有 npm：
```bash
npm install --global smee-client
smee -u https://smee.io/YourChannelID -t http://localhost:8000/webhook
```

**或者**，如果你不想装 npm，可以直接手动测试：
1. 启动你的 Python 服务：`python app_server.py`。
2. 在 Smee 网页上点击 "Redeliver" (如果有历史事件) 或者进入下一步直接在 GitHub 触发。

---

## 第六步：安装 App 并测试

1.  回到 GitHub App 的设置页面。
2.  点击左侧菜单的 **"Install App"**。
3.  点击你账号旁边的 **"Install"** 按钮。
4.  选择 **"Only select repositories"**，选择一个测试用的仓库。
5.  点击 **"Install"**。

### 触发测试
1.  去你刚才选择的仓库。
2.  创建一个 Issue。
3.  在 Issue 下面写一条评论 "Hello Bot"。
4.  观察你的本地终端日志，以及 Smee.io 的界面。
5.  几秒钟后，你应该能看到机器人自动回复了一条消息！

---

## 总结：GitHub App vs Personal Token

| 特性 | GitHub App | Personal Access Token (PAT) |
| :--- | :--- | :--- |
| **身份** | 独立的机器人身份 (Bot) | 代表你个人账号 |
| **权限** | 细粒度（只读 Issue，不可读代码等） | 粗粒度 (Scope) |
| **安全性** | Token 短期有效 (1小时)，通过私钥生成 | 长期有效，泄露风险大 |
| **安装范围** | 可以被别人安装到他们的仓库 | 只能操作你自己有权限的仓库 |
| **速率限制** | 更高 (针对每个安装单独计算) | 较低 (共用账号限制) |

