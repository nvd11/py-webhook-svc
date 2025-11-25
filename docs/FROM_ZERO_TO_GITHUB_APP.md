# 从零构建 GitHub App：原理、实现与部署指南

本文档将详细介绍如何从零开始构建、部署并配置一个 GitHub App。我们将使用 `py-webhook-svc` 作为示例项目，展示如何通过 GitHub App 自动监听 Pull Request 并发送欢迎评论。

## 1. 什么是 GitHub App？

**GitHub App** 是 GitHub 官方推荐的集成方式，用于扩展 GitHub 的功能。

### GitHub App 与 Webhook 的关系

很多开发者容易混淆 GitHub App 和 Webhook。其实可以这样理解：

*   **Webhook 是底层机制**：它负责将 GitHub 上的事件（如代码提交、PR 创建）推送到你的服务器。
*   **GitHub App 是上层应用**：它不仅包含了 Webhook 功能，还通过**安装 (Installation)** 的方式，解决了“如何方便地将 Webhook 应用到多个仓库”以及“如何安全授权”的问题。

**简单来说：**
当你将一个 GitHub App 安装到某个组织或仓库时，GitHub 会自动为这些仓库配置好 Webhook，并授予你的应用特定的权限。你不需要手动去每个仓库的 Settings 里填 Webhook URL，一切都是自动化的。

---

## 2. 项目概况：py-webhook-svc

`py-webhook-svc` 是一个基于 Python (FastAPI) 的 Web 服务，它作为一个 GitHub App 的后端，接收并处理来自 GitHub 的 Webhook 事件。

### 核心功能

该服务的主要功能是：监听仓库的 `pull_request` `opened` 事件，并在新创建的 PR 下自动发表一条欢迎评论。

### 关键代码解析

核心逻辑位于 `server.py` 文件中。我们使用了 `gidgethub` 库来简化 GitHub API 的交互。

#### 1. 监听事件

使用 `@router.register` 装饰器来注册我们感兴趣的事件。这里我们订阅了 `pull_request` 的 `opened` 动作。

```python
# server.py

from gidgethub import routing

router = routing.Router()

# 监听 pull_request 事件，且动作是 opened (新建)
@router.register("pull_request", action="opened")
async def pull_request_opened_event(event, gh, *args, **kwargs):
    """
    当一个新的 Pull Request 被创建时触发
    """
    # event.data 包含了 GitHub 发送的完整 JSON payload
    pr_info = event.data["pull_request"]
    pr_number = pr_info["number"]
    author = pr_info["user"]["login"]
    
    # 动态获取仓库信息 (这是避免 Not Found 错误的关键)
    repo_info = event.data["repository"]
    repo_owner = repo_info["owner"]["login"]
    repo_name = repo_info["name"]
    
    # ... 后续处理逻辑 ...
```

#### 2. 处理逻辑与 API 调用

在获取到 PR 的相关信息（如 PR 编号、作者、仓库名）后，我们调用 Service 层的方法向 GitHub API 发送评论。

```python
    # 构建欢迎消息
    welcome_message = f"Thanks for opening this PR, @{author}! We will review it soon."
    
    # 初始化 Service
    gh_service = GithubService(gh)
    
    # 调用 GitHub API 发表评论
    # 注意：这里使用的是基于 Installation Token 的 gh 客户端
    comment_result = await gh_service.post_general_pr_comment(
        owner=repo_owner, 
        repo_name=repo_name, 
        pr_number=pr_number, 
        comment_body=welcome_message
    )
```

---

## 3. 部署到 GKE (Google Kubernetes Engine)

为了让 GitHub 能把事件推送给我们，我们的服务必须部署在公网可访问的服务器上。这里我们使用 GKE 和 Helm 进行部署。

### 前提条件
*   已拥有 GCP 项目和 GKE 集群。
*   本地已安装 `kubectl` 和 `helm`。
*   已配置好 Ingress Controller (如 Nginx Ingress) 和公网 IP。

### 部署步骤

1.  **打包镜像**：构建 Docker 镜像并推送到 GCR/Artifact Registry。
    ```bash
    docker build -t gcr.io/YOUR_PROJECT/py-webhook-svc:latest .
    docker push gcr.io/YOUR_PROJECT/py-webhook-svc:latest
    ```

2.  **配置 Helm Chart**：
    修改 `py-webhook-svc-chart/values.yaml`，填入你的镜像地址和 Ingress 域名。
    ```yaml
    image:
      repository: gcr.io/YOUR_PROJECT/py-webhook-svc
      tag: latest
    
    ingress:
      enabled: true
      hosts:
        - host: webhook.your-domain.com
          paths:
            - path: /webhook
              pathType: Prefix
    ```

3.  **配置密钥 (Secrets)**：
    GitHub App 需要 `GITHUB_APP_ID`, `GITHUB_WEBHOOK_SECRET` 和 `GITHUB_PRIVATE_KEY`。建议使用 Kubernetes Secrets 管理。

4.  **执行部署**：
    ```bash
    helm upgrade --install py-webhook-svc ./py-webhook-svc-chart
    ```

5.  **验证公网访问**：
    确保访问 `https://webhook.your-domain.com/webhook` 能得到响应（通常是 405 Method Not Allowed，因为浏览器发的是 GET，而 webhook 是 POST，这说明服务是通的）。

---

## 4. 配置 GitHub App

现在我们的服务已经在公网上跑起来了，接下来需要在 GitHub 上创建并配置 App，将其指向我们的服务地址。

### 第一步：创建 App
1.  进入 **Settings** -> **Developer settings** -> **GitHub Apps** -> **New GitHub App**。
2.  **GitHub App name**: 起一个唯一的名字。
3.  **Homepage URL**: 你的项目主页。
4.  **Webhook URL**: 填入你刚才部署的公网地址，例如 `https://webhook.your-domain.com/webhook`。
5.  **Webhook secret**: 设置一个强密码，并确保它与你部署服务时环境变量中的 `GITHUB_WEBHOOK_SECRET` 一致。

> **⚠️ 重要提示：Secret 必须一致**
>
> 你在这里填写的 Secret 必须与你的服务中 `GITHUB_WEBHOOK_SECRET` 环境变量完全一致。GitHub 会用这个 Secret 对请求进行签名，你的服务会用同一个 Secret 进行验签。如果两者不匹配，你的服务将拒绝接收请求（报错 400 或 401）。
>
> **相关代码展示 (`server.py`)：**
> ```python
> @app.post("/")
> @app.post("/webhook")
> async def webhook(request: Request, background_tasks: BackgroundTasks):
>     # 1. 读取 Body 和 Headers
>     body = await request.body()
>     # 从环境变量获取 Secret
>     secret = os.getenv("GITHUB_WEBHOOK_SECRET")
>     
>     try:
>         # 2. 验证签名：from_http 会自动使用 secret 校验请求的签名是否合法
>         # 如果 Secret 不匹配，这里会直接抛出异常，拒绝请求
>         event = sansio.Event.from_http(request.headers, body, secret=secret)
>         # ...
> ```

*(在此处插入截图：GitHub App 基本信息配置页面)*

### 第二步：权限设置 (Permissions)
为了让我们的 App 能读取 PR 并发表评论，需要授予以下权限：

在 **Repository permissions** 栏目下：
1.  找到 **Pull requests**。
2.  选择 **Read and write** (读写权限)。
    *   *注：选择 Write 会自动勾选 Read。*

*(在此处插入截图：Repository permissions 设置页面)*

### 第三步：事件订阅 (Subscribe to events)
告诉 GitHub 我们关心哪些事件。

在 **Subscribe to events** 栏目下：
1.  勾选 **Pull request**。

*(在此处插入截图：Subscribe to events 设置页面)*

### 第四步：保存并获取凭证
点击 **Create GitHub App**。
创建成功后，你需要记录下 **App ID**，并生成并下载 **Private Key** (.pem 文件)。这些将用于更新你的 GKE 部署配置。

#### 为什么需要这些凭证？(目的)
GitHub App 的认证机制非常安全且独特。为了让我们的服务能够以 App 的身份操作仓库（例如发表评论），我们需要获取一个 **Installation Access Token**。而获取这个 Token 的过程，必须使用 **App ID** 和 **Private Key** 进行签名验证。

简单流程如下：
1.  服务使用 **App ID** 和 **Private Key** 生成一个 **JWT (JSON Web Token)**。
2.  使用这个 JWT 调用 GitHub API，申请一个临时的 **Installation Access Token**。
3.  使用这个 Installation Access Token 去调用其他 API（如发评论）。

此外，使用这种认证方式的一个关键优势是：**我们的应用将以独立的 Bot 身份（例如 `py-webhook-svc[bot]`）在 PR 中发表评论，不需要提供任何个人的账号 Token (PAT)。** 这样既保护了个人账号安全，又使得自动化操作的身份更加明确和独立。

#### 代码实现原理
在我们的 `src/services/gh_service.py` 中，`create_installation_access_token` 函数实现了这一逻辑：

```python
import jwt
import time
import aiohttp

async def create_installation_access_token(app_id, private_key, installation_id, base_url="https://api.github.com"):
    # 1. 生成 JWT (JSON Web Token)
    # payload 中包含签发时间(iat)、过期时间(exp)和发布者(iss=App ID)
    def generate_jwt(app_id, private_key):
        payload = {
            'iat': int(time.time()),
            'exp': int(time.time()) + (10 * 60),  # JWT 有效期 10 分钟
            'iss': app_id
        }
        # 使用 Private Key 进行 RS256 签名
        return jwt.encode(payload, private_key, algorithm='RS256')

    jwt_token = generate_jwt(app_id, private_key)

    # 2. 使用 JWT 向 GitHub 申请 Installation Token
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github+json'
    }
    url = f"{base_url}/app/installations/{installation_id}/access_tokens"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers) as response:
            if response.status == 201:
                data = await response.json()
                return data.get('token')  # 获取到 Installation Token
            # ... 错误处理 ...
```

---

## 5. 安装 GitHub App

App 创建好了，现在需要把它安装到具体的账号或仓库上才能生效。

1.  在 GitHub App 的设置页面左侧菜单，点击 **Install App**。
2.  找到你的账号或组织，点击 **Install**。
3.  选择 **All repositories** (所有仓库) 或 **Only select repositories** (指定仓库)。
    *   *建议先选择一个测试仓库进行测试。*
4.  点击 **Install** 按钮确认。

*(在此处插入截图：安装 App 选择仓库页面)*

---

## 6. 测试验证

一切准备就绪，让我们来验证一下。

1.  **创建 PR**：在刚才安装了 App 的测试仓库中，创建一个新的 Pull Request。
    *   你可以修改 `README.md` 或任意文件，提交到一个新分支，然后提 PR 到 main 分支。
2.  **查看效果**：
    *   PR 创建成功后，刷新页面。
    *   你应该能看到一条来自你的 GitHub App (Bot) 的评论：
        > "Thanks for opening this PR, @your-username! We will review it soon."

*(在此处插入截图：PR 页面成功显示机器人评论)*

如果看到了这条评论，恭喜你！你已经成功从零构建并部署了一个能够自动响应 PR 的 GitHub App。

---

## 7. 如何让其他人安装？(发布与分享)

默认情况下，你创建的 GitHub App 是 **Private (私有)** 的，只有你自己的账号或组织可以安装。如果你想让其他人也能使用这个 App，需要将其设置为 **Public (公开)**。

### 步骤一：设置公开
1.  回到你的 GitHub App 设置页面 (`Settings` -> `Developer settings` -> `GitHub Apps` -> `你的应用`)。
2.  在左侧菜单中选择 **Advanced**。
3.  找到 **Danger zone** 区域。
4.  点击 **Make public** 按钮。

*(注：设置为公开并不意味着你的代码被公开，只是允许其他用户安装这个 App)*

### 步骤二：分享安装链接
App 公开后，你可以直接分享它的公共页面链接给其他人。
链接格式通常为：
`https://github.com/apps/<你的应用名称-slug>`

用户访问这个链接，点击右上角的 **Install** 按钮，即可将你的 App 安装到他们自己的账号或仓库中。

### 步骤三：发布到 Marketplace (可选)
如果你希望通过 GitHub 官方市场推广你的应用，可以申请上架 **GitHub Marketplace**。

**上架的好处：**
*   **官方认证**：增加用户的信任度。
*   **流量曝光**：用户可以在 Marketplace 中通过分类或搜索找到你的应用。
*   **收费能力**：如果你的服务是收费的，可以直接利用 GitHub 的计费系统。

**上架的基本要求：**
1.  **App 必须是 Public 的**。
2.  **完成身份验证**：如果是组织发布的 App，需要验证域名所有权；如果是个人，需要启用 2FA。
3.  **Listing 信息**：填写详细的描述、上传 Logo 和截图、提供隐私政策和用户支持链接。
4.  **Webhook 活跃**：App 必须已经至少在一个仓库中安装并能成功接收事件。

满足条件后，在 App 设置页面的左侧菜单选择 **Marketplace**，点击 **List in Marketplace** 即可开始提交审核流程。
