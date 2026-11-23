from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.video import router as video_router
from app.api.reaction import router as reaction_router
from app.api.comment import router as comment_router

app = FastAPI(title="YouTude", description="YouTube clone: FastAPI + PostgreSQL + SQLAlchemy (async) + S3")

app.include_router(auth_router)
app.include_router(video_router)
app.include_router(reaction_router)
app.include_router(comment_router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "youtude-api"}