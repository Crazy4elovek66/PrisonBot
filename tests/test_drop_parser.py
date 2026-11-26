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
    assert currencies.get("Папиросы") == 500
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


def test_zero_loss_boss_claim_all_categories_and_prison_stash_no_try_on():
    payload = {
        "bossId": 39,
        "mode": "odin",
        "rewards": {
            "authority": 1500,
            "cigarettes": 800,
            "rubles": 25,
            "keys": 2,
            "bonusChips": 5,
            "collectionDrop": {"itemId": 7, "title": "Компас"},
            "hiddenItems": [{"id": 99, "name": "Телогрейка", "count": 1}],
            "tattoo": {"id": 12, "name": "Перстень", "set": "Блатной"},
            "clothing": {"id": 34, "name": "Кепка"},
            "room": {"id": 54, "name": "Торт Люськи"},
        },
    }
    parsed = DropParser.parse_boss_claim(payload, boss_name="Воркута", mode="odin")
    assert parsed["title"] == "Победа над боссом: Воркута (В одного)"
    kinds = {d["kind"] for d in parsed["drops"]}
    assert {"stash", "stashed_gear", "tattoo", "clothing", "room", "other"}.issubset(kinds)
    lines = "\n".join(DropParser.format_boss_rewards_lines(parsed))
    for expected in ("Авторитет", "Папиросы", "Рубли", "Ключи", "Компас", "Телогрейка", "Перстень", "Кепка", "Торт Люськи", "bonusChips"):
        assert expected in lines

    p_stash = DropParser.parse_prison_work(
        {
            "rewardCigarettes": 28,
            "collectionDrop": {"itemId": 7, "title": "Коллекция «Компас»", "imageUrl": "assets/PrisonV3/collections/4/1/7.webp"},
        },
        prison_name="КРЕСТЫ",
        works_count=1,
        is_day=True,
        stage_num=7,
        prison_id=4,
    )
    assert len(p_stash["drops"]) == 1
    assert p_stash["drops"][0]["kind"] == "stash"
    assert p_stash["drops"][0]["type"] == "stash"


def test_parse_boss_claim_nested_global_reward_and_damage_bonuses():
    """Парсинг реального контракта POST /api/boss/claim (rewards.globalReward, *ByDamage, stashGearReward)."""
    from core.drop_parser import DropParser

    claim_payload = {
        "success": True,
        "status": "claimed",
        "claimId": "01a214b5a76d782f92a508f666130076",
        "rewards": {
            "mode": "pacansky",
            "title": "Палыч",
            "bossId": 9,
            "result": "victory",
            "globalReward": {
                "keys": 1,
                "authority": 25,
                "currencies": [
                    {"type": "sugar", "amount": 25},
                    {"type": "cigarettes", "amount": "150"},
                ],
            },
            "rublesByDamage": 15,
            "authorityByDamage": 10,
            "bonusKeysByDamage": 1,
            "stashGearReward": {"id": 55, "name": "Заточка"},
        },
    }
    parsed = DropParser.parse_boss_claim(claim_payload, boss_name="Палыч", mode="pacansky")
    cur_map = {r["currency"]: r["amount"] for r in parsed["rewards"]}
    assert cur_map["keys"] == 2          # 1 + bonusKeysByDamage 1
    assert cur_map["authority"] == 35     # 25 + authorityByDamage 10
    assert cur_map["sugar"] == 25
    assert cur_map["cigarettes"] == 150
    assert cur_map["rubles"] == 15
    assert any("Заточка" in d["title"] for d in parsed["drops"])
    inline = DropParser.format_boss_rewards_inline(parsed)
    assert "Ключи +2" in inline
    assert "Авторитет +35" in inline
    assert "Сахар +25" in inline
    assert "Папиросы +150" in inline
    assert "Рубли +15" in inline
    assert "получены" not in inline
