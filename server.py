import os

import aiohttp
from gidgethub.aiohttp import GitHubAPI
from src.services.gh_service import GithubService
import src.configs.config

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
from gidgethub import routing, sansio
from src.services.gh_service import create_installation_access_token

app = FastAPI(root_path="/webhook")
router = routing.Router()

# 读取 GitHub App 配置
app_id_str = os.getenv("GITHUB_APP_ID")
# Convert from scientific notation string if necessary
APP_ID = int(float(app_id_str)) if app_id_str else None
PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH")
GITHUB_API_BASE_URL = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com")
PRIVATE_KEY = None

if PRIVATE_KEY_PATH:
    try:
        with open(PRIVATE_KEY_PATH, "r") as f:
            PRIVATE_KEY = f.read()
        logger.info("GitHub App Private Key successfully loaded from path.")
    except Exception as e:
        logger.error(f"无法读取 Private Key: {e}")
else:
    logger.warning("GITHUB_PRIVATE_KEY_PATH is not set. App authentication will fail.")

logger.info(f"GitHub App ID loaded: {APP_ID}")

@app.get("/")
def read_root():
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
    logger.info("--- Background webhook processing started ---")
    
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
    logger.info("Webhook test endpoint called. Acknowledging request immediately.")
    
    headers = dict(request.headers)
    try:
        body = await request.json()
    except Exception as e:
        logger.warning(f"Could not parse request body as JSON: {e}")
        body = {"error": "Request body is not valid JSON."}

    background_tasks.add_task(process_and_log_webhook, headers, body)
    
    response.status_code = 202
    return {"status": "Accepted"}

@router.register("issue_comment", action="created")
async def issue_comment_event(event, gh, *args, **kwargs):
    url = event.data["issue"]["comments_url"]
    author = event.data["comment"]["user"]["login"]
    message = f"Hello @{author}, thanks for the comment!"
    await gh.post(url, data={"body": message})
    print(f"Replied to {author}")


@router.register("pull_request", action="opened")
async def pull_request_opened_event(event, gh, *args, **kwargs):
    pr_info = event.data["pull_request"]
    pr_number = pr_info["number"]
    pr_title = pr_info["title"]
    author = pr_info["user"]["login"]
    
    repo_info = event.data["repository"]
    repo_owner = repo_info["owner"]["login"]
    repo_name = repo_info["name"]
    
    logger.info(f"New Pull Request #{pr_number} opened by @{author} in {repo_owner}/{repo_name}: '{pr_title}'")
    
    welcome_message = f"Thanks for opening this PR, @{author}! We will review it soon."
    
    gh_service = GithubService(gh)
    comment_result= await gh_service.post_general_pr_comment(owner=repo_owner, repo_name=repo_name, pr_number=pr_number, comment_body=welcome_message)
    logger.info(f"Comment result: {comment_result}")


async def process_webhook_event(event: sansio.Event):
    logger.info(f"--- 后台事件处理开始: {event.event} ---")
    
    if not APP_ID or not PRIVATE_KEY:
        logger.error("App ID or Private Key is not configured. Cannot process event.")
        return
        
    try:
        installation_id = event.data.get("installation", {}).get("id")
        if not installation_id:
            logger.error(f"事件 {event.event} 中未找到 installation id，无法进行认证")
            return

        token = await create_installation_access_token(
            app_id=APP_ID,
            private_key=PRIVATE_KEY,
            installation_id=installation_id,
            base_url=GITHUB_API_BASE_URL
        )
        if not token:
            return

        async with aiohttp.ClientSession() as session:
            gh = GitHubAPI(session, "my-bot", oauth_token=token, base_url=GITHUB_API_BASE_URL)
            
            await router.dispatch(event, gh)
            logger.info(f"--- 后台事件处理完成: {event.event} ---")
            
    except Exception as e:
        logger.error(f"处理事件 {event.event} 时出错: {e}")


@app.post("/")
@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    
    try:
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        logger.info(f"Webhook 事件已接收: {event.event}")
        background_tasks.add_task(process_webhook_event, event)
        return Response(status_code=202)
    except Exception as e:
        logger.error(f"处理 webhook 请求时出错: {e}")
        raise HTTPException(status_code=400, detail="无效的 webhook 请求")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
