import uvicorn

from app.config import get_settings

settings = get_settings()

uvicorn.run("app.main:app", host="127.0.0.1", port=settings.api_port)
