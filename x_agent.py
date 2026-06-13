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

# ── AI・就活関連 RSS フィード ─────────────────
RSS_FEEDS = [
    "https://zenn.dev/topics/ai/feed",       # Zenn AI特集
    "https://zenn.dev/topics/chatgpt/feed",  # Zenn ChatGPT特集
    "https://qiita.com/tags/ai/feed",        # Qiita AIタグ
    "https://qiita.com/tags/chatgpt/feed",   # Qiita ChatGPTタグ
]

# ── 就活×AI活用トピック（フォールバック） ────────
FALLBACK_TOPICS = [
    "ChatGPTを使ってエントリーシートを書く正しい方法と注意点",
    "AIが書いたESは採用担当者に見抜かれる？見抜かれないための工夫",
    "就活の自己PRをAIで磨く具体的なプロンプト術",
    "志望動機をChatGPTで書くときに必ず守るべきルール",
    "AIを使った企業研究の効率化テクニック",
    "ガクチカをAIで言語化するステップと落とし穴",
    "面接練習にClaudeやChatGPTを活用する方法",
    "AI時代に就活で差がつく自己分析の進め方",
    "就活のOB訪問質問リストをAIで作る方法",
    "ChatGPTで業界研究レポートを10分で作る手順",
    "AIに頼りすぎない！ES添削でAIを正しく使うコツ",
    "就活メールの文章をAIで効率よく仕上げる方法",
    "AIプロンプトで「刺さる」強みエピソードを引き出すコツ",
    "グループディスカッション対策にAIを使う方法",
    "AIで模擬面接をする際の効果的なプロンプト設計",
    "就活でChatGPTを使うのはずるい？AI活用のボーダーライン",
    "AIを使って複数企業のES提出を効率化する戦略",
    "ClaudeとChatGPTを使い分ける就活シーン別ガイド",
    "AI時代の就活で人間らしさをアピールする方法",
    "就活のスケジュール管理にAIツールを活用する方法",
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


TRENDING_HASHTAGS = [
    "#就活",
    "#ChatGPT",
    "#AI就活",
    "#就活AI",
    "#ES就活",
    "#自己PR",
    "#就活生と繋がりたい",
    "#エントリーシート",
    "#就活対策",
    "#就活面接",
    "#ChatGPT活用",
    "#AI活用",
    "#就活垢",
    "#就活相談",
    "#内定",
]


def fetch_trending_tweets() -> str | None:
    """X APIで就活界隈のバズっているツイートを取得する"""
    try:
        tag = random.choice(TRENDING_HASHTAGS)
        query = f"#28卒 {tag} -is:retweet lang:ja"
        log.info(f"トレンド検索クエリ: {query}")
        client = tweepy.Client(bearer_token=X_BEARER_TOKEN)
        response = client.search_recent_tweets(
            query=query,
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
        user_prompt = f"""以下は就活界隈でバズっているツイートです。これらを参考に、「就活×AI活用」をテーマにした独自のツイートを作成してください。

【バズっている投稿】
{trending_context}

ルール:
- 参考投稿のコピーは絶対にしない。テーマやトーンを参考に独自の内容にする
- ChatGPT・Claude等のAIを就活に活用する具体的なノウハウを盛り込む
- 280文字以内（日本語）
- 改行を適度に使い読みやすく
- 末尾に関連ハッシュタグを2〜3個付ける（例: #就活 #AI就活 #28卒）
- ハッシュタグは必ず #28卒 を使うこと。#26卒 #27卒 は絶対に使わないこと
- 絵文字を1〜2個使って親しみやすく
- 上から目線にならず、同じ目線で語りかけるように
ツイート本文のみ出力してください。"""
    elif news_context:
        user_prompt = f"""以下のニュースを参考に、「就活×AI活用」をテーマにしたツイートを作成してください。

【参考ニュース】
{news_context}

ルール:
- ChatGPT・Claude等のAIを就活に活用する視点でコメントする
- ハッシュタグを含め230文字以内（日本語）に収める（末尾にURLを別途追加するため）
- 改行を適度に使い読みやすく
- 末尾に関連ハッシュタグを2〜3個付ける（例: #就活 #AI就活 #28卒）
- ハッシュタグは必ず #28卒 を使うこと。#26卒 #27卒 は絶対に使わないこと
- 絵文字を1〜2個使って親しみやすく
- 宣伝っぽくならないよう自然な口調で
ツイート本文のみ出力してください。"""
    else:
        topic = random.choice(FALLBACK_TOPICS)
        user_prompt = f"""就活生に向けて「就活×AI活用」をテーマにした情報をツイートしてください。

【テーマ】{topic}

ルール:
- ChatGPT・Claude等のAIを就活に活用する具体的なアドバイスを書く
- 280文字以内（日本語）
- 改行を適度に使い読みやすく
- 末尾に関連ハッシュタグを2〜3個付ける（例: #就活 #AI就活 #28卒）
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


def generate_card_content(tweet_text: str) -> dict:
    """ツイートをカード用に要約する（title / points / summary）"""
    import json
    import re
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": f"""以下のツイートをカード画像用に要約してください。

ツイート:
{tweet_text}

以下のJSON形式のみ出力してください（コードブロック不要、余分なテキスト不要）:
{{
  "title": "15文字以内のタイトル",
  "points": ["ポイント1（20文字以内）", "ポイント2（20文字以内）", "ポイント3（20文字以内）"],
  "summary": "まとめの一言（25文字以内）"
}}"""}],
    )
    raw = message.content[0].text.strip()
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(raw)
    except Exception as e:
        log.warning(f"カードJSON解析失敗: {e} / raw={raw}")
        return {"title": "IT就活Tips", "points": [], "summary": ""}


def generate_image_card(tweet_text: str) -> str:
    """ツイート内容からテキストカード画像を生成してパスを返す"""
    from PIL import Image, ImageDraw, ImageFont

    card = generate_card_content(tweet_text)
    card_title   = _strip_emoji(card.get("title", "IT就活Tips"))
    card_points  = [_strip_emoji(p) for p in card.get("points", [])]
    card_summary = _strip_emoji(card.get("summary", ""))

    # ハッシュタグをツイート本文から抽出
    tag_lines = [l.strip() for l in tweet_text.split("\n") if l.strip().startswith("#")]
    hashtag_text = "  ".join(tag_lines)

    WIDTH, HEIGHT = 1200, 675
    BG_COLOR      = (13, 17, 38)
    ACCENT_COLOR  = (29, 115, 230)
    TEXT_COLOR    = (235, 240, 255)
    POINT_COLOR   = (200, 220, 255)
    SUMMARY_COLOR = (160, 200, 255)
    HASHTAG_COLOR = (100, 170, 255)

    img  = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 枠線
    draw.rectangle([(0, 0), (8, HEIGHT)], fill=ACCENT_COLOR)
    draw.rectangle([(0, 0), (WIDTH, 6)], fill=ACCENT_COLOR)
    draw.rectangle([(WIDTH - 8, 0), (WIDTH, HEIGHT)], fill=ACCENT_COLOR)
    draw.rectangle([(0, HEIGHT - 6), (WIDTH, HEIGHT)], fill=ACCENT_COLOR)

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
        header_font  = ImageFont.truetype(font_path, 42) if font_path else ImageFont.load_default()
        title_font   = ImageFont.truetype(font_path, 48) if font_path else ImageFont.load_default()
        point_font   = ImageFont.truetype(font_path, 34) if font_path else ImageFont.load_default()
        summary_font = ImageFont.truetype(font_path, 30) if font_path else ImageFont.load_default()
        tag_font     = ImageFont.truetype(font_path, 26) if font_path else ImageFont.load_default()
    except Exception:
        header_font = title_font = point_font = summary_font = tag_font = ImageFont.load_default()

    # ヘッダー
    draw.text((40, 40), "就活 x AI活用 Tips", font=header_font, fill=ACCENT_COLOR)
    draw.rectangle([(40, 102), (WIDTH - 40, 106)], fill=(40, 60, 110))

    # タイトル
    draw.text((40, 118), card_title, font=title_font, fill=TEXT_COLOR)

    # ポイント
    y = 188
    for point in card_points[:3]:
        draw.text((40, y), f"・{point}", font=point_font, fill=POINT_COLOR)
        y += 52

    # 区切り線
    draw.rectangle([(40, y + 8), (WIDTH - 40, y + 11)], fill=(40, 60, 110))

    # まとめ
    if card_summary:
        draw.text((40, y + 20), card_summary, font=summary_font, fill=SUMMARY_COLOR)

    # ハッシュタグ
    draw.text((40, HEIGHT - 60), hashtag_text, font=tag_font, fill=HASHTAG_COLOR)

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

