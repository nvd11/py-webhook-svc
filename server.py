import src.configs.config

from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

app = FastAPI(root_path="/webhook")


@app.get("/")
def read_root():
    logger.info("Root endpoint accessed!")
    return {"message": "Hello, webhook service!"}

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
