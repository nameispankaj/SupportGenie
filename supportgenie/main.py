from fastapi import FastAPI

from supportgenie.api.routes import router
from supportgenie.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(router)
