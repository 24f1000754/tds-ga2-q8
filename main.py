
import os
import time
import json
import uuid
import threading
from datetime import datetime, timezone
from collections import deque

from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

START_TIME = time.monotonic()
EMAIL = os.getenv("EMAIL", "")

request_count = 0
counter_lock = threading.Lock()
log_lock = threading.Lock()
logs = deque(maxlen=1000)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    global request_count

    with counter_lock:
        request_count += 1

    request_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        response = await call_next(request)
    except Exception:
        response_status = 500
        with log_lock:
            logs.append({
                "level": "ERROR",
                "ts": timestamp,
                "path": request.url.path,
                "request_id": request_id,
            })
        raise

    with log_lock:
        logs.append({
            "level": "INFO",
            "ts": timestamp,
            "path": request.url.path,
            "request_id": request_id,
        })

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/work")
def work(n: int = Query(default=1, ge=0)):
    return {
        "email": EMAIL,
        "done": n
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    with counter_lock:
        count = request_count

    return (
        "# HELP http_requests_total Total HTTP requests\n"
        "# TYPE http_requests_total counter\n"
        f"http_requests_total {count}\n"
    )


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "uptime_s": max(0.0, time.monotonic() - START_TIME)
    }


@app.get("/logs/tail")
def logs_tail(limit: int = Query(default=10, ge=0, le=1000)):
    with log_lock:
        recent_logs = list(logs)[-limit:] if limit else []

    return recent_logs
