# GitHub Webhook 指南：原理、实现与配置

本文档将带你从零开始理解 Webhook，并以 `py-webhook-svc` 项目中的 `/webhook-test` 接口为例，手把手教你如何在 GitHub 上创建一个 Webhook，实现代码提交时自动通知你的服务器。

## 1. 什么是 Webhook？

在传统的 API 调用中（如你调用 GitHub API 获取用户信息），是你的程序**主动**去“拉取”（Pull）数据。这就像你每隔几分钟就去查看信箱里有没有新信件。

**Webhook** 则相反，它是一种“推送”（Push）机制。当 GitHub 上发生某些特定事件（如有人提交了代码、提出了 Issue、合并了 PR）时，GitHub 会**主动**向你预先配置好的服务器 URL 发送一个 HTTP POST 请求，把相关的数据“推”给你。

**通俗类比**：
*   **传统 API (Polling)**: 你每隔 5 分钟给快递员打电话：“我的快递到了吗？”
*   **Webhook**: 你告诉快递员：“快递到了请直接打我电话。”

### Webhook 的核心流程

1.  **事件发生**: 比如开发者向 GitHub 仓库 Push 了代码。
2.  **触发 Webhook**: GitHub 检测到该事件，查找你配置的 Webhook URL (例如 `https://api.example.com/webhook/webhook-test`)。
3.  **发送请求**: GitHub 向该 URL 发送一个 POST 请求，Body 中包含 JSON 格式的事件详情（谁提交的、提交了什么文件等）。
4.  **服务器处理**: 你的服务器接收请求，解析 JSON，并执行相应逻辑（如触发 CI/CD、发送钉钉/Slack 通知、更新数据库）。

---

## 2. 服务器端实现：接收 Webhook

为了接收 GitHub 发来的通知，我们需要一个能处理 HTTP POST 请求的接口。以下是我们 `py-webhook-svc` 项目中的实现代码。

### 2.1 核心代码解析 (`server.py`)

我们将使用 FastAPI 框架，利用 `BackgroundTasks` 来实现“快收快回”，避免 GitHub 因为超时而认为发送失败。

```python:server.py
# ... 导入必要的库 ...

# 1. 后台处理逻辑
def process_and_log_webhook(headers: dict, body: dict):
    """
    这个函数在后台运行，处理具体的 Webhook 数据。
    这样即使处理过程很慢，也不会阻塞 GitHub 的请求。
    """
    logger.info("--- Background webhook processing started ---")
    
    # 获取 GitHub 传递的事件类型（如 'push', 'ping', 'pull_request'）
    github_event = headers.get("x-github-event")
    if github_event:
        logger.info(f"GitHub Event: {github_event}")
        
    # 实际业务逻辑可以写在这里
    # 例如：检查 body 中的 ref 字段，如果是 'refs/heads/main' 则触发部署
    
    logger.info(f"Received payload: {body}")
    logger.info("--- Background webhook processing finished ---")

# 2. 定义接收接口
@app.post("/webhook-test")  # 定义为 POST 方法，因为 GitHub 只发送 POST
async def webhook_test(request: Request, background_tasks: BackgroundTasks, response: Response):
    """
    接收 GitHub Webhook 的主入口。
    """
    logger.info("Webhook received!")
    
    # 提取 Headers (包含签名、事件类型等关键信息)
    headers = dict(request.headers)
    
    # 提取 Body (JSON 数据)
    try:
        body = await request.json()
    except Exception as e:
        logger.warning(f"Invalid JSON: {e}")
        return {"error": "Invalid JSON"}

    # 将耗时任务交给后台
    background_tasks.add_task(process_and_log_webhook, headers, body)
    
    # 立即返回 202 Accepted
    # 告诉 GitHub："我收到了，你放心吧"，然后自己慢慢处理
    response.status_code = 202
    return {"status": "Accepted"}
```

### 2.2 本地测试准备

在将代码部署到公网之前，你需要确保你的服务在本地能正常运行。
```bash
# 启动服务
python server.py
```
此时你的服务运行在 `http://localhost:8000/webhook-test`。

**注意**: GitHub 无法直接访问你的 `localhost`。你需要：
1.  将服务部署到公网服务器（如 GKE, AWS EC2）。
2.  或者使用内网穿透工具（如 `ngrok`）将本地端口暴露给外网。

---

## 3. 如何在 GitHub 创建 Webhook

现在你的服务器代码已经准备好了，接下来我们需要去 GitHub 仓库进行配置，告诉 GitHub 把消息发给谁。

### 第一步：进入仓库设置
1.  打开你的 GitHub 仓库页面。
2.  点击顶部的 **"Settings"** (设置) 选项卡。
3.  在左侧侧边栏中，找到并点击 **"Webhooks"**。

### 第二步：添加 Webhook
1.  点击右上角的 **"Add webhook"** 按钮。
    *   *(此处可插入截图：Webhooks 列表页面的 Add webhook 按钮)*
2.  GitHub 可能会要求你输入密码进行确认。

### 第三步：配置 Webhook 参数 (关键步骤)

在配置页面，填写以下信息：

1.  **Payload URL (目标地址)**:
    *   填写你的服务器接口地址。
    *   **对于我们的项目**，请使用：`https://gateway.jpgcp.cloud/webhook/webhook-test`
    *   *解析：`https://gateway.jpgcp.cloud/webhook/` 是我们在 GKE 上配置的 Ingress 路径，`/webhook-test` 是我们在 `server.py` 中定义的具体 API 路径。*

2.  **Content type (内容类型)**:
    *   选择 **`application/json`**。
    *   *虽然 GitHub 支持 `application/x-www-form-urlencoded`，但在处理复杂数据结构时，JSON 更方便。*

3.  **Secret (密钥)**:
    *   （可选但强烈推荐）输入一个随机生成的长字符串。
    *   你的代码应该使用这个密钥来验证接收到的请求确实来自 GitHub，防止伪造请求。（当前示例代码暂略过了签名验证，生产环境建议加上）。

4.  **Which events would you like to trigger this webhook? (触发事件)**:
    *   选择 **Let me select individual events** (自定义事件)。
    *   在下方展开的列表中，找到并勾选 **Issues**。
    *   **本文演示场景**：我们要监听 **Issue 的创建**。勾选 Issues 后，当有人新建、编辑或关闭 Issue 时，GitHub 都会发送通知。你可以取消勾选默认的 Pushes，以便专注测试 Issue 事件。

5.  **Active**: 确保勾选，表示启用该 Webhook。

6.  点击底部的 **"Add webhook"** 按钮。

### 第四步：验证连接

1.  添加完成后，GitHub 会立即向你配置的 URL 发送一个 **Ping** 事件。
2.  在 Webhooks 列表页面，你应该能看到你刚添加的 Webhook。
3.  如果前面有一个**绿色对勾** ✅，说明 GitHub 成功连接到了你的服务器，并且你的服务器返回了 2xx 状态码。
4.  如果是一个**红色感叹号** ❌，点击它查看详情（"Recent Deliveries"），查看 Response 代码（如 404, 500, 403），据此排查服务器问题。

---

## 4. 常见问题排查

*   **收不到请求？**
    *   检查 Payload URL 是否正确（http vs https, 端口号, 路径）。
    *   检查服务器防火墙是否允许了 GitHub 的 IP段。
*   **收到 404？**
    *   检查 URL 路径是否与 `server.py` 中的 `@app.post("/webhook-test")` 匹配。
    *   别忘了 `root_path` 的影响。
*   **收到 405 Method Not Allowed？**
    *   确保你的接口装饰器是 `@app.post` 而不是 `@app.get`。GitHub Webhook 始终使用 POST。

