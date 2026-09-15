# -*- coding: utf-8 -*-
"""✨ AmirFacts — Persian Daily Facts Telegram Bot.

Multi-source fact bot with per-user no-repeat history, SQLite persistence,
source attribution, graceful fallbacks, and strong network hygiene.
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
from typing import Any

import aiohttp
from telebot import types
from telebot.async_telebot import AsyncTeleBot

# =========================================================
# TOKEN — KEEP THIS SECTION
# =========================================================
BOT_TOKEN = "TOKEN RO INJA BEZAR"
BOT_TOKEN = os.getenv("AMIRXPROXY_BOT_TOKEN", BOT_TOKEN)
# =========================================================

DB_PATH = Path(os.getenv("AMIRFACTS_DB", "amirfacts.sqlite3"))
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=12, connect=5, sock_read=8)
MAX_FACT_LENGTH = 650
MIN_FACT_LENGTH = 90
USER_COOLDOWN_SECONDS = 2.0
MAX_SOURCE_ATTEMPTS = 10

TOPICS: dict[str, tuple[str, ...]] = {
    "space": ("فضا", "کهکشان", "سیاره", "ستاره", "ماه", "NASA"),
    "science": ("فیزیک", "شیمی", "زیست", "علم", "مغز", "ژنتیک"),
    "technology": ("رایانه", "اینترنت", "هوش مصنوعی", "فناوری", "برنامه نویسی"),
    "nature": ("حیوانات", "اقیانوس", "طبیعت", "گیاه", "جانور", "زلزله"),
    "history": ("تاریخ", "تمدن", "باستان", "اختراع", "اکتشاف"),
    "world": ("کشورها", "جمعیت", "اقتصاد", "آموزش", "سلامت", "توسعه"),
}

TOPIC_NAMES = {
    "space": "فضا",
    "science": "علم",
    "technology": "فناوری",
    "nature": "طبیعت",
    "history": "تاریخ",
    "world": "جهان",
}

FALLBACK_FACTS: tuple[tuple[str, str, str], ...] = (
    ("علم", "نور خورشید برای رسیدن به زمین حدود ۸ دقیقه و ۲۰ ثانیه در راه است.", "NASA / دانش عمومی"),
    ("فضا", "یک شبانه‌روز خورشیدی روی عطارد حدود ۱۷۶ روز زمینی طول می‌کشد.", "NASA / دانش نجوم"),
    ("طبیعت", "اختاپوس سه قلب دارد و خونش به‌دلیل وجود هموسیانین، رنگی متمایل به آبی دارد.", "دانش زیست‌شناسی"),
    ("علم", "بدن انسان برای حفظ تعادل، اطلاعات چشم، گوش داخلی و گیرنده‌های عضلات و مفاصل را با هم ترکیب می‌کند.", "دانش پزشکی پایه"),
    ("فناوری", "کد QR می‌تواند داده را در دو بُعد ذخیره کند و برای خواندن سریع اطلاعات طراحی شده است.", "استاندارد QR"),
    ("تاریخ", "واژه «الگوریتم» ریشه در نام دانشمند ایرانی محمد بن موسی خوارزمی دارد.", "دانش تاریخ علم"),
    ("علم", "در خلأ، موج صوتی معمولی نمی‌تواند مثل زمین منتشر شود چون محیط مادی کافی برای انتقالش وجود ندارد.", "فیزیک"),
    ("طبیعت", "زنبورهای عسل از الگوی حرکتی ویژه‌ای برای انتقال اطلاعات درباره جهت منابع غذایی استفاده می‌کنند.", "زیست‌شناسی"),
)


class FactError(Exception):
    pass


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    with db_connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS seen_facts (
                user_id INTEGER NOT NULL,
                fact_key TEXT NOT NULL,
                created_at REAL NOT NULL,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                PRIMARY KEY (user_id, fact_key)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL
            )"""
        )
        conn.commit()


def remember_user(user_id: int) -> None:
    now = time.time()
    with db_connect() as conn:
        conn.execute(
            """INSERT INTO users(user_id, first_seen, last_seen)
               VALUES(?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen""",
            (user_id, now, now),
        )
        conn.commit()


def has_seen(user_id: int, key: str) -> bool:
    with db_connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM seen_facts WHERE user_id=? AND fact_key=? LIMIT 1",
            (user_id, key),
        ).fetchone()
    return row is not None


def mark_seen(user_id: int, key: str, source: str = "", category: str = "") -> None:
    with db_connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO seen_facts
               (user_id, fact_key, created_at, source, category)
               VALUES(?, ?, ?, ?, ?)""",
            (user_id, key, time.time(), source, category),
        )
        conn.commit()


def seen_count(user_id: int) -> int:
    with db_connect() as conn:
        row = conn.execute("SELECT COUNT(*) FROM seen_facts WHERE user_id=?", (user_id,)).fetchone()
    return int(row[0] if row else 0)


def fact_key(text: str, source: str) -> str:
    normalized = re.sub(r"\s+", " ", text.casefold().strip())
    return hashlib.sha256(f"{source.casefold()}|{normalized}".encode("utf-8")).hexdigest()


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\[[0-9۰-۹]+\]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" \t\r\n–—")
    if len(text) > MAX_FACT_LENGTH:
        cut = text[:MAX_FACT_LENGTH].rsplit(" ", 1)[0]
        text = cut + "…"
    return text


def usable_fact(text: str) -> bool:
    if not (MIN_FACT_LENGTH <= len(text) <= MAX_FACT_LENGTH + 1):
        return False
    junk = ("صفحهٔ ابهام", "ابهام‌زدایی", "این مقاله", "فهرست")
    return not any(marker in text[:120] for marker in junk)


async def http_json(session: aiohttp.ClientSession, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        async with session.get(url, params=params, allow_redirects=True) as response:
            if response.status != 200:
                return None
            return await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return None


async def fetch_wikimedia_fact(session: aiohttp.ClientSession, topic: str | None) -> tuple[str, str, str] | None:
    terms = TOPICS.get(topic or "") or TOPICS["science"]
    query = random.choice(terms)
    data = await http_json(
        session,
        "https://fa.wikipedia.org/w/api.php",
        params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrnamespace": 0, "gsrlimit": 10,
            "prop": "extracts|info", "exintro": 1, "explaintext": 1,
            "inprop": "url",
        },
    )
    if not data:
        return None
    pages = list(data.get("query", {}).get("pages", {}).values())
    random.shuffle(pages)
    for page in pages:
        title = str(page.get("title", "")).strip()
        text = clean_text(str(page.get("extract", "")))
        url = str(page.get("fullurl", "")).strip()
        if not title or not url or not usable_fact(text):
            continue
        if any(x in title for x in ("کاربر:", "بحث:", "الگو:", "پرونده:", "رده:")):
            continue
        return text, title, url
    return None


async def fetch_wikidata_fact(session: aiohttp.ClientSession, topic: str | None) -> tuple[str, str, str] | None:
    terms = TOPICS.get(topic or "") or TOPICS["science"]
    term = random.choice(terms)
    data = await http_json(
        session,
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities", "search": term, "language": "fa",
            "format": "json", "limit": 8, "type": "item",
        },
    )
    if not data:
        return None
    hits = data.get("search", [])
    random.shuffle(hits)
    for hit in hits:
        label = clean_text(str(hit.get("label", "")))
        desc = clean_text(str(hit.get("description", "")))
        qid = str(hit.get("id", ""))
        if label and desc and qid and usable_fact(desc):
            return f"«{label}» {desc}.", label, f"https://www.wikidata.org/wiki/{qid}"
    return None


async def fetch_nasa_fact(session: aiohttp.ClientSession, topic: str | None) -> tuple[str, str, str] | None:
    if topic not in (None, "space"):
        return None
    data = await http_json(
        session,
        "https://api.nasa.gov/planetary/apod",
        params={"api_key": os.getenv("NASA_API_KEY", "DEMO_KEY")},
    )
    if not data:
        return None
    title = clean_text(str(data.get("title", "")))
    explanation = clean_text(str(data.get("explanation", "")))
    url = str(data.get("url", "https://apod.nasa.gov/"))
    if not title or not usable_fact(explanation):
        return None
    sentence = explanation.split(". ")[0].strip()
    if len(sentence) < MIN_FACT_LENGTH:
        sentence = explanation
    return sentence, title, url


async def fetch_world_bank_fact(session: aiohttp.ClientSession, topic: str | None) -> tuple[str, str, str] | None:
    if topic not in (None, "world"):
        return None
    indicators = (
        ("SP.POP.TOTL", "جمعیت"),
        ("SP.URB.TOTL.IN.ZS", "جمعیت شهری"),
        ("SE.XPD.TOTL.GD.ZS", "هزینه آموزش"),
    )
    indicator, label = random.choice(indicators)
    countries = ("IRN", "JPN", "FRA", "DEU", "BRA", "IND", "CAN", "AUS", "KOR", "TUR")
    country = random.choice(countries)
    data = await http_json(session, f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}", params={"format": "json", "per_page": 10})
    if not isinstance(data, list) or len(data) < 2:
        return None
    rows = [x for x in data[1] if x.get("value") is not None]
    if not rows:
        return None
    row = rows[0]
    country_name = str(row.get("country", {}).get("value", country))
    year = str(row.get("date", ""))
    value = row.get("value")
    try:
        if indicator == "SP.POP.TOTL":
            value_text = f"{int(value):,} نفر"
        else:
            value_text = f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return None
    text = f"در داده‌های بانک جهانی برای {country_name} در سال {year}، شاخص «{label}» برابر با {value_text} ثبت شده است."
    return text, f"{label} در {country_name}", "https://data.worldbank.org/"


async def fetch_usgs_fact(session: aiohttp.ClientSession, topic: str | None) -> tuple[str, str, str] | None:
    if topic not in (None, "nature"):
        return None
    data = await http_json(
        session,
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
    )
    if not data:
        return None
    features = data.get("features", [])
    if not features:
        return None
    item = random.choice(features)
    props = item.get("properties", {})
    place = clean_text(str(props.get("place", "")))
    magnitude = props.get("mag")
    when_ms = props.get("time")
    if not place or magnitude is None:
        return None
    text = f"یکی از زمین‌لرزه‌های مهم ثبت‌شده توسط USGS در ماه اخیر در «{place}» بزرگای حدود {float(magnitude):.1f} داشته است."
    return text, "یک زمین‌لرزه مهم اخیر", "https://earthquake.usgs.gov/"


async def fetch_fact_from_sources(topic: str | None) -> tuple[str, str, str, str] | None:
    headers = {"User-Agent": "AmirFacts/2.0 (+https://github.com/Amirho33ein7/amirbot)"}
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT, headers=headers) as session:
        sources = [
            fetch_wikimedia_fact,
            fetch_wikidata_fact,
            fetch_nasa_fact,
            fetch_world_bank_fact,
            fetch_usgs_fact,
        ]
        random.shuffle(sources)
        for _ in range(MAX_SOURCE_ATTEMPTS):
            source_fn = random.choice(sources)
            try:
                result = await source_fn(session, topic)
            except Exception:
                continue
            if not result:
                continue
            text, title, url = result
            key = fact_key(text, url)
            return text, title, url, key
    return None


def fallback_fact(user_id: int, topic: str | None) -> tuple[str, str, str, str] | None:
    pool = [x for x in FALLBACK_FACTS if topic is None or TOPIC_NAMES.get(topic) == x[0]] or list(FALLBACK_FACTS)
    random.shuffle(pool)
    for category, text, source in pool:
        key = fact_key(text, source)
        if not has_seen(user_id, key):
            return text, category, source, key
    return None


_last_action: dict[int, float] = {}


def rate_allowed(user_id: int) -> bool:
    now = time.monotonic()
    last = _last_action.get(user_id, 0.0)
    if now - last < USER_COOLDOWN_SECONDS:
        return False
    _last_action[user_id] = now
    return True


async def get_new_fact(user_id: int, topic: str | None = None) -> tuple[str, str, str, str] | None:
    remember_user(user_id)
    for _ in range(MAX_SOURCE_ATTEMPTS):
        candidate = await fetch_fact_from_sources(topic)
        if not candidate:
            break
        text, title, url, key = candidate
        if not has_seen(user_id, key):
            category = TOPIC_NAMES.get(topic, "دانستنی")
            return text, category, f"{title}", key
    return fallback_fact(user_id, topic)


def make_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🎲 فکت جدید", callback_data="fact:new"),
        types.InlineKeyboardButton("🌌 فضا", callback_data="fact:space"),
        types.InlineKeyboardButton("🧠 علم", callback_data="fact:science"),
        types.InlineKeyboardButton("💻 تکنولوژی", callback_data="fact:technology"),
        types.InlineKeyboardButton("🌿 طبیعت", callback_data="fact:nature"),
        types.InlineKeyboardButton("🏛️ تاریخ", callback_data="fact:history"),
        types.InlineKeyboardButton("🌍 جهان", callback_data="fact:world"),
        types.InlineKeyboardButton("📊 آمار من", callback_data="stats"),
    )
    return keyboard


def make_fact_text(text: str, category: str, source: str) -> str:
    return (
        "✨ <b>AMIR FACTS</b>\n\n"
        f"💡 {html.escape(text)}\n\n"
        f"🏷️ <b>دسته:</b> {html.escape(category)}\n"
        f"📚 <b>منبع:</b> {html.escape(source)}\n\n"
        "🎲 برای یه فکت تازه دوباره بزن!"
    )


if not BOT_TOKEN or BOT_TOKEN == "TOKEN RO INJA BEZAR":
    raise RuntimeError("Telegram bot token is missing")

bot = AsyncTeleBot(BOT_TOKEN, parse_mode="HTML")

WELCOME = (
    "🧠 <b>AMIR FACTS</b>\n\n"
    "هر بار یه دانستنی کوتاه، خفن و منبع‌دار از چند منبع مختلف پیدا می‌کنم.\n"
    "فکت‌های دیده‌شده برای هر کاربر ذخیره می‌شن تا بی‌جهت تکراری نباشن.\n\n"
    "🎲 بزن بریم!"
)


async def send_stats(chat_id: int, user_id: int) -> None:
    count = seen_count(user_id)
    await bot.send_message(
        chat_id,
        f"📊 <b>آمار تو</b>\n\n🧠 فکت دیده‌شده: <b>{count}</b>\n🔥 حالت: ضدتکرار فعال",
        reply_markup=make_keyboard(),
    )


async def send_fact(chat_id: int, user_id: int, topic: str | None = None) -> None:
    if not rate_allowed(user_id):
        await bot.send_message(chat_id, "⏳ یه کوچولو آروم‌تر 😄 فکت بعدی همین الان میاد.")
        return
    await bot.send_dice(chat_id, emoji="🎲")
    status = await bot.send_message(chat_id, "🔍 <i>چند منبع رو دارم بررسی می‌کنم...</i>")
    result = await get_new_fact(user_id, topic)
    if not result:
        await bot.edit_message_text(
            "😵‍💫 فعلاً فکت تازه‌ای پیدا نشد. بعداً دوباره امتحان کن.",
            chat_id=chat_id,
            message_id=status.message_id,
        )
        return
    text, category, source, key = result
    mark_seen(user_id, key, source=source, category=category)
    rendered = make_fact_text(text, category, source)
    try:
        await bot.edit_message_text(
            rendered,
            chat_id=chat_id,
            message_id=status.message_id,
            reply_markup=make_keyboard(),
        )
    except Exception:
        await bot.send_message(chat_id, rendered, reply_markup=make_keyboard())


@bot.message_handler(commands=["start", "help"])
async def start_handler(message: types.Message) -> None:
    remember_user(message.from_user.id)
    await bot.send_message(message.chat.id, WELCOME, reply_markup=make_keyboard())


@bot.message_handler(commands=["fact"])
async def fact_command(message: types.Message) -> None:
    await send_fact(message.chat.id, message.from_user.id)


@bot.message_handler(commands=["stats"])
async def stats_command(message: types.Message) -> None:
    await send_stats(message.chat.id, message.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "fact:new")
async def new_fact_callback(call: types.CallbackQuery) -> None:
    await bot.answer_callback_query(call.id)
    await send_fact(call.message.chat.id, call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("fact:") and call.data != "fact:new")
async def topic_callback(call: types.CallbackQuery) -> None:
    await bot.answer_callback_query(call.id)
    topic = call.data.split(":", 1)[1]
    if topic not in TOPIC_NAMES:
        await bot.send_message(call.message.chat.id, "❌ موضوع ناشناخته است.")
        return
    await send_fact(call.message.chat.id, call.from_user.id, topic)


@bot.callback_query_handler(func=lambda call: call.data == "stats")
async def stats_callback(call: types.CallbackQuery) -> None:
    await bot.answer_callback_query(call.id)
    await send_stats(call.message.chat.id, call.from_user.id)


async def main() -> None:
    init_db()
    print("✨ AmirFacts is running...")
    await bot.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    asyncio.run(main())
