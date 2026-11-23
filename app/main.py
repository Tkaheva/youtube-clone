from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.api.auth import router as auth_router
from app.api.video import router as video_router
from app.api.reaction import router as reaction_router
from app.api.comment import router as comment_router
from app.api.subscription import router as subscription_router
from app.api.moderation import router as moderation_router

app = FastAPI(title="YouTude", description="YouTube clone: FastAPI + PostgreSQL + SQLAlchemy (async) + S3")

# Подключаем API-роутеры
app.include_router(auth_router)
app.include_router(video_router)
app.include_router(reaction_router)
app.include_router(comment_router)
app.include_router(subscription_router)
app.include_router(moderation_router)

# Раздача статических файлов (фронтенд)
# Папка static должна лежать в корне проекта рядом с папкой app
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "youtude-api"}

@app.get("/", include_in_schema=False)
async def root():
    # При заходе на главную страницу автоматически открываем наш фронтенд
    return RedirectResponse(url="/static/index.html")