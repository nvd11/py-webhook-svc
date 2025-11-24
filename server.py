import os

import aiohttp
from gidgethub.aiohttp import GitHubAPI
from src.services.gh_service import GithubService
import src.configs.config

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
from gidgethub import routing, sansio

app = FastAPI(root_path="/webhook")
router = routing.Router()

gh_token = os.getenv("GITHUB_TOKEN")
@app.get("/")
def read_root():
    logger.debug("Root endpoint accessed!")
    return {"message": "Hello, webhook service from Helm Chart2!"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}

@app.get("/getcallinfo")
def endpoint1(request: Request):
    client_ip = getattr(request, "client", None)
    client_ip = client_ip.host if client_ip else None
    headers = dict(request.headers)
    return {
        "endpoint": "webhook/getcallinfo",
        "client_ip": client_ip,
        "host": headers.get("host"),
        "method": request.method,
        "path": request.url.path,
        "query": request.url.query,
        "headers": headers,
    }

def process_and_log_webhook(headers: dict, body: dict):
    """This function runs in the background to process the webhook data."""
    logger.info("--- Background webhook processing started ---")
    
    # Get and log the X-GitHub-Event header
    github_event = headers.get("x-github-event")
    if github_event:
        logger.info(f"GitHub Event: {github_event}")
    else:
        logger.info("X-GitHub-Event header not found.")
        
    logger.info(f"Received full headers: {headers}")
    logger.info(f"Received webhook payload: {body}")
    logger.info("--- Background webhook processing finished ---")

@app.post("/webhook-test")
async def webhook_test(request: Request, background_tasks: BackgroundTasks, response: Response):
    """
    An endpoint to test webhooks. It immediately returns a 202 Accepted response
    and processes the webhook payload in the background.
    """
    logger.info("Webhook test endpoint called. Acknowledging request immediately.")
    
    headers = dict(request.headers)
    try:
        body = await request.json()
    except Exception as e:
        logger.warning(f"Could not parse request body as JSON: {e}")
        body = {"error": "Request body is not valid JSON."}

    # Add the processing to background tasks
    background_tasks.add_task(process_and_log_webhook, headers, body)
    
    response.status_code = 202
    return {"status": "Accepted"}



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


@router.register("pull_request", action="opened")
async def pull_request_opened_event(event, gh, *args, **kwargs):
    """
    当一个新的 Pull Request 被创建时触发
    """
    pr_info = event.data["pull_request"]
    pr_number = pr_info["number"]
    pr_title = pr_info["title"]
    author = pr_info["user"]["login"]
    
    # 获取仓库信息
    repo_info = event.data["repository"]
    repo_owner = repo_info["owner"]["login"]
    repo_name = repo_info["name"]
    
    logger.info(f"New Pull Request #{pr_number} opened by @{author} in {repo_owner}/{repo_name}: '{pr_title}'")
    
    # 在这里你可以添加自动化逻辑，例如:
    # 1. 检查 PR 标题是否符合规范
    # 2. 自动给 PR 添加标签 (label)
    # 3. 自动指派审查者 (assign reviewer)
    # 4. 在 PR 下发表一条欢迎评论
    
    # 示例：发表一条欢迎评论
    comments_url = pr_info["comments_url"]
    welcome_message = f"Thanks for opening this PR, @{author}! We will review it soon."
    
    gh_service = GithubService(gh)
    comment_result= await gh_service.post_general_pr_comment(owner=repo_owner, repo_name=repo_name, pr_number=pr_number, comment_body=welcome_message)
    logger.info(f"Comment result: {comment_result}")


async def process_webhook_event(event: sansio.Event):
    """
    此函数在后台运行以处理 Webhook 事件。
    """
    logger.info(f"--- 后台事件处理开始: {event.event} ---")
    
    # 初始化 GitHubAPI 客户端
    # 注意：实际生产中通常需要根据 event.data['installation']['id'] 获取对应的 Installation Token
    # 这里为了演示简化，直接使用环境变量中的 PAT

    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "my-bot", oauth_token=gh_token)
        
        try:
            # 将事件分发给对应的处理器
            await router.dispatch(event, gh)
            logger.info(f"--- 后台事件处理完成: {event.event} ---")
        except Exception as e:
            logger.error(f"处理事件 {event.event} 时出错: {e}")


@app.post("/")
@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """
    FastAPI 的入口端点，接收、验证并后台处理 Webhook。
    """
    # 1. 读取 Headers 和 Body
    body = await request.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    
    try:
        # 2. 构建 Event 对象 (会自动验证签名)
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        logger.info(f"Webhook 事件已接收: {event.event}")
        
        # 3. 将事件处理逻辑添加到后台任务
        background_tasks.add_task(process_webhook_event, event)
        
        # 4. 立即返回 202 Accepted 响应
        return Response(status_code=202)

    except Exception as e:
        logger.error(f"处理 webhook 请求时出错: {e}")
        raise HTTPException(status_code=400, detail="无效的 webhook 请求")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
