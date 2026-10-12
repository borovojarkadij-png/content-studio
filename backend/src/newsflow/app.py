"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from newsflow.api.editorial_policy import router as editorial_policy_router
from newsflow.api.illustration_review import router as illustration_review_router
from newsflow.api.settings import router as settings_router
from newsflow.api.studio import router as studio_router
from newsflow.api.telegram import router as telegram_router

app = FastAPI(title="NEWSFLOW Content Studio", version="0.1.0")
app.include_router(telegram_router)
app.include_router(settings_router)
app.include_router(studio_router)
app.include_router(illustration_review_router)
app.include_router(editorial_policy_router)


@app.middleware("http")
async def private_editorial_policy_responses(request: Request, call_next):
    if request.url.path not in (
        "/api/settings/editorial-policy",
        "/api/settings/editorial-policy/",
    ):
        return await call_next(request)
    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001 - exact-route privacy boundary for unexpected failures
        return JSONResponse(
            status_code=500,
            content={"detail": "Editorial policy operation unavailable"},
            headers={"Cache-Control": "no-store"},
        )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def redact_rewrite_provider_validation_error(request: Request, exc: RequestValidationError):
    """Keep credentials out of FastAPI's otherwise helpful validation detail."""
    if request.url.path in ("/api/settings/editorial-policy", "/api/settings/editorial-policy/"):
        return JSONResponse(status_code=422, content={"detail": "Invalid editorial policy request"})
    if request.url.path.startswith(
        ("/api/settings/rewrite-providers/", "/api/illustration-review/")
    ):
        detail = [
            {key: value for key, value in error.items() if key != "input"} for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})
    return await request_validation_exception_handler(request, exc)


@app.get("/healthz", tags=["system"])
def healthz() -> dict[str, str]:
    """Liveness endpoint used by local and production orchestration."""
    return {"service": "newsflow-api", "status": "ok"}
