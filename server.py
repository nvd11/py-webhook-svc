import src.configs.config

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

app = FastAPI(root_path="/webhook")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
