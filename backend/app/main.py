from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import activity, blocklist, config
from .api.routes import router
from .db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .providers import shutdown as providers_shutdown
    from .services import scheduler

    init_db()
    from .services import accounts

    accounts.ensure_legacy_account()
    n = blocklist.seed_if_empty()
    if n:
        activity.info("blocklist", f"Seeded blocklist with {n} starter brands/keywords")
    if app.state.start_scheduler:
        scheduler.start()
    yield
    scheduler.shutdown()
    providers_shutdown()


def create_app(start_scheduler: bool = True) -> FastAPI:
    app = FastAPI(title="Amazon → eBay Listing Automation", lifespan=lifespan)
    app.state.start_scheduler = start_scheduler
    app.include_router(router)

    dist = config.FRONTEND_DIST
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return HTMLResponse("Not found", 404)
        f = dist / path
        if path and f.is_file() and f.name != "index.html":
            return FileResponse(f)
        index = dist / "index.html"
        if index.exists():
            # Never cache the page shell, so an updated dashboard shows up right away.
            return FileResponse(index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
        return HTMLResponse("<h3>Dashboard not built yet.</h3><p>Run <code>npm install && npm run build</code> in "
                            "the <code>frontend</code> folder (the setup script does this).</p>")

    return app


app = create_app()
