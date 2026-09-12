
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .db import init_db
from .models import ErrorResponse
from .routes import router
from .routes_auth import auth_router, keys_router

app = FastAPI(title="BrowserMesh control plane", version="2.0")


@app.on_event("startup")
def _startup() -> None:
    """Create the SQLite tables for users/keys if they don't exist yet."""
    init_db()

# Allow the dashboard (different origin) to call this API in local dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Return a structured ErrorResponse body for any HTTP error."""
    body = ErrorResponse(error="http_error", detail=str(exc.detail)).model_dump()
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Return a structured ErrorResponse for invalid request payloads."""
    body = ErrorResponse(error="validation_error", detail=str(exc.errors())).model_dump()
    return JSONResponse(status_code=422, content=body)


app.include_router(router)
app.include_router(auth_router)
app.include_router(keys_router)
