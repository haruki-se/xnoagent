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

# ── IT業界ニュース RSS フィード ───────────────
RSS_FEEDS = [
    "https://news.yahoo.co.jp/rss/topics/it.xml",
    "https://rss.itmedia.co.jp/rss/2.0/itmedia_all.xml",
    "https://zenn.dev/feed",
]

# ── IT就活トピック（ニュースがない場合のフォールバック） ──
FALLBACK_TOPICS = [
    "IT企業のエンジニア職・SE職の面接でよく聞かれる技術質問",
    "未経験からIT就職するためのポートフォリオの作り方",
    "SIer・Web系・自社開発の違いと選び方",
    "IT企業のインターンシップで評価されるポイント",
    "エンジニア就活で差がつくGitHub活用術",
    "IT就活のためのプログラミングスキル習得ロードマップ",
    "Webエンジニア志望者が知っておくべき技術スタック",
    "IT企業の技術面接対策：アルゴリズムとデータ構造の基礎",
    "Google・Amazon・Metaなど外資IT企業の就活攻略法",
    "ITベンチャー vs 大手SIer、就活生はどちらを選ぶべきか",
    "AI・機械学習エンジニア志望者の就活戦略",
    "IT企業のOB・OG訪問で絶対に聞くべき質問リスト",
    "クラウド（AWS・GCP・Azure）資格は就活に有利か",
    "IT企業の逆質問で好印象を与えるテクニック",
    "エンジニア就活における自己PRの書き方",
    "IT業界の職種比較：SE・PG・インフラ・PM・データサイエンティスト",
    "IT就活のガクチカ：個人開発・ハッカソン・競プロの活かし方",
    "IT企業の年収・働き方・キャリアパスを徹底比較",
    "セキュリティエンジニア志望者の就活準備",
    "IT就活に役立つ資格：基本情報技術者・応用情報・TOEIC",
]


def fetch_news() -> tuple[str, str] | None:
    """RSSフィードから就活・ビジネス関連の最新ニュースを取得する。(context, url) を返す"""
    items = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                items.append({
                    "title": entry.title,
                    "summary": getattr(entry, "summary", ""),
                    "link": getattr(entry, "link", ""),
                })
        except Exception as e:
            log.warning(f"RSS取得失敗 {url}: {e}")

    if not items:
        return None

    random.shuffle(items)
    picked = items[0]
    context = f"タイトル: {picked['title']}\n概要: {picked['summary'][:200]}"
    return context, picked["link"]


def fetch_trending_tweets() -> str | None:
    """X APIで就活界隈のバズっているツイートを取得する"""
    try:
        client = tweepy.Client(bearer_token=X_BEARER_TOKEN)
        response = client.search_recent_tweets(
            query="#就活 #IT就活 -is:retweet lang:ja",
            max_results=10,
            tweet_fields=["public_metrics"],
            sort_order="relevancy",
        )
        if not response.data:
            return None
        tweets = sorted(
            response.data,
            key=lambda t: t.public_metrics["like_count"] + t.public_metrics["retweet_count"] * 2,
            reverse=True,
        )
        parts = []
        for i, t in enumerate(tweets[:3], 1):
            m = t.public_metrics
            parts.append(f"【参考{i}】\n{t.text}\nいいね:{m['like_count']} RT:{m['retweet_count']}")
        return "\n\n".join(parts)
    except Exception as e:
        log.warning(f"トレンドツイート取得失敗: {e}")
        return None


def generate_tweet(news_context: str | None, news_url: str | None = None, trending_context: str | None = None) -> str:
    """Claude APIを使って就活に関するツイートを生成する"""
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    if trending_context:
        user_prompt = f"""以下は就活界隈でバズっているツイートです。これらを参考に、IT就活生に役立つ独自のツイートを作成してください。

【バズっている投稿】
{trending_context}

ルール:
- 参考投稿のコピーは絶対にしない。テーマやトーンを参考に独自の内容にする
- IT業界を志望する就活生の役に立つ内容
- 280文字以内（日本語）
- 改行を適度に使い読みやすく
- 末尾に関連ハッシュタグを2〜3個付ける（例: #IT就活 #エンジニア就活 #28卒）
- ハッシュタグは必ず #28卒 を使うこと。#26卒 #27卒 は絶対に使わないこと
- 絵文字を1〜2個使って親しみやすく
- 上から目線にならず、同じ目線で語りかけるように
ツイート本文のみ出力してください。"""
    elif news_context:
        user_prompt = f"""以下のIT業界のニュースを参考に、IT就活生に役立つ情報をツイートしてください。

【参考ニュース】
{news_context}

ルール:
- IT業界を志望する就活生の役に立つ内容にしてください
- ハッシュタグを含め230文字以内（日本語）に収める（末尾にURLを別途追加するため）
- 改行を適度に使い読みやすく
- 末尾に関連ハッシュタグを2〜3個付ける（例: #IT就活 #エンジニア就活 #28卒）
- ハッシュタグは必ず #28卒 を使うこと。#26卒 #27卒 は絶対に使わないこと
- 絵文字を1〜2個使って親しみやすく
- 宣伝っぽくならないよう自然な口調で
ツイート本文のみ出力してください。"""
    else:
        topic = random.choice(FALLBACK_TOPICS)
        user_prompt = f"""IT業界を志望する就活生に役立つ情報をツイートしてください。

【テーマ】{topic}

ルール:
- IT業界志望の就活生に役立つ具体的なアドバイスを書く
- 280文字以内（日本語）
- 改行を適度に使い読みやすく
- 末尾に関連ハッシュタグを2〜3個付ける（例: #IT就活 #エンジニア就活 #28卒）
- ハッシュタグは必ず #28卒 を使うこと。#26卒 #27卒 は絶対に使わないこと
- 絵文字を1〜2個使って親しみやすく
- 上から目線にならず、同じ目線で語りかけるように
- 直近の投稿と内容が被らないように
ツイート本文のみ出力してください。"""

    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=400,
        messages=[{"role": "user", "content": user_prompt}],
    )
    tweet = message.content[0].text.strip()
    if news_url:
        tweet = f"{tweet}\n\n{news_url}"
    return tweet


def _strip_emoji(text: str) -> str:
    """絵文字を除去して文字化けを防ぐ"""
    import unicodedata
    return "".join(c for c in text if unicodedata.category(c) not in ("So", "Cs") and ord(c) < 0x10000)


def generate_image_card(tweet_text: str) -> str:
    """ツイート内容からテキストカード画像を生成してパスを返す"""
    from PIL import Image, ImageDraw, ImageFont

    WIDTH, HEIGHT = 1200, 675
    BG_COLOR      = (13, 17, 38)
    ACCENT_COLOR  = (29, 115, 230)
    TEXT_COLOR    = (235, 240, 255)
    HASHTAG_COLOR = (100, 170, 255)

    img  = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 枠線
    draw.rectangle([(0, 0), (8, HEIGHT)], fill=ACCENT_COLOR)
    draw.rectangle([(0, 0), (WIDTH, 6)], fill=ACCENT_COLOR)
    draw.rectangle([(WIDTH - 8, 0), (WIDTH, HEIGHT)], fill=ACCENT_COLOR)
    draw.rectangle([(0, HEIGHT - 6), (WIDTH, HEIGHT)], fill=ACCENT_COLOR)

    # フォント読み込み（Ubuntu / Windows 両対応）
    font_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/YuGothR.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]
    font_path = next((p for p in font_candidates if os.path.exists(p)), None)
    try:
        title_font = ImageFont.truetype(font_path, 54) if font_path else ImageFont.load_default()
        body_font  = ImageFont.truetype(font_path, 36) if font_path else ImageFont.load_default()
        tag_font   = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()
    except Exception:
        title_font = body_font = tag_font = ImageFont.load_default()

    # 本文とハッシュタグを分離（絵文字除去）
    raw_lines  = tweet_text.split("\n")
    tag_lines  = [_strip_emoji(l.strip()) for l in raw_lines if l.strip().startswith("#")]
    body_lines = [_strip_emoji(l) for l in raw_lines if not l.strip().startswith("#") and l.strip() and not l.startswith("http")]
    hashtag_text = "  ".join(tag_lines)

    # タイトル
    draw.text((52, 48), "IT就活 Tips", font=title_font, fill=ACCENT_COLOR)
    draw.rectangle([(52, 120), (WIDTH - 52, 124)], fill=(40, 60, 110))

    # 本文：22文字で折り返し、最大7行まで表示
    wrapped: list[str] = []
    for line in body_lines:
        if not line.strip():
            continue
        for i in range(0, max(len(line), 1), 22):
            wrapped.append(line[i:i + 22])
    wrapped = wrapped[:7]
    draw.text((52, 148), "\n".join(wrapped), font=body_font, fill=TEXT_COLOR, spacing=16)

    # ハッシュタグ
    draw.text((52, HEIGHT - 68), hashtag_text, font=tag_font, fill=HASHTAG_COLOR)

    path = os.path.join(os.path.dirname(__file__), "tweet_card.png")
    img.save(path)
    return path


def post_tweet(text: str) -> bool:
    """X APIでツイートを投稿する"""
    try:
        auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
        api_v1 = tweepy.API(auth)

        image_path = generate_image_card(text)
        media = api_v1.media_upload(filename=image_path)
        os.remove(image_path)

        client = tweepy.Client(
            bearer_token=X_BEARER_TOKEN,
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_SECRET,
        )
        response = client.create_tweet(text=text, media_ids=[media.media_id])
        tweet_id = response.data["id"]
        log.info(f"投稿成功 tweet_id={tweet_id}")
        return True
    except tweepy.TweepyException as e:
        log.error(f"投稿失敗: {e}")
        return False


def run_once(dry_run: bool = False):
    """ニュース取得 → ツイート生成 → 投稿を1回実行する"""
    log.info("=== エージェント起動 ===")

    trending_context = fetch_trending_tweets()
    if trending_context:
        log.info("トレンドツイートを取得しました")
        tweet = generate_tweet(None, None, trending_context)
    else:
        log.info("トレンド取得失敗。RSSニュースにフォールバックします")
        result = fetch_news()
        if result:
            news_context, news_url = result
            log.info("ニュースを取得しました")
        else:
            news_context, news_url = None, None
            log.info("ニュース取得失敗。フォールバックトピックを使用します")
        tweet = generate_tweet(news_context, news_url)
    log.info(f"生成ツイート:\n{tweet}")

    if dry_run:
        log.info("[DRY RUN] 実際には投稿しません")
        return

    post_tweet(tweet)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run_once(dry_run=dry)

