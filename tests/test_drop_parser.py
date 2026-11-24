import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
from sqlalchemy import select

from core.database import get_engine, init_db, get_session
from core.models import Account, Notification
from core.drop_parser import DropParser


@pytest_asyncio.fixture
async def drop_setup():
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    async with get_session(engine) as session:
        acc = Account(phone="+79990001122", nickname="DropHero")
        session.add(acc)
        await session.flush()
        acc_id = acc.id
    yield engine, acc_id
    await engine.dispose()


def test_parse_boss_claim_rewards_and_tattoo():
    """Проверка парсинга победы над боссом с валютами (Авторитет, Сигареты, Ключи) и сетом тату."""
    raw_payload = {
        "success": True,
        "reward": [
            {"type": "authority", "amount": 1000},
            {"type": "cigarettes", "amount": 500},
        ],
        "keys": 2,
        "soloSetReward": {
            "title": 'Комплект "Биомеханика"',
            "tattoo": "Самопал +1",
            "owned": 7,
            "total": 20,
        },
    }

    parsed = DropParser.parse_boss_claim(raw_payload, boss_name="Воркута", mode="pacansky")

    assert parsed["category"] == "bosses"
    assert "Воркута" in parsed["title"]
    assert "Пацанский" in parsed["title"]

    currencies = {r["label"]: r["amount"] for r in parsed["rewards"]}
    assert currencies.get("Авторитет") == 1000
    assert currencies.get("Сигареты") == 500
    assert currencies.get("Ключи") == 2

    assert len(parsed["drops"]) == 1
    assert parsed["drops"][0]["kind"] == "tattoo"
    assert parsed["drops"][0]["title"] == 'Комплект "Биомеханика"'
    assert "7/20" in parsed["drops"][0]["subtitle"]


def test_parse_prison_work_stash():
    """Проверка парсинга ходки в тюрьме с выпадением нычки."""
    raw_payload = {
        "success": True,
        "rewardCigarettes": 2,
        "rewardAuthority": 1,
        "stash": True,
    }

    parsed = DropParser.parse_prison_work(raw_payload, prison_name="Бутырка", works_count=1)

    assert parsed["category"] == "prisons"
    assert "Бутырка" in parsed["title"]

    currencies = {r["label"]: r["amount"] for r in parsed["rewards"]}
    assert currencies.get("Сигареты") == 2
    assert currencies.get("Авторитет") == 1

    assert any(d["kind"] == "stash" and d["title"] == "Нычка" for d in parsed["drops"])


@pytest.mark.asyncio
async def test_save_notification_in_db(drop_setup):
    """Проверка сохранения уведомления в таблицу notifications с категорией и is_read=False."""
    engine, acc_id = drop_setup

    data = {
        "category": "bosses",
        "title": "Победа над Сизым",
        "subtitle": "Босс повержен",
        "rewards": [{"currency": "authority", "label": "Авторитет", "amount": 500}],
        "drops": [{"kind": "stash", "title": "Нычка", "subtitle": "Выпала нычка"}],
    }

    notif = await DropParser.save_notification(account_id=acc_id, parsed_data=data, db_engine=engine)

    assert notif.id is not None
    assert notif.category == "bosses"
    assert notif.is_read is False

    async with get_session(engine) as session:
        stmt = select(Notification).where(Notification.id == notif.id)
        saved = (await session.execute(stmt)).scalar_one()
        assert saved.title == "Победа над Сизым"
        assert saved.is_read is False
        assert len(saved.rewards) == 1
        assert len(saved.drops) == 1


def test_parse_boss_defeat_and_prison_day_stage_meta():
    """Проверка parse_boss_defeat (HP прогресс) и parse_prison_work с этапом и кликами."""
    defeat = DropParser.parse_boss_defeat(boss_name="Махно", mode="blotnoy", remaining_hp=3200, max_hp=10000)
    assert defeat["category"] == "bosses"
    assert "Махно" in defeat["title"]
    assert defeat["meta_json"]["type"] == "boss_defeat"
    assert defeat["meta_json"]["outcome"] == "defeat"
    assert defeat["meta_json"]["remaining_hp"] == 3200
    assert defeat["meta_json"]["max_hp"] == 10000

    p_work = DropParser.parse_prison_work(
        {"rewardCigarettes": 15, "respect": 20},
        prison_name="Кресты",
        works_count=1,
        is_day=True,
        stage_num=5,
        prison_id=4,
    )
    assert p_work["title"] == "Кресты: День 5"
    assert p_work["subtitle"] == "Кликов: 1"
    assert p_work["meta_json"]["clicks"] == 1
    assert any(r["currency"] == "respect" and r["amount"] == 20 for r in p_work["rewards"])
