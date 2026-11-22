from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from database import init_db, get_connection
from seed import seed
from routes import (
    auth,
    clients,
    collections,
    dashboard,
    employees,
    payments,
    reports,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Render's free plan wipes the SQLite file on restart, so if there are no
    # users yet, create the demo dealer/employees automatically.
    conn = get_connection()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    if user_count == 0:
        seed()
    yield


app = FastAPI(
    title="DueTrack API",
    description="Payment Collection Management System API in Python (FastAPI)",
    version="1.0.0",
    lifespan=lifespan,
)

client_origin = os.environ.get("CLIENT_ORIGIN", "http://localhost:5173")
origins = [
    client_origin,
    "https://duetrack-app-2026.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": str(exc.detail), "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {}
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err["loc"] if loc != "body")
        errors[field] = err["msg"]
    first_msg = exc.errors()[0]["msg"] if exc.errors() else "Validation error"
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": first_msg, "errors": errors, "detail": exc.errors()},
    )


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(employees.router)
app.include_router(collections.router)
app.include_router(payments.router)
app.include_router(dashboard.router)
app.include_router(reports.router)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)