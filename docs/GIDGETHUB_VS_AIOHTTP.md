# Gidgethub.aiohttp vs 普通 aiohttp

简单来说：**`gidgethub.aiohttp` 不是 `aiohttp` 的替代品，而是它的“GitHub 专用增强包”。**

它们的关系是 **包含与被包含** 的关系，而不是平行的竞争关系。

---

## 1. 核心区别一览

| 特性 | 普通 aiohttp (`aiohttp.ClientSession`) | Gidgethub (`gidgethub.aiohttp.GitHubAPI`) |
| :--- | :--- | :--- |
| **定位** | **通用** HTTP 客户端 | **GitHub 专用** API 客户端 |
| **底层实现** | 处理 TCP 连接、SSL、HTTP 协议解析 | **不处理网络**，它直接调用传入的 `aiohttp.ClientSession` 发送请求 |
| **URL 处理** | 必须提供完整 URL (e.g., `https://api.github.com/user`) | 只需提供路径 (e.g., `/user`)，自动补全基地址 |
| **认证 (Auth)** | 需要手动在 Headers 中添加 `Authorization: token ...` | 构造时传入 Token，自动为每个请求注入 Auth Header |
| **数据处理** | 需要手动调用 `resp.json()` 解析响应，手动 `json.dumps()` 请求体 | **全自动**。输入字典，返回字典 |
| **错误处理** | 返回 HTTP 状态码 (200, 404)，需要手动判断 | **抛出语义化异常** (如 `GitHubBroken`, `BadRequest`, `RateLimitExceeded`) |

---

## 2. 代码对比：获取当前用户信息

通过对比代码，你可以清晰地看到 Gidgethub 帮你省去了哪些“脏活累活”。

### 方式 A：使用普通 `aiohttp` (原生写法)

你需要自己处理 Header、URL 拼接、JSON 解析和错误检查。

```python
import aiohttp
import asyncio

async def use_pure_aiohttp():
    token = "YOUR_GITHUB_TOKEN"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json", # GitHub 推荐的 Header
        "User-Agent": "my-app" # GitHub 强制要求 User-Agent
    }
    
    async with aiohttp.ClientSession() as session:
        # 1. 必须写完整的 URL
        async with session.get("https://api.github.com/user", headers=headers) as resp:
            # 2. 必须手动检查状态码
            if resp.status != 200:
                print(f"Error: {resp.status}")
                return
            
            # 3. 必须手动解析 JSON
            data = await resp.json()
            print(f"User: {data['login']}")
```

### 方式 B：使用 `gidgethub`

Gidgethub 包装了 `aiohttp` session，帮你处理了所有 GitHub 特有的协议细节。

```python
import aiohttp
import asyncio
from gidgethub.aiohttp import GitHubAPI

async def use_gidgethub():
    token = "YOUR_GITHUB_TOKEN"
    
    async with aiohttp.ClientSession() as session:
        # 1. 初始化时传入 session
        gh = GitHubAPI(session, "my-app", oauth_token=token)
        
        # 2. 直接请求路径，自动处理 Auth 和 JSON
        # 如果出错（如 401/404），它会直接抛出 Python 异常，而不是静默失败
        data = await gh.getitem("/user")
        print(f"User: {data['login']}")
```

---

## 3. Gidgethub 的“黑魔法” (它到底多做了什么？)

当你调用 `gh.getitem("/user")` 时，`gidgethub` 在内部执行了以下流程：

1.  **请求构建**：
    *   自动拼接基地址 `https://api.github.com`。
    *   自动添加 `Authorization` 和 `User-Agent` 头。
    *   自动设置 `Accept` 头以适配 GitHub API 版本。
2.  **调用底层**：
    *   调用你传入的 `aiohttp.ClientSession.request()` 发送数据。
3.  **响应处理 (关键)**：
    *   **速率限制 (Rate Limit)**：自动读取响应头中的 `X-RateLimit-Remaining` 和 `X-RateLimit-Reset`，并更新内部状态。如果次数用尽，抛出 `RateLimitExceeded` 异常并告诉你还要等多久。
    *   **异常转换**：
        *   400 -> `gidgethub.BadRequest`
        *   401 -> `gidgethub.InvalidAuthentication` (这就知道是 Token 错了)
        *   422 -> `gidgethub.ValidationFailure` (提交的数据格式不对)
    *   **JSON 解包**：直接返回 Python 字典或列表。

## 4. 常见误区澄清

**Q: `GitHubAPI` 就是 `gidgethub.aiohttp` 的全部吗？**

**A: 是的，可以这么理解。**

`GitHubAPI` 是 `gidgethub.aiohttp` 模块暴露给用户的**核心且唯一的入口类**。
当你 `from gidgethub.aiohttp import GitHubAPI` 时，你已经拿到了该模块 99% 的功能。

*   `gidgethub.aiohttp` 是一个**模块 (Module)**。
*   `GitHubAPI` 是这个模块里定义的**类 (Class)**。

这个类的源码逻辑非常简单：它继承自 `gidgethub` 的抽象基类，并实现了 `_request` 方法（负责调用 `aiohttp` 发送请求）。掌握了 `GitHubAPI` 类，你就掌握了该模块的全部。

## 5. 总结

*   **如果你在写爬虫**，爬取任意网站 -> 用普通的 `aiohttp`。
*   **如果你在写 GitHub App / 工具** -> 请务必用 `gidgethub`。它不是为了取代 `aiohttp`，而是为了让你在 `aiohttp` 上更舒服地操作 GitHub API。

