"""FastAPI application entry point."""

from fastapi import FastAPI

from newsflow.api.telegram import router as telegram_router

app = FastAPI(title="NEWSFLOW Content Studio", version="0.1.0")
app.include_router(telegram_router)


@app.get("/healthz", tags=["system"])
def healthz() -> dict[str, str]:
    """Liveness endpoint used by local and production orchestration."""
    return {"service": "newsflow-api", "status": "ok"}
