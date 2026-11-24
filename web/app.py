from contextlib import asynccontextmanager
import logging
import re
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from core.database import init_db, get_engine
from web.routes import api_router, public_router, proxy_game_asset, close_asset_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database is migrated on dashboard start
    engine = get_engine()
    await init_db(engine)

    # Initialize bot_context APIs if not already set by main.py
    from bot.handlers import bot_context
    if bot_context.db_engine is None:
        bot_context.db_engine = engine
    if bot_context.player_api is None:
        try:
            from core.database import get_session
            from core.models import Account, SessionData
            from sqlalchemy import select
            from client.auth_provider import AuthProvider
            from client.http_client import GameHttpClient
            from client.api.player import PlayerAPI
            from client.api.boss import BossAPI
            from client.api.prison import PrisonAPI
            from client.api.social import SocialAPI
            from workers.boss_worker import BossWorker
            from workers.prison_worker import PrisonWorker

            async with get_session(engine) as session:
                stmt = select(Account).order_by(Account.id.asc()).limit(1)
                acc = (await session.execute(stmt)).scalar_one_or_none()
                if not acc:
                    acc = Account(phone="+70000000000", is_active=True)
                    session.add(acc)
                    await session.flush()
                    session.add(SessionData(account_id=acc.id))
                    await session.commit()
                acc_id = acc.id

            auth_provider = AuthProvider(account_id=acc_id, db_engine=engine)
            http_client = GameHttpClient(auth_provider=auth_provider)
            player_api = PlayerAPI(http_client=http_client)
            boss_api = BossAPI(http_client=http_client)
            prison_api = PrisonAPI(http_client=http_client)
            social_api = SocialAPI(http_client=http_client)

            bot_context.player_api = player_api
            bot_context.boss_api = boss_api
            bot_context.prison_api = prison_api
            bot_context.social_api = social_api
            bot_context.boss_worker = BossWorker(account_id=acc_id, boss_api=boss_api, db_engine=engine)
            bot_context.prison_worker = PrisonWorker(account_id=acc_id, prison_api=prison_api, player_api=player_api, db_engine=engine)
            from workers.social_worker import SocialWorker
            bot_context.social_worker = SocialWorker(account_id=acc_id, social_api=social_api, db_engine=engine)
        except Exception as e:
            logger.warning("Could not auto-initialize bot_context in web dashboard: %s", e)

    yield


def create_app() -> FastAPI:
    """Создает и настраивает FastAPI приложение PrisonBot Dashboard."""
    app = FastAPI(
        title="PrisonBot Web Dashboard",
        version="2.0.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    # GZip compression (70-85% reduction for JSON/JS/CSS)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Cache-Control headers: public for /static/assets/*, no-cache for HTML/JS/CSS
    @app.middleware("http")
    async def add_cache_control_headers(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/assets/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        elif path == "/" or path.endswith((".html", ".js", ".css")) or (path.startswith("/static/") and not path.startswith("/static/assets/")):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    # REST API
    app.include_router(public_router)
    app.include_router(api_router)

    # Direct fallback for /assets/... requests from browser
    @app.get("/assets/{rest_path:path}")
    async def root_assets_proxy(rest_path: str):
        return await proxy_game_asset(path=f"assets/{rest_path}")

    # Static files directory
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)

    # Dynamic index.html route with auto-versioning (?v=<mtime>)
    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        index_file = static_dir / "index.html"
        if not index_file.exists():
            return HTMLResponse("Not found", status_code=404)
        content = index_file.read_text(encoding="utf-8")
        styles_file = static_dir / "styles.css"
        app_file = static_dir / "app.js"
        mtimes = [index_file.stat().st_mtime]
        if styles_file.exists():
            mtimes.append(styles_file.stat().st_mtime)
        if app_file.exists():
            mtimes.append(app_file.stat().st_mtime)
        v_tag = str(int(max(mtimes)))

        content = re.sub(r'styles\.css(?:\?v=[^"\'\s>]+)?', f'styles.css?v={v_tag}', content)
        content = re.sub(r'app\.js(?:\?v=[^"\'\s>]+)?', f'app.js?v={v_tag}', content)
        return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, must-revalidate"})

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static_assets")
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static_root")

    return app


app = create_app()
