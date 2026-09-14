import uvicorn

from src.app import create_app
from src.config import get_settings


settings = get_settings()
app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=True,
    )
