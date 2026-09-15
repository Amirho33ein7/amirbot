# -*- coding: utf-8 -*-
"""AmirFacts — Persian multi-source Telegram facts bot."""
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

# ============================================================
# TOKEN — KEEP THIS SECTION
# ============================================================
BOT_TOKEN = "TOKEN RO INJA BEZAR"
BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("AMIRXPROXY_BOT_TOKEN")
    or BOT_TOKEN
)
# ============================================================

DB_PATH = Path(os.getenv("AMIRFACTS_DB", "amirfacts.sqlite3"))
TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
MIN_FACT = 70
MAX_FACT = 650
COOLDOWN = 2.0

TOPICS: dict[str, tuple[str, ...]] = {
    "new": ("دانستنی", "اختراع", "کشف", "علم", "دانشمند", "تاریخ علم", "جانور", "طبیعت", "جهان", "فرهنگ"),
    "space": ("فضا", "سیاره", "کهکشان", "ستاره", "ماه", "مریخ", "زمین", "خورشید", "نجوم", "کیهان", "سیارک", "سحابی"),
    "science": ("فیزیک", "شیمی", "زیست", "مغز", "ژنتیک", "سلول", "اتم", "مولکول", "زیست شناسی", "پزشکی", "ریاضی", "آزمایش"),
    "technology": ("رایانه", "اینترنت", "هوش مصنوعی", "فناوری", "برنامه نویسی", "شبکه", "پردازنده", "نرم افزار", "سخت افزار", "ربات", "داده", "الگوریتم"),
    "nature": ("حیوانات", "اقیانوس", "طبیعت", "گیاه", "جانور", "پرندگان", "پستانداران", "دریا", "جنگل", "زیست بوم", "زمین شناسی", "اقلیم"),
    "history": ("تاریخ", "تمدن", "باستان", "اختراع", "اکتشاف", "امپراتوری", "پادشاه", "جنگ", "باستان شناسی", "فرهنگ", "ایران باستان", "دانشمندان"),
    "football": ("فوتبال", "جام جهانی", "رونالدو", "مسی", "پله", "مارادونا", "لیگ قهرمانان", "باشگاه", "بازیکن", "مربی", "تیم ملی", "ورزشگاه"),
    "world": ("جمعیت", "کشورها", "اقتصاد", "آمار", "جهان", "تولید ناخالص", "جمعیت جهان", "انرژی", "اینترنت", "سلامت", "آموزش", "آب"),
}
TOPIC_NAMES = {
    "new": "دانستنی", "space": "فضا", "science": "علم", "technology": "فناوری",
    "nature": "طبیعت", "history": "تاریخ", "football": "فوتبال", "world": "جهان",
}
TOPIC_SIGNALS = {
    "space": ("فضا", "سیاره", "کهکشان", "ستاره", "ماه", "مریخ", "خورشید", "نجوم", "کیهان", "سیارک", "سحابی", "زمین"),
    "science": ("فیزیک", "شیمی", "زیست", "سلول", "ژن", "مغز", "اتم", "مولکول", "پزشکی", "ریاضی", "آزمایش", "علم"),
    "technology": ("رایانه", "اینترنت", "هوش مصنوعی", "فناوری", "برنامه نویسی", "شبکه", "پردازنده", "نرم افزار", "سخت افزار", "ربات", "داده", "الگوریتم"),
    "nature": ("حیوان", "جانور", "گیاه", "اقیانوس", "دریا", "جنگل", "اقلیم", "زیست بوم", "پرنده", "پستاندار", "زمین شناسی", "طبیعت"),
    "history": ("تاریخ", "تمدن", "باستان", "امپراتوری", "پادشاه", "جنگ", "باستان شناسی", "ایران باستان", "موزه", "فرهنگ"),
    "football": ("فوتبال", "جام جهانی", "رونالدو", "مسی", "پله", "مارادونا", "لیگ قهرمانان", "باشگاه", "بازیکن", "مربی", "تیم ملی", "ورزشگاه"),
    "world": ("جمعیت", "کشور", "اقتصاد", "تولید ناخالص", "انرژی", "اینترنت", "سلامت", "آموزش", "آب", "جهان", "آمار"),
}

# Emergency bank is intentionally larger, but live sources are preferred first.
FOOTBALL_FALLBACKS = (
    "اولین دوره جام جهانی فوتبال در سال ۱۹۳۰ در اروگوئه برگزار شد و تیم میزبان قهرمان آن دوره شد.",
    "پله تنها بازیکنی است که سه بار قهرمان جام جهانی فوتبال شده است و این رکورد در تاریخ مسابقات ثبت شده است.",
    "جام جهانی فوتبال در نخستین دوره خود با حضور ۱۳ تیم برگزار شد و مسابقات آن در کشور اروگوئه انجام شد.",
    "فینال نخستین دوره جام جهانی فوتبال در سال ۱۹۳۰ بین اروگوئه و آرژانتین برگزار شد و اروگوئه قهرمان شد.",
    "آلمان برای نخستین بار در سال ۱۹۵۴ قهرمان جام جهانی فوتبال شد و در فینال مجارستان را شکست داد.",
    "برزیل نخستین قهرمانی خود در جام جهانی فوتبال را در سال ۱۹۵۸ به دست آورد.",
)
GENERAL_FALLBACKS = (
    ("علم", "نور خورشید حدود ۸ دقیقه و ۲۰ ثانیه طول می‌کشد تا از خورشید به زمین برسد.", "دانش نجوم"),
    ("طبیعت", "اختاپوس سه قلب دارد و خونش به‌دلیل وجود هموسیانین، متمایل به آبی است.", "دانش زیست‌شناسی"),
    ("فناوری", "کد پاسخ سریع برای ذخیره و خواندن سریع داده در قالبی دوبعدی طراحی شده است.", "دانش فناوری"),
    ("فضا", "یک شبانه‌روز خورشیدی روی عطارد حدود ۱۷۶ روز زمینی طول می‌کشد.", "دانش نجوم"),
    ("تاریخ", "واژه الگوریتم از نام دانشمند ایرانی محمد بن موسی خوارزمی گرفته شده است.", "تاریخ علم"),
    ("علم", "آب در فشار معمولی در دمای صفر درجه سلسیوس یخ می‌زند و در صد درجه به جوش می‌آید.", "دانش فیزیک"),
    ("طبیعت", "نهنگ آبی بزرگ‌ترین جانور شناخته‌شده در تاریخ زمین است و طول آن می‌تواند به بیش از ۲۵ متر برسد.", "دانش زیست‌شناسی"),
    ("فناوری", "اولین رایانه‌های الکترونیکی بسیار بزرگ بودند و بخش زیادی از فضای اتاق را اشغال می‌کردند.", "تاریخ فناوری"),
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
            PRIMARY KEY(user_id, fact_key)
        )""")


def remember_user(user_id: int) -> None:
    now = time.time()
    with db() as conn:
        conn.execute("""INSERT INTO users(user_id,first_seen,last_seen) VALUES(?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen""", (user_id, now, now))


def fact_key(text: str, source: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().casefold())
    normalized = re.sub(r"[\u200c\u200d\u200f\u202a-\u202e]", "", normalized)
    return hashlib.sha256(f"{source.casefold()}|{normalized}".encode("utf-8")).hexdigest()


def has_seen(user_id: int, key: str) -> bool:
    with db() as conn:
        row = conn.execute("SELECT 1 FROM seen_facts WHERE user_id=? AND fact_key=? LIMIT 1", (user_id, key)).fetchone()
    return row is not None


def mark_seen(user_id: int, key: str, source: str, category: str) -> None:
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO seen_facts VALUES(?,?,?,?,?)", (user_id, key, time.time(), source, category))


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
    persian = len(re.findall(r"[\u0600-\u06FF]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return persian >= 15 and latin == 0


def usable(text: str) -> bool:
    text = clean(text)
    return MIN_FACT <= len(text) <= MAX_FACT and "@" not in text and "t.me/" not in text.lower() and persian_only(text)


def is_relevant(text: str, topic: str | None) -> bool:
    if topic in (None, "new"):
        return True
    haystack = clean(text)
    return any(signal in haystack for signal in TOPIC_SIGNALS.get(topic, ()))


def snippet_variants(text: str) -> list[str]:
    text = clean(text)
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[\.؟!])\s+", text) if p.strip()]
    if len(parts) <= 1:
        return [text]
    variants: list[str] = []
    windows = [(0, 1), (1, 2), (0, 2), (2, 4), (1, 4), (0, 3)]
    random.shuffle(windows)
    for start, end in windows:
        if start < len(parts):
            candidate = " ".join(parts[start:min(end, len(parts))]).strip()
            if candidate and candidate not in variants:
                variants.append(candidate)
    return variants or [text]


async def get_json(session: aiohttp.ClientSession, url: str, params: dict[str, Any] | None = None) -> Any:
    try:
        async with session.get(url, params=params, allow_redirects=True) as response:
            if response.status != 200:
                return None
            return await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return None


async def source_wikipedia(session: aiohttp.ClientSession, topic: str | None):
    queries = list(TOPICS.get(topic or "new", TOPICS["new"]))
    random.shuffle(queries)
    for query in queries[:8]:
        data = await get_json(session, "https://fa.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrnamespace": 0, "gsrlimit": 20,
            "prop": "extracts|info", "exintro": 1, "explaintext": 1,
            "inprop": "url",
        })
        if not isinstance(data, dict):
            continue
        pages = list(data.get("query", {}).get("pages", {}).values())
        random.shuffle(pages)
        for page in pages:
            title = clean(str(page.get("title", "")))
            extract = clean(str(page.get("extract", "")))
            url = str(page.get("fullurl", ""))
            if not title or not url.startswith("https://fa.wikipedia.org/") or not is_relevant(title + " " + extract, topic):
                continue
            if any(x in title for x in ("کاربر:", "بحث:", "الگو:", "پرونده:", "رده:")):
                continue
            for text in snippet_variants(extract):
                if usable(text):
                    return text, TOPIC_NAMES.get(topic or "new", "دانستنی"), "ویکی‌پدیای فارسی", fact_key(text, url + title)
    return None


async def source_wikipedia_random(session: aiohttp.ClientSession, topic: str | None):
    data = await get_json(session, "https://fa.wikipedia.org/w/api.php", {
        "action": "query", "format": "json", "list": "random",
        "rnnamespace": 0, "rnlimit": 30,
        "prop": "extracts|info", "exintro": 1, "explaintext": 1, "inprop": "url",
    })
    if not isinstance(data, dict):
        return None
    pages = list(data.get("query", {}).get("random", []))
    for item in pages:
        page_id = str(item.get("id", ""))
        if not page_id:
            continue
        page = await get_json(session, "https://fa.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "pageids": page_id,
            "prop": "extracts|info", "exintro": 1, "explaintext": 1, "inprop": "url",
        })
        if not isinstance(page, dict):
            continue
        for obj in page.get("query", {}).get("pages", {}).values():
            title = clean(str(obj.get("title", "")))
            extract = clean(str(obj.get("extract", "")))
            url = str(obj.get("fullurl", ""))
            if not url.startswith("https://fa.wikipedia.org/") or not is_relevant(title + " " + extract, topic):
                continue
            for text in snippet_variants(extract):
                if usable(text):
                    return text, TOPIC_NAMES.get(topic or "new", "دانستنی"), "ویکی‌پدیای فارسی — تصادفی", fact_key(text, url + title)
    return None


async def source_football_wikipedia(session: aiohttp.ClientSession):
    value = await source_wikipedia(session, "football")
    if value and value[1] == "فوتبال":
        return value[0], "فوتبال", "ویکی‌پدیای فارسی — فوتبال", value[3]
    return None


async def source_wikidata_football(session: aiohttp.ClientSession):
    queries = list(TOPICS["football"])
    random.shuffle(queries)
    for query in queries[:6]:
        data = await get_json(session, "https://www.wikidata.org/w/api.php", {
            "action": "wbsearchentities", "search": query, "language": "fa",
            "uselang": "fa", "format": "json", "limit": 20, "type": "item",
        })
        if not isinstance(data, dict):
            continue
        hits = data.get("search", [])
        random.shuffle(hits)
        for hit in hits:
            label = clean(str(hit.get("label", "")))
            desc = clean(str(hit.get("description", "")))
            qid = str(hit.get("id", ""))
            text = clean(f"«{label}» {desc}.")
            if qid and label and desc and is_relevant(text, "football") and usable(text):
                return text, "فوتبال", "ویکی‌داده", fact_key(text, qid)
    return None


async def source_nasa(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "space"):
        return None
    for _ in range(5):
        stamp = time.gmtime()
        days_back = random.randint(1, 2500)
        day = time.strftime("%Y-%m-%d", time.gmtime(time.mktime(stamp) - days_back * 86400))
        data = await get_json(session, "https://api.nasa.gov/planetary/apod", {
            "api_key": os.getenv("NASA_API_KEY", "DEMO_KEY"), "date": day,
        })
        if not isinstance(data, dict) or not data.get("date"):
            continue
        text = f"ناسا در آرشیو تصویر نجومی روز، برای تاریخ {data['date']} یک محتوای نجومی ثبت کرده است."
        if usable(text):
            return text, "فضا", "ناسا", fact_key(text, str(data["date"]))
    return None


WORLD_COUNTRIES = {
    "IRN": "ایران", "FRA": "فرانسه", "DEU": "آلمان", "BRA": "برزیل", "JPN": "ژاپن",
    "IND": "هند", "CAN": "کانادا", "ESP": "اسپانیا", "ITA": "ایتالیا", "TUR": "ترکیه",
    "EGY": "مصر", "AUS": "استرالیا", "MEX": "مکزیک", "KOR": "کره جنوبی", "ZAF": "آفریقای جنوبی",
}
WORLD_INDICATORS = {
    "SP.POP.TOTL": "جمعیت",
    "NY.GDP.MKTP.CD": "تولید ناخالص داخلی",
    "SP.DYN.LE00.IN": "امید به زندگی",
    "IT.NET.USER.ZS": "درصد استفاده از اینترنت",
    "EG.ELC.ACCS.ZS": "درصد دسترسی به برق",
}


async def source_world_bank(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "world"):
        return None
    indicator, indicator_name = random.choice(list(WORLD_INDICATORS.items()))
    code, country = random.choice(list(WORLD_COUNTRIES.items()))
    data = await get_json(session, f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}", {
        "format": "json", "per_page": 30,
    })
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
        return None
    rows = [row for row in data[1] if row.get("value") is not None]
    if not rows:
        return None
    row = random.choice(rows)
    value = row.get("value")
    try:
        if indicator in ("SP.DYN.LE00.IN", "IT.NET.USER.ZS", "EG.ELC.ACCS.ZS"):
            number = f"{float(value):.2f}".replace(".", "٫")
        elif indicator == "NY.GDP.MKTP.CD":
            number = f"{int(value):,}".replace(",", "،")
        else:
            number = f"{int(value):,}".replace(",", "،")
    except (TypeError, ValueError):
        return None
    unit = " درصد" if indicator in ("IT.NET.USER.ZS", "EG.ELC.ACCS.ZS") else ""
    text = f"طبق داده‌های بانک جهانی، {indicator_name} {country} در سال {row.get('date')} برابر با حدود {number}{unit} ثبت شده است."
    if usable(text):
        return text, "جهان", "بانک جهانی", fact_key(text, f"{code}:{indicator}:{row.get('date')}")
    return None


async def source_usgs(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "nature"):
        return None
    feeds = (
        "significant_month",
        "4.5_month",
        "2.5_month",
        "1.0_month",
    )
    feed = random.choice(feeds)
    data = await get_json(session, f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson")
    if not isinstance(data, dict) or not data.get("features"):
        return None
    item = random.choice(data["features"])
    props = item.get("properties", {})
    magnitude = props.get("mag")
    event_id = str(item.get("id", ""))
    if magnitude is None or not event_id:
        return None
    text = f"در داده‌های سازمان زمین‌شناسی آمریکا، یک زمین‌لرزه با بزرگای حدود {float(magnitude):.1f} ثبت شده است."
    if usable(text):
        return text, "طبیعت", "سازمان زمین‌شناسی آمریکا", fact_key(text, event_id)
    return None


async def source_general(session: aiohttp.ClientSession, topic: str | None):
    candidates: list[Callable[..., Awaitable[Any]]] = [source_wikipedia, source_wikipedia_random]
    if topic in (None, "space"):
        candidates.append(source_nasa)
    if topic in (None, "world"):
        candidates.append(source_world_bank)
    if topic in (None, "nature"):
        candidates.append(source_usgs)
    random.shuffle(candidates)
    for loader in candidates:
        value = await loader(session, topic)
        if value and usable(value[0]) and is_relevant(value[0], topic):
            return value
    return None


async def live_fact(topic: str | None):
    async with aiohttp.ClientSession(timeout=TIMEOUT, headers={"User-Agent": "AmirFacts/4.0"}) as session:
        if topic == "football":
            candidates = [source_football_wikipedia, source_wikidata_football, lambda s: source_wikipedia_random(s, "football")]
        else:
            candidates = [lambda s: source_general(s, topic), lambda s: source_wikipedia_random(s, topic)]
        random.shuffle(candidates)
        for loader in candidates:
            value = await loader(session)
            if value and usable(value[0]) and (topic != "football" or value[1] == "فوتبال"):
                return value
    return None


def football_fallback(user_id: int):
    pool = list(FOOTBALL_FALLBACKS)
    random.shuffle(pool)
    for text in pool:
        source = "مجموعه پشتیبان فوتبال"
        key = fact_key(text, source)
        if usable(text) and not has_seen(user_id, key):
            return text, "فوتبال", source, key
    return None


def general_fallback(user_id: int, topic: str | None):
    pool = list(GENERAL_FALLBACKS)
    random.shuffle(pool)
    for category, text, source in pool:
        if topic and category != TOPIC_NAMES.get(topic):
            continue
        key = fact_key(text, source)
        if usable(text) and not has_seen(user_id, key):
            return text, category, source, key
    return None


async def get_new_fact(user_id: int, topic: str | None = None):
    remember_user(user_id)
    # Multiple independent source attempts dramatically reduce false "nothing found" states.
    for _ in range(8):
        value = await live_fact(topic)
        if value and usable(value[0]) and is_relevant(value[0], topic) and not has_seen(user_id, value[3]):
            return value
    if topic == "football":
        return football_fallback(user_id)
    value = general_fallback(user_id, topic)
    if value:
        return value
    # One more deep-source pass before ever returning an empty result.
    for _ in range(4):
        value = await live_fact(topic)
        if value and usable(value[0]) and is_relevant(value[0], topic) and not has_seen(user_id, value[3]):
            return value
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
        (("🎲 فکت جدید", "fact:new"), ("⚽ فوتبال", "fact:football")),
        (("🌌 فضا", "fact:space"), ("🧠 علم", "fact:science")),
        (("💻 فناوری", "fact:technology"), ("🌿 طبیعت", "fact:nature")),
        (("🏛️ تاریخ", "fact:history"), ("🌍 جهان", "fact:world")),
    )
    for row in rows:
        kb.add(*[types.InlineKeyboardButton(text, callback_data=data) for text, data in row])
    kb.add(types.InlineKeyboardButton("📊 آمار من", callback_data="stats"))
    return kb


def render(text: str, category: str, source: str) -> str:
    return f"✨ <b>فکت جدید</b>\n\n{html.escape(text)}\n\n🏷️ <b>دسته:</b> {html.escape(category)}\n📚 <b>منبع:</b> {html.escape(source)}"


if not BOT_TOKEN or BOT_TOKEN == "TOKEN RO INJA BEZAR":
    raise RuntimeError("Telegram bot token is missing")

bot = AsyncTeleBot(BOT_TOKEN, parse_mode="HTML")


@bot.message_handler(commands=["start", "help"])
async def start_handler(message: types.Message) -> None:
    remember_user(message.from_user.id)
    await bot.send_message(message.chat.id, "🚀 <b>AmirFacts</b>\n\nفکت‌های فارسی، منبع‌دار و غیرتکراری. ⚽ فوتبال هم اضافه شده.\n\nهر بار قبل از پاسخ، از چند منبع دنبال مورد تازه می‌گردم.", reply_markup=keyboard())


async def send_fact(chat_id: int, user_id: int, topic: str | None = None) -> None:
    if not allowed(user_id):
        await bot.send_message(chat_id, "⏳ یه کم آروم‌تر 😄")
        return
    await bot.send_dice(chat_id, emoji="🎲")
    status = await bot.send_message(chat_id, "🔎 <i>از چند منبع دنبال یک فکت تازه و غیرتکراری می‌گردم...</i>")
    result = await get_new_fact(user_id, topic)
    if not result:
        await bot.edit_message_text("🔄 منابع در دسترس نبودند؛ دوباره بزن تا از دور بعدی منابع یک فکت تازه بگیرم.", chat_id=chat_id, message_id=status.message_id, reply_markup=keyboard())
        return
    text, category, source, key = result
    if not usable(text) or (topic == "football" and category != "فوتبال"):
        await bot.edit_message_text("🔄 این مورد فیلتر شد؛ دارم مورد دیگری پیدا می‌کنم.", chat_id=chat_id, message_id=status.message_id, reply_markup=keyboard())
        return
    mark_seen(user_id, key, source, category)
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
    topic = call.data.split(":", 1)[1]
    if topic in TOPICS:
        await send_fact(call.message.chat.id, call.from_user.id, topic)


@bot.callback_query_handler(func=lambda call: call.data == "stats")
async def stats_callback(call: types.CallbackQuery) -> None:
    await bot.answer_callback_query(call.id)
    await send_stats(call.message.chat.id, call.from_user.id)


async def main() -> None:
    init_db()
    print("AmirFacts polling is ON.")
    await bot.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    asyncio.run(main())
