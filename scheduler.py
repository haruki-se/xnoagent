"""
スケジューラー: x_agent.py を1日4〜8回自動実行する
実行方法: python scheduler.py
"""

import schedule
import time
import logging
import random
from x_agent import run_once

log = logging.getLogger(__name__)

# 1日の投稿時刻（JST）。必要に応じて変更してください
SCHEDULE_TIMES = [
    "07:30",  # 朝（通勤時間帯）
    "10:00",  # 午前
    "12:15",  # 昼休み
    "15:00",  # 午後
    "18:30",  # 退勤時間帯
    "21:00",  # 夜
]


def job():
    """ランダムな遅延（0〜5分）を加えて投稿（自然な間隔のため）"""
    delay = random.randint(0, 300)
    log.info(f"{delay}秒後に投稿します...")
    time.sleep(delay)
    run_once()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    for t in SCHEDULE_TIMES:
        schedule.every().day.at(t).do(job)
        log.info(f"スケジュール登録: {t}")

    log.info("スケジューラー起動。Ctrl+C で停止。")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
