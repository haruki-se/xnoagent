"""
X (Twitter) 就活情報 自動投稿エージェント
- 就活に関する有益情報をAIが自動生成し、X(Twitter)へ投稿する
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import os
import time
import random
import logging
from datetime import datetime
import anthropic
import tweepy
import feedparser
from dotenv import load_dotenv

# ── 設定読み込み ──────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

CLAUDE_API_KEY      = os.environ["CLAUDE_API_KEY"]
X_API_KEY           = os.environ["X_API_KEY"]
X_API_SECRET        = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN      = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_SECRET     = os.environ["X_ACCESS_SECRET"]
X_BEARER_TOKEN      = os.environ["X_BEARER_TOKEN"]

# ── ログ設定 ──────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "agent.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── 就活ニュース RSS フィード ─────────────────
RSS_FEEDS = [
    "https://news.yahoo.co.jp/rss/topics/business.xml",
    "https://news.yahoo.co.jp/rss/topics/economy.xml",
    "https://www3.nhk.or.jp/rss/news/cat6.xml",  # NHK 社会
]

# ── 就活トピック（ニュースがない場合のフォールバック） ──
FALLBACK_TOPICS = [
    "面接でよく聞かれる「自己PR」の作り方と答え方のコツ",
    "エントリーシートで差がつく「ガクチカ」の書き方",
    "就活の自己分析を深める方法：強みの見つけ方",
    "OB・OG訪問で絶対に聞くべき質問リスト",
    "グループディスカッションで評価されるための立ち回り",
    "就活スケジュール管理：3月解禁前にやるべきこと",
    "インターンシップを最大限に活かす方法",
    "業界研究の進め方：IR情報・決算資料の読み方入門",
    "就活メールのマナー：件名・本文・署名の書き方",
    "内定後のやること：内定承諾書・健康診断・入社準備",
    "SPI・適性検査の効率的な対策方法",
    "逆質問で好印象を与える質問の作り方",
    "志望動機をロジカルに組み立てる3ステップ",
    "就活うつにならないメンタルケア術",
    "外資系就活と日系就活の違いと対策",
    "就活に役立つ資格・スキルと優先度の考え方",
    "1dayインターンと長期インターン、どちらを選ぶべきか",
    "就活での服装・身だしなみの基本ルール",
    "面接の「最後に一言」で使えるフレーズ集",
    "就活サイト完全比較：マイナビ・リクナビ・OfferBox等",
]


def fetch_news() -> str | None:
    """RSSフィードから就活・ビジネス関連の最新ニュースを取得する"""
    items = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                items.append({"title": entry.title, "summary": getattr(entry, "summary", "")})
        except Exception as e:
            log.warning(f"RSS取得失敗 {url}: {e}")

    if not items:
        return None

    random.shuffle(items)
    picked = items[0]
    return f"タイトル: {picked['title']}\n概要: {picked['summary'][:200]}"


def generate_tweet(news_context: str | None) -> str:
    """Claude APIを使って就活に関するツイートを生成する"""
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    if news_context:
        user_prompt = f"""以下のニュースを参考に、就活生に役立つ情報をツイートしてください。

【参考ニュース】
{news_context}

ルール:
- 就活生の役に立つ内容にしてください
- 280文字以内（日本語）
- 改行を適度に使い読みやすく
- 末尾に関連ハッシュタグを2〜3個付ける（例: #就活 #面接対策 #22卒）
- 絵文字を1〜2個使って親しみやすく
- 宣伝っぽくならないよう自然な口調で
ツイート本文のみ出力してください。"""
    else:
        topic = random.choice(FALLBACK_TOPICS)
        user_prompt = f"""就活生に役立つ情報をツイートしてください。

【テーマ】{topic}

ルール:
- 就活生の役に立つ具体的なアドバイスを書く
- 280文字以内（日本語）
- 改行を適度に使い読みやすく
- 末尾に関連ハッシュタグを2〜3個付ける（例: #就活 #ES対策 #26卒）
- 絵文字を1〜2個使って親しみやすく
- 上から目線にならず、同じ目線で語りかけるように
-直近の投稿と内容が被らないように
ツイート本文のみ出力してください。"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text.strip()


def post_tweet(text: str) -> bool:
    """X APIでツイートを投稿する"""
    try:
        client = tweepy.Client(
            bearer_token=X_BEARER_TOKEN,
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_SECRET,
        )
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        log.info(f"投稿成功 tweet_id={tweet_id}")
        return True
    except tweepy.TweepyException as e:
        log.error(f"投稿失敗: {e}")
        return False


def run_once(dry_run: bool = False):
    """ニュース取得 → ツイート生成 → 投稿を1回実行する"""
    log.info("=== エージェント起動 ===")

    news = fetch_news()
    if news:
        log.info("ニュースを取得しました")
    else:
        log.info("ニュース取得失敗。フォールバックトピックを使用します")

    tweet = generate_tweet(news)
    log.info(f"生成ツイート:\n{tweet}")

    if dry_run:
        log.info("[DRY RUN] 実際には投稿しません")
        return

    post_tweet(tweet)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run_once(dry_run=dry)

