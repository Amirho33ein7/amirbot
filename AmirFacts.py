# -*- coding: utf-8 -*-
"""AmirFacts — Persian multi-source fact bot.

Runtime polling is intentionally OFF. The source engine is designed for a
large, continuously refreshed fact pool with persistent per-user deduplication.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import os
import random
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

import aiohttp
from telebot import types
from telebot.async_telebot import AsyncTeleBot

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("AMIRXPROXY_BOT_TOKEN") or "TOKEN RO INJA BEZAR"
DB_PATH = Path(os.getenv("AMIRFACTS_DB", "amirfacts.sqlite3"))
TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
MIN_FACT = 70
MAX_FACT = 700
COOLDOWN = 2.0

TOPICS: dict[str, tuple[str, ...]] = {
    "new": ("دانستنی", "اختراع", "کشف", "علم", "دانشمند", "تاریخ علم", "فرهنگ", "جهان"),
    "space": ("فضا", "سیاره", "کهکشان", "ستاره", "ماه", "مریخ", "زمین", "خورشید", "نجوم", "کیهان", "سیارک", "سحابی", "آسمان"),
    "science": ("فیزیک", "شیمی", "زیست", "مغز", "ژنتیک", "سلول", "اتم", "مولکول", "زیست شناسی", "پزشکی", "ریاضی", "آزمایش", "ماده", "انرژی"),
    "technology": ("رایانه", "اینترنت", "هوش مصنوعی", "فناوری", "برنامه نویسی", "شبکه", "پردازنده", "نرم افزار", "سخت افزار", "ربات", "داده", "الگوریتم", "رمزنگاری"),
    "nature": ("حیوانات", "اقیانوس", "طبیعت", "گیاه", "جانور", "پرندگان", "پستانداران", "دریا", "جنگل", "زیست بوم", "زمین شناسی", "اقلیم", "حشرات"),
    "history": ("تاریخ", "تمدن", "باستان", "اختراع", "اکتشاف", "امپراتوری", "پادشاه", "جنگ", "باستان شناسی", "فرهنگ", "ایران باستان", "موزه", "سلسله"),
    "football": ("فوتبال", "جام جهانی", "رونالدو", "مسی", "پله", "مارادونا", "لیگ قهرمانان", "باشگاه", "بازیکن", "مربی", "تیم ملی", "ورزشگاه", "لیگ"),
    "world": ("جمعیت", "کشورها", "اقتصاد", "آمار", "جهان", "تولید ناخالص", "انرژی", "اینترنت", "سلامت", "آموزش", "آب", "جمعیت کشورها"),
}
TOPIC_NAMES = {"new":"دانستنی", "space":"فضا", "science":"علم", "technology":"فناوری", "nature":"طبیعت", "history":"تاریخ", "football":"فوتبال", "world":"جهان"}
TOPIC_SIGNALS = {
    "space": ("فضا", "سیاره", "کهکشان", "ستاره", "ماه", "مریخ", "خورشید", "نجوم", "کیهان", "سیارک", "سحابی", "زمین", "مدار"),
    "science": ("علم", "فیزیک", "شیمی", "زیست", "سلول", "ژن", "مغز", "اتم", "مولکول", "پزشکی", "ریاضی", "آزمایش", "ماده", "انرژی"),
    "technology": ("رایانه", "اینترنت", "هوش مصنوعی", "فناوری", "برنامه نویسی", "شبکه", "پردازنده", "نرم افزار", "سخت افزار", "ربات", "داده", "الگوریتم", "رمزنگاری"),
    "nature": ("حیوان", "جانور", "گیاه", "اقیانوس", "دریا", "جنگل", "اقلیم", "زیست بوم", "پرنده", "پستاندار", "زمین شناسی", "طبیعت", "حشرات"),
    "history": ("تاریخ", "تمدن", "باستان", "امپراتوری", "پادشاه", "جنگ", "باستان شناسی", "ایران باستان", "موزه", "فرهنگ", "سلسله"),
    "football": ("فوتبال", "جام جهانی", "رونالدو", "مسی", "پله", "مارادونا", "لیگ قهرمانان", "باشگاه", "بازیکن", "مربی", "تیم ملی", "ورزشگاه", "لیگ"),
    "world": ("جمعیت", "کشور", "اقتصاد", "تولید ناخالص", "انرژی", "اینترنت", "سلامت", "آموزش", "آب", "جهان", "آمار"),
}

FALLBACK_FACTS = (
    ("علم", "نور خورشید حدود ۸ دقیقه و ۲۰ ثانیه طول می‌کشد تا از خورشید به زمین برسد.", "بانک پشتیبان علمی"),
    ("علم", "اختلاف زمان دریافت نور خورشید و مشاهده آن از زمین به دلیل فاصله بسیار زیاد خورشید از زمین است.", "بانک پشتیبان علمی"),
    ("طبیعت", "اختاپوس سه قلب دارد و خون آن به دلیل وجود هموسیانین رنگی متمایل به آبی دارد.", "بانک پشتیبان طبیعت"),
    ("فضا", "یک شبانه‌روز خورشیدی روی عطارد حدود ۱۷۶ روز زمینی طول می‌کشد.", "بانک پشتیبان فضا"),
    ("تاریخ", "واژه الگوریتم از نام محمد بن موسی خوارزمی، دانشمند ایرانی، گرفته شده است.", "بانک پشتیبان تاریخ علم"),
    ("فناوری", "رایانه‌های الکترونیکی نخستین بسیار بزرگ بودند و برای نگهداری آنها به فضای بسیار زیادی نیاز بود.", "بانک پشتیبان فناوری"),
    ("فوتبال", "نخستین دوره جام جهانی فوتبال در سال ۱۹۳۰ در اروگوئه برگزار شد و تیم میزبان قهرمان شد.", "بانک پشتیبان فوتبال"),
    ("فوتبال", "پله تنها بازیکنی است که سه بار قهرمان جام جهانی فوتبال شده است.", "بانک پشتیبان فوتبال"),
)
_last_action: dict[int, float] = {}


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, first_seen REAL NOT NULL, last_seen REAL NOT NULL)")
        conn.execute("""CREATE TABLE IF NOT EXISTS seen_facts(
            user_id INTEGER NOT NULL,
            fact_key TEXT NOT NULL,
            created_at REAL NOT NULL,
            source TEXT NOT NULL,
            category TEXT NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(user_id, fact_key)
        )""")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(seen_facts)").fetchall()}
        if "text" not in columns:
            conn.execute("ALTER TABLE seen_facts ADD COLUMN text TEXT NOT NULL DEFAULT ''")


def remember_user(user_id: int) -> None:
    now = time.time()
    with db() as conn:
        conn.execute("INSERT INTO users(user_id,first_seen,last_seen) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen", (user_id, now, now))


def normalize_fact(text: str) -> str:
    text = html.unescape(text or "").casefold()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[\u200c\u200d\u200f\u202a-\u202e]", "", text)
    text = re.sub(r"[«»\"'“”()\[\]{}]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fact_key(text: str, source: str = "") -> str:
    # Deliberately source-independent: the same sentence from another source is still a duplicate.
    return hashlib.sha256(normalize_fact(text).encode("utf-8")).hexdigest()


def has_seen(user_id: int, key: str) -> bool:
    with db() as conn:
        row = conn.execute("SELECT 1 FROM seen_facts WHERE user_id=? AND fact_key=? LIMIT 1", (user_id, key)).fetchone()
    return row is not None


def mark_seen(user_id: int, key: str, source: str, category: str, text: str = "") -> None:
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO seen_facts(user_id,fact_key,created_at,source,category,text) VALUES(?,?,?,?,?,?)", (user_id, key, time.time(), source, category, clean(text)))


def seen_count(user_id: int) -> int:
    with db() as conn:
        row = conn.execute("SELECT COUNT(*) FROM seen_facts WHERE user_id=?", (user_id,)).fetchone()
    return int(row[0] if row else 0)


def clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\[[0-9۰-۹]+\]", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_FACT:
        text = text[:MAX_FACT].rsplit(" ", 1)[0] + "…"
    return text


def persian_only(text: str) -> bool:
    text = clean(text)
    return len(re.findall(r"[\u0600-\u06FF]", text)) >= 15 and not re.search(r"[A-Za-z]", text)


def usable(text: str) -> bool:
    text = clean(text)
    return MIN_FACT <= len(text) <= MAX_FACT and "@" not in text and "t.me/" not in text.lower() and persian_only(text)


def is_relevant(text: str, topic: str | None) -> bool:
    if topic in (None, "new"):
        return True
    hay = normalize_fact(text)
    return any(signal in hay for signal in TOPIC_SIGNALS.get(topic, ()))


def shingle_similarity(a: str, b: str) -> float:
    na, nb = normalize_fact(a), normalize_fact(b)
    if not na or not nb:
        return 0.0
    wa, wb = set(na.split()), set(nb.split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def is_user_duplicate(user_id: int, text: str) -> bool:
    key = fact_key(text)
    if has_seen(user_id, key):
        return True
    with db() as conn:
        rows = conn.execute("SELECT text FROM seen_facts WHERE user_id=? AND text!='' ORDER BY created_at DESC LIMIT 400", (user_id,)).fetchall()
    return any(shingle_similarity(text, row[0]) >= 0.78 for row in rows)


async def get_json(session: aiohttp.ClientSession, url: str, params: dict[str, Any] | None = None) -> Any:
    try:
        async with session.get(url, params=params, allow_redirects=True) as response:
            if response.status != 200:
                return None
            return await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return None


def variants(extract: str) -> list[str]:
    extract = clean(extract)
    if not extract:
        return []
    sentences = [s.strip() for s in re.split(r"(?<=[\.؟!])\s+", extract) if s.strip()]
    if len(sentences) <= 2:
        return [extract]
    result = [extract]
    windows = [(0,2),(1,3),(2,4),(0,3),(1,4)]
    random.shuffle(windows)
    for a,b in windows:
        candidate = " ".join(sentences[a:b]).strip()
        if candidate and candidate not in result:
            result.append(candidate)
    return result


async def source_wikipedia(session: aiohttp.ClientSession, topic: str | None):
    queries = list(TOPICS.get(topic or "new", TOPICS["new"]))
    random.shuffle(queries)
    for query in queries[:10]:
        data = await get_json(session, "https://fa.wikipedia.org/w/api.php", {
            "action":"query", "format":"json", "generator":"search", "gsrsearch":query,
            "gsrnamespace":0, "gsrlimit":25, "prop":"extracts|info", "exintro":1,
            "explaintext":1, "inprop":"url"
        })
        if not isinstance(data, dict):
            continue
        pages = list(data.get("query", {}).get("pages", {}).values())
        random.shuffle(pages)
        for page in pages:
            title = clean(str(page.get("title", "")))
            extract = clean(str(page.get("extract", "")))
            url = str(page.get("fullurl", ""))
            if not title or not url.startswith("https://fa.wikipedia.org/"):
                continue
            if any(prefix in title for prefix in ("کاربر:","بحث:","الگو:","پرونده:","رده:","فهرست ")):
                continue
            if not is_relevant(title + " " + extract, topic):
                continue
            for text in variants(extract):
                if usable(text):
                    return text, TOPIC_NAMES.get(topic or "new","دانستنی"), "ویکی‌پدیای فارسی", fact_key(text)
    return None


async def source_wikipedia_random(session: aiohttp.ClientSession, topic: str | None):
    data = await get_json(session, "https://fa.wikipedia.org/w/api.php", {
        "action":"query", "format":"json", "generator":"random", "grnnamespace":0,
        "grnlimit":35, "prop":"extracts|info", "exintro":1, "explaintext":1, "inprop":"url"
    })
    if not isinstance(data, dict):
        return None
    pages = list(data.get("query", {}).get("pages", {}).values())
    random.shuffle(pages)
    for page in pages:
        title = clean(str(page.get("title", "")))
        extract = clean(str(page.get("extract", "")))
        url = str(page.get("fullurl", ""))
        if not url.startswith("https://fa.wikipedia.org/") or any(prefix in title for prefix in ("کاربر:","بحث:","الگو:","پرونده:","رده:","فهرست ")):
            continue
        if not is_relevant(title + " " + extract, topic):
            continue
        for text in variants(extract):
            if usable(text):
                return text, TOPIC_NAMES.get(topic or "new","دانستنی"), "ویکی‌پدیای فارسی — تصادفی", fact_key(text)
    return None


async def source_wikidata_topic(session: aiohttp.ClientSession, topic: str | None):
    if topic is None:
        topic = "new"
    queries = list(TOPICS.get(topic, TOPICS["new"]))
    random.shuffle(queries)
    for query in queries[:10]:
        data = await get_json(session, "https://www.wikidata.org/w/api.php", {
            "action":"wbsearchentities", "search":query, "language":"fa", "uselang":"fa",
            "format":"json", "limit":25, "type":"item"
        })
        if not isinstance(data, dict):
            continue
        hits = data.get("search", [])
        random.shuffle(hits)
        for hit in hits:
            label = clean(str(hit.get("label", "")))
            desc = clean(str(hit.get("description", "")))
            qid = str(hit.get("id", ""))
            if not (qid and label and desc):
                continue
            text = clean(f"در موضوع {TOPIC_NAMES.get(topic, 'دانستنی')}، «{label}» {desc} است.")
            if usable(text) and is_relevant(text, topic):
                return text, TOPIC_NAMES.get(topic,"دانستنی"), "ویکی‌داده", fact_key(text)
    return None


async def source_football(session: aiohttp.ClientSession):
    candidates = [source_wikipedia, source_wikipedia_random, source_wikidata_topic]
    random.shuffle(candidates)
    for loader in candidates:
        value = await loader(session, "football")
        if value and value[1] == "فوتبال" and usable(value[0]) and is_relevant(value[0], "football"):
            return value[0], "فوتبال", value[2] + " — فوتبال", value[3]
    return None


async def source_nasa(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "space"):
        return None
    for _ in range(5):
        offset = random.randint(1, 2500)
        day = time.strftime("%Y-%m-%d", time.gmtime(time.time() - offset * 86400))
        data = await get_json(session, "https://api.nasa.gov/planetary/apod", {"api_key":os.getenv("NASA_API_KEY","DEMO_KEY"),"date":day})
        if not isinstance(data, dict) or not data.get("date"):
            continue
        text = clean(f"ناسا در آرشیو تصویر نجومی روز، برای تاریخ {data['date']} یک محتوای نجومی ثبت کرده است.")
        if usable(text):
            return text, "فضا", "ناسا", fact_key(text)
    return None


WORLD_COUNTRIES = {"IRN":"ایران","FRA":"فرانسه","DEU":"آلمان","BRA":"برزیل","JPN":"ژاپن","IND":"هند","CAN":"کانادا","ESP":"اسپانیا","ITA":"ایتالیا","TUR":"ترکیه","EGY":"مصر","AUS":"استرالیا","MEX":"مکزیک","KOR":"کره جنوبی","ZAF":"آفریقای جنوبی"}
WORLD_INDICATORS = {"SP.POP.TOTL":"جمعیت", "NY.GDP.MKTP.CD":"تولید ناخالص داخلی", "SP.DYN.LE00.IN":"امید به زندگی", "IT.NET.USER.ZS":"درصد استفاده از اینترنت", "EG.ELC.ACCS.ZS":"درصد دسترسی به برق"}


async def source_world_bank(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "world"):
        return None
    indicator, name = random.choice(list(WORLD_INDICATORS.items()))
    code, country = random.choice(list(WORLD_COUNTRIES.items()))
    data = await get_json(session, f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}", {"format":"json","per_page":30})
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
        return None
    rows = [r for r in data[1] if r.get("value") is not None]
    if not rows:
        return None
    row = random.choice(rows)
    try:
        value = float(row["value"])
        number = f"{value:,.2f}" if indicator in ("SP.DYN.LE00.IN","IT.NET.USER.ZS","EG.ELC.ACCS.ZS") else f"{int(value):,}"
        number = number.replace(",","،").replace(".","٫")
    except (TypeError, ValueError):
        return None
    unit = " درصد" if indicator in ("IT.NET.USER.ZS","EG.ELC.ACCS.ZS") else ""
    text = clean(f"طبق داده‌های بانک جهانی، {name} {country} در سال {row.get('date')} حدود {number}{unit} ثبت شده است.")
    return (text,"جهان","بانک جهانی",fact_key(text)) if usable(text) else None


async def source_usgs(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "nature"):
        return None
    feed = random.choice(("significant_month","4.5_month","2.5_month","1.0_month"))
    data = await get_json(session, f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson")
    if not isinstance(data, dict) or not data.get("features"):
        return None
    item = random.choice(data["features"])
    props = item.get("properties", {})
    magnitude = props.get("mag")
    event_id = str(item.get("id", ""))
    if magnitude is None or not event_id:
        return None
    text = clean(f"در داده‌های سازمان زمین‌شناسی آمریکا، یک زمین‌لرزه با بزرگای حدود {float(magnitude):.1f} ثبت شده است.")
    return (text,"طبیعت","سازمان زمین‌شناسی آمریکا",fact_key(text)) if usable(text) else None


async def candidate_loaders(topic: str | None) -> list[Callable[[aiohttp.ClientSession, str | None], Awaitable[Any]]]:
    loaders: list[Callable[[aiohttp.ClientSession, str | None], Awaitable[Any]]] = [source_wikipedia, source_wikipedia_random, source_wikidata_topic]
    if topic in (None, "space"):
        loaders.append(source_nasa)
    if topic in (None, "world"):
        loaders.append(source_world_bank)
    if topic in (None, "nature"):
        loaders.append(source_usgs)
    if topic == "football":
        loaders = [source_football]
    return loaders


async def get_new_fact(user_id: int, topic: str | None = None):
    remember_user(user_id)
    loaders = await candidate_loaders(topic)
    async with aiohttp.ClientSession(timeout=TIMEOUT, headers={"User-Agent":"AmirFacts/6.0"}) as session:
        for _ in range(24):
            loader = random.choice(loaders)
            try:
                value = await loader(session, topic)
            except Exception:
                value = None
            if not value:
                continue
            text, category, source, key = value
            if category != TOPIC_NAMES.get(topic, category):
                continue
            if not usable(text) or not is_relevant(text, topic):
                continue
            if is_user_duplicate(user_id, text):
                continue
            return text, category, source, fact_key(text)

    # Finite local reserve is only a last resort when live sources fail.
    pool = list(FALLBACK_FACTS)
    random.shuffle(pool)
    for category, text, source in pool:
        if topic and category != TOPIC_NAMES.get(topic):
            continue
        if not usable(text) or is_user_duplicate(user_id, text):
            continue
        return text, category, source, fact_key(text)
    return None


def allowed(user_id: int) -> bool:
    now = time.time()
    if now - _last_action.get(user_id, 0.0) < COOLDOWN:
        return False
    _last_action[user_id] = now
    return True


def keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    rows = (
        (("🎲 فکت جدید","fact:new"),("⚽ فوتبال","fact:football")),
        (("🌌 فضا","fact:space"),("🧠 علم","fact:science")),
        (("💻 فناوری","fact:technology"),("🌿 طبیعت","fact:nature")),
        (("🏛️ تاریخ","fact:history"),("🌍 جهان","fact:world")),
    )
    for row in rows:
        kb.add(*[types.InlineKeyboardButton(text, callback_data=data) for text,data in row])
    kb.add(types.InlineKeyboardButton("📊 آمار من","stats"))
    return kb


def render(text: str, category: str, source: str) -> str:
    return f"✨ <b>فکت جدید</b>\n\n{html.escape(text)}\n\n🏷️ <b>دسته:</b> {html.escape(category)}\n📚 <b>منبع:</b> {html.escape(source)}"

if not BOT_TOKEN or BOT_TOKEN == "TOKEN RO INJA BEZAR":
    raise RuntimeError("Telegram bot token is missing")

bot = AsyncTeleBot(BOT_TOKEN, parse_mode="HTML")


@bot.message_handler(commands=["start","help"])
async def start_handler(message: types.Message) -> None:
    remember_user(message.from_user.id)
    await bot.send_message(message.chat.id, "🚀 <b>AmirFacts</b>\n\nفکت‌های فارسی، منبع‌دار و غیرتکراری.", reply_markup=keyboard())


async def send_fact(chat_id: int, user_id: int, topic: str | None = None) -> None:
    if not allowed(user_id):
        await bot.send_message(chat_id, "⏳ یه کم آروم‌تر 😄")
        return
    await bot.send_dice(chat_id, emoji="🎲")
    status = await bot.send_message(chat_id, "🔎 <i>از چند منبع دنبال یک فکت تازه و غیرتکراری می‌گردم...</i>")
    result = await get_new_fact(user_id, topic)
    if not result:
        await bot.edit_message_text("🔄 منابع زنده فعلاً پاسخ مناسب ندادند؛ دوباره امتحان کن تا مسیر دیگری از منابع بررسی شود.", chat_id=chat_id, message_id=status.message_id, reply_markup=keyboard())
        return
    text, category, source, key = result
    if not usable(text) or (topic and category != TOPIC_NAMES[topic]) or is_user_duplicate(user_id, text):
        await bot.edit_message_text("🔄 مورد تکراری یا نامعتبر فیلتر شد؛ دوباره بزن.", chat_id=chat_id, message_id=status.message_id, reply_markup=keyboard())
        return
    mark_seen(user_id, key, source, category, text)
    await bot.edit_message_text(render(text, category, source), chat_id=chat_id, message_id=status.message_id, reply_markup=keyboard())


@bot.message_handler(commands=["fact"])
async def fact_command(message: types.Message) -> None:
    await send_fact(message.chat.id, message.from_user.id)


@bot.message_handler(commands=["stats"])
async def stats_command(message: types.Message) -> None:
    await send_stats(message.chat.id, message.from_user.id)


async def send_stats(chat_id: int, user_id: int) -> None:
    await bot.send_message(chat_id, f"📊 <b>آمار تو</b>\n\n🧠 فکت‌های دیده‌شده: <b>{seen_count(user_id)}</b>", reply_markup=keyboard())


@bot.callback_query_handler(func=lambda call: call.data == "fact:new")
async def new_fact_callback(call: types.CallbackQuery) -> None:
    await bot.answer_callback_query(call.id)
    await send_fact(call.message.chat.id, call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("fact:") and call.data != "fact:new")
async def topic_callback(call: types.CallbackQuery) -> None:
    await bot.answer_callback_query(call.id)
    topic = call.data.split(":",1)[1]
    if topic in TOPICS:
        await send_fact(call.message.chat.id, call.from_user.id, topic)


@bot.callback_query_handler(func=lambda call: call.data == "stats")
async def stats_callback(call: types.CallbackQuery) -> None:
    await bot.answer_callback_query(call.id)
    await send_stats(call.message.chat.id, call.from_user.id)


async def main() -> None:
    init_db()
    print("AmirFacts configured. Polling is OFF by design.")


if __name__ == "__main__":
    asyncio.run(main())
