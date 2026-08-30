#!/usr/bin/env python3
"""
Этап 1: гость → 3 бесплатных → расклад Таро → осталось 2.

Запуск из корня max_bot (нужен .env с APP_DB_* и API_KEY):

  python scripts/test_app_stage1.py
  python scripts/test_app_stage1.py --skip-llm   # без вызова DeepSeek
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import (  # noqa: E402
    AppDatabase,
    FREE_DIVINATIONS_START,
    create_guest,
    get_user_balance,
    save_divination,
    use_divination,
)
from app.divination_service import run_tarot  # noqa: E402


async def main(skip_llm: bool) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    user_id = await create_guest(install_id="stage1-test")
    balance = await get_user_balance(user_id)
    assert balance is not None
    free_before = balance["free_divinations_remaining"]
    print(f"✓ Гость {user_id}, бесплатных: {free_before}")
    assert free_before == FREE_DIVINATIONS_START, f"Ожидалось {FREE_DIVINATIONS_START}"

    question = "Что меня ждёт в ближайший месяц?"

    if skip_llm:
        card_ids = ["00-TheFool", "16-TheTower", "Cups01"]
        used = await use_divination(user_id)
        assert used
        div_id = await save_divination(
            user_id,
            divination_type="Таро",
            question=question,
            selected_cards=card_ids,
            interpretation="<b>Тест</b> без LLM",
            is_free=True,
        )
        assert div_id
        print(f"✓ Расклад сохранён id={div_id} (без LLM)")
    else:
        result = await run_tarot(
            user_id,
            question,
            card_ids=["00-TheFool", "16-TheTower", "Cups01"],
        )
        print(f"✓ Расклад id={result.divination_id}, карты: {result.card_ids}")
        print(f"  Толкование (начало): {result.interpretation[:120]}...")

    balance_after = await get_user_balance(user_id)
    assert balance_after is not None
    free_after = balance_after["free_divinations_remaining"]
    print(f"✓ Бесплатных после расклада: {free_after}")
    assert free_after == free_before - 1, f"Ожидалось {free_before - 1}, получено {free_after}"

    await AppDatabase.close_pool()
    print("✅ Этап 1 пройден")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Проверить только БД, без вызова DeepSeek",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(skip_llm=args.skip_llm)))
