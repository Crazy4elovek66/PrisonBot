import sys
import time
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
import httpx
from sqlalchemy import select
from core.database import get_engine, init_db, get_session
from core.models import Account, SessionData
from client.auth_provider import AuthProvider
from telegram.webview import WebViewExtractor


class MockWebViewExtractor(WebViewExtractor):
    def __init__(self, init_data: str = "query_id=mock_init_data"):
        self.init_data = init_data
        self.call_count = 0

    async def fetch_fresh_init_data(self, session_path=None) -> str:
        self.call_count += 1
        return self.init_data


@pytest_asyncio.fixture
async def test_db():
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    async with get_session(engine) as session:
        acc = Account(phone="+79991112233", nickname="TestHero")
        session.add(acc)
        await session.flush()
        sess = SessionData(
            account_id=acc.id,
            access_token="valid_jwt_token",
            refresh_token="valid_refresh_token",
            access_exp=int(time.time() + 3600),  # годен 1 час
        )
        session.add(sess)
        acc_id = acc.id
    return engine, acc_id


@pytest.mark.asyncio
async def test_auth_provider_returns_cached_token(test_db):
    """1. Возврат кэшированного access_token, если accessExp еще не истек."""
    engine, acc_id = test_db
    provider = AuthProvider(account_id=acc_id, db_engine=engine)

    token = await provider.get_valid_token()
    assert token == "valid_jwt_token"


@pytest.mark.asyncio
async def test_auth_provider_auto_refresh_on_expire(test_db):
    """2. Автоматический вызов refresh-эндпоинта при истечении accessExp и сохранение в SQLite."""
    engine, acc_id = test_db

    # Делаем токен истекшим
    async with get_session(engine) as session:
        stmt = select(SessionData).where(SessionData.account_id == acc_id)
        res = await session.execute(stmt)
        sess = res.scalar_one()
        sess.access_exp = int(time.time() - 100)

    refresh_called = 0

    def mock_handler(request: httpx.Request):
        nonlocal refresh_called
        if request.url.path == "/api/auth/refresh":
            refresh_called += 1
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "accessToken": "brand_new_access_token",
                    "refreshToken": "brand_new_refresh_token",
                    "accessExp": int(time.time() + 7200),
                },
            )
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)

    token = await provider.get_valid_token()
    assert token == "brand_new_access_token"
    assert refresh_called == 1

    # Проверяем запись в SQLite
    async with get_session(engine) as session:
        stmt = select(SessionData).where(SessionData.account_id == acc_id)
        res = await session.execute(stmt)
        sess = res.scalar_one()
        assert sess.access_token == "brand_new_access_token"
        assert sess.refresh_token == "brand_new_refresh_token"


@pytest.mark.asyncio
async def test_auth_provider_fallback_to_telethon_on_refresh_401(test_db):
    """3. Fallback на мок WebViewExtractor + POST /api/auth/login, если refresh вернул 401."""
    engine, acc_id = test_db

    # Делаем токен истекшим
    async with get_session(engine) as session:
        stmt = select(SessionData).where(SessionData.account_id == acc_id)
        res = await session.execute(stmt)
        sess = res.scalar_one()
        sess.access_exp = int(time.time() - 100)

    login_called = 0

    def mock_handler(request: httpx.Request):
        nonlocal login_called
        if request.url.path == "/api/auth/refresh":
            return httpx.Response(401, json={"success": False, "message": "session_expired"})
        if request.url.path == "/api/auth/login":
            login_called += 1
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "userId": 9000000000466709,
                    "nickname": "FallbackHero",
                    "accessToken": "relogin_access_token",
                    "refreshToken": "relogin_refresh_token",
                    "accessExp": int(time.time() + 7200),
                },
            )
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    mock_extractor = MockWebViewExtractor("query_id=test_fresh_init_data")
    provider = AuthProvider(
        account_id=acc_id,
        http_client=mock_client,
        webview_extractor=mock_extractor,
        db_engine=engine,
    )

    token = await provider.get_valid_token()
    assert token == "relogin_access_token"
    assert mock_extractor.call_count == 1
    assert login_called == 1

    # Проверяем обновление профиля и сессии в БД
    async with get_session(engine) as session:
        stmt = select(SessionData).where(SessionData.account_id == acc_id)
        res = await session.execute(stmt)
        sess = res.scalar_one()
        assert sess.access_token == "relogin_access_token"
        assert sess.init_data == "query_id=test_fresh_init_data"

        acc_stmt = select(Account).where(Account.id == acc_id)
        acc = (await session.execute(acc_stmt)).scalar_one()
        assert acc.nickname == "FallbackHero"
        assert acc.game_user_id == 9000000000466709


@pytest.mark.asyncio
async def test_auth_provider_concurrency_lock(test_db):
    """4. Проверка работы asyncio.Lock при конкурентном вызове get_valid_token() из 5 корутин."""
    engine, acc_id = test_db

    # Делаем токен истекшим
    async with get_session(engine) as session:
        stmt = select(SessionData).where(SessionData.account_id == acc_id)
        res = await session.execute(stmt)
        sess = res.scalar_one()
        sess.access_exp = int(time.time() - 100)

    refresh_counter = 0

    def mock_handler(request: httpx.Request):
        nonlocal refresh_counter
        if request.url.path == "/api/auth/refresh":
            refresh_counter += 1
            # Небольшая задержка для имитации сетевого запроса
            time.sleep(0.05)
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "accessToken": "concurrent_access_token",
                    "refreshToken": "concurrent_refresh_token",
                    "accessExp": int(time.time() + 3600),
                },
            )
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler), base_url="https://test.local")
    provider = AuthProvider(account_id=acc_id, http_client=mock_client, db_engine=engine)

    # Запускаем 5 одновременных задач
    tasks = [provider.get_valid_token() for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # Все задачи должны получить один и тот же новый токен
    assert all(r == "concurrent_access_token" for r in results)
    # Но запрос на сервер должен был уйти строго 1 раз!
    assert refresh_counter == 1
