from fastapi import FastAPI

from app.api.auth import router as auth_router

app = FastAPI(title="YouTude", description="YouTube clone: FastAPI + PostgreSQL + SQLAlchemy (async) + S3")

app.include_router(auth_router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "youtude-api"}