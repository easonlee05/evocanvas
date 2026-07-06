from app.api.server import create_app
from starlette.staticfiles import StaticFiles
import uvicorn


api_app = create_app()
static_app = StaticFiles(directory="frontend/dist", html=True)


async def app(scope, receive, send):
    path = scope.get("path", "")
    target = api_app if path.startswith("/api") else static_app
    await target(scope, receive, send)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
