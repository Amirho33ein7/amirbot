# -*- coding: utf-8 -*-
"""✨ AmirFacts — Telegram Daily Facts Bot

A self-contained Persian Telegram bot that:
- sends fun, useful facts;
- pulls fresh Persian knowledge from Wikipedia when possible;
- remembers sent facts in SQLite per user;
- uses Telegram's animated dice as a playful reveal effect;
- keeps the existing GitHub Actions token secret compatible.
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
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)
MAX_FACT_LENGTH = 520
USER_COOLDOWN_SECONDS = 2

TOPICS: dict[str, tuple[str, ...]] = {
    "space": ("فضا", "کهکشان", "سیاره", "ستاره", "ماه"),
    "science": ("فیزیک", "شیمی", "زیست", "علم", "مغز"),
    "technology": ("رایانه", "اینترنت", "هوش مصنوعی", "فناوری", "برنامه‌نویسی"),
    "nature": ("حیوانات", "اقیانوس", "طبیعت", "گیاه", "جانور"),
    "history": ("تاریخ", "تمدن", "باستان", "اختراع", "اکتشاف"),
}

# Fallback pack: used only if the public source is unavailable.
FALLBACK_FACTS: tuple[tuple[str, str], ...] = (
    ("علم", "صدای انسان فقط از تارهای صوتی ساخته نمی‌شود؛ شکل دهان، زبان و حفره‌های بدن هم در رنگ و جنس صدا نقش دارند."),
    ("فضا", "نور خورشید حدود ۸ دقیقه و ۲۰ ثانیه در راه است تا به زمین برسد."),
    ("فناوری", "اولین وب‌سایت جهان توسط تیم CERN ساخته شد و هدف اولیه‌اش اشتراک‌گذاری اطلاعات پروژه World Wide Web بود."),
    ("طبیعت", "اختاپوس‌ها سه قلب دارند و رنگ خونشان به‌دلیل هموسیانینِ دارای مس، متمایل به آبی است."),
    ("تاریخ", "واژه «الگوریتم» از نام دانشمند ایرانی، محمد بن موسی خوارزمی، گرفته شده است."),
    ("علم", "در خلأ، مانند فضای بیرون از جو، صدا نمی‌تواند مثل روی زمین منتشر شود چون محیط مادی کافی برای انتقال موج صوتی وجود ندارد."),
    ("فناوری", "کدهای QR برای خواندن سریع اطلاعات طراحی شدند و می‌توانند داده را در دو بُعد ذخیره کنند."),
    ("فضا", "یک شبانه‌روز خورشیدی روی عطارد حدود ۱۷۶ روز زمینی طول می‌کشد."),
    ("طبیعت", "زنبورهای عسل برای نشان دادن جهت و فاصله منابع غذایی به هم «رقص» انجام می‌دهند."),
    ("علم", "بدن انسان برای حفظ تعادل از اطلاعات چشم، گوش داخلی و حسگرهای موجود در عضلات و مفاصل به‌صورت همزمان استفاده می‌کند."),
    ("تاریخ", "قدیمی‌ترین نمونه‌های شناخته‌شده شیشه‌سازی به تمدن‌های باستانی خاورمیانه و مصر برمی‌گردند."),
    ("فناوری", "یک فایل متنی ساده می‌تواند با فشرده‌سازی درست به شکل چشمگیری کوچک‌تر شود، چون الگوهای تکراری در متن زیادند."),
)


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_facts (
                user_id INTEGER NOT NULL,
                fact_key TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (user_id, fact_key)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL
            )
            """
        )


def remember_user(user_id: int) -> None:
    now = time.time()
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO users(user_id, first_seen, last_seen)
            VALUES(?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen
            """,
            (user_id, now, now),
        )


def has_seen(user_id: int, key: str) -> bool:
    with db_connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM seen_facts WHERE user_id=? AND fact_key=? LIMIT 1",
            (user_id, key),
        ).fetchone()
    return row is not None


def mark_seen(user_id: int, key: str) -> None:
    with db_connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen_facts(user_id, fact_key, created_at) VALUES(?, ?, ?)",
            (user_id, key, time.time()),
        )


def fact_key(text: str, source: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(f"{source}|{normalized}".encode("utf-8")).hexdigest()


def clean_extract(text: str) -> str:
    text = re.sub(r"\[[0-9۰-۹]+\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_FACT_LENGTH:
        text = text[:MAX_FACT_LENGTH].rsplit(" ", 1)[0] + "…"
    return text


def make_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🎲 فکت جدید", callback_data="fact:new"),
        types.InlineKeyboardButton("🌌 فکت فضایی", callback_data="fact:space"),
    )
    keyboard.add(
        types.InlineKeyboardButton("🧠 علم", callback_data="fact:science"),
        types.InlineKeyboardButton("💻 تکنولوژی", callback_data="fact:technology"),
    )
    keyboard.add(
        types.InlineKeyboardButton("🌿 طبیعت", callback_data="fact:nature"),
        types.InlineKeyboardButton("🏛️ تاریخ", callback_data="fact:history"),
    )
    keyboard.add(types.InlineKeyboardButton("📊 وضعیت من", callback_data="stats"))
    return keyboard


def make_fact_text(text: str, category: str, source: str) -> str:
    return (
        "✨ <b>یه فکت باحال برای تو</b>\n\n"
        f"{html.escape(text)}\n\n"
        f"🏷️ <b>دسته:</b> {html.escape(category)}\n"
        f"🔎 <b>منبع:</b> {html.escape(source)}\n\n"
        "👇 برای یکی دیگه بزن"
    )


async def fetch_wikipedia_fact(topic: str | None = None) -> tuple[str, str, str] | None:
    terms = TOPICS.get(topic)
    query = random.choice(terms) if terms else random.choice(tuple(sum(TOPICS.values(), ())))
    api_url = "https://fa.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 0,
        "gsrlimit": 8,
        "prop": "extracts|info",
        "exintro": 1,
        "explaintext": 1,
        "inprop": "url",
    }
    headers = {"User-Agent": "AmirFactsBot/1.0 (+Telegram bot)"}

    try:
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT, headers=headers) as session:
            async with session.get(api_url, params=params) as response:
                response.raise_for_status()
                data: dict[str, Any] = await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return None

    pages = list(data.get("query", {}).get("pages", {}).values())
    candidates: list[tuple[str, str, str]] = []
    for page in pages:
        title = str(page.get("title", "")).strip()
        extract = clean_extract(str(page.get("extract", "")))
        url = str(page.get("fullurl", "")).strip()
        if not title or len(extract) < 90 or not url:
            continue
        blocked = ("ویکی", "کاربر:", "بحث:", "الگو:", "پرونده:")
        if any(token in title for token in blocked):
            continue
        candidates.append((extract, title, url))

    return random.choice(candidates) if candidates else None


def pick_fallback(user_id: int, topic: str | None) -> tuple[str, str, str] | None:
    pool = [item for item in FALLBACK_FACTS if topic is None or item[0] == TOPIC_NAMES.get(topic, "")]
    if not pool:
        pool = list(FALLBACK_FACTS)
    random.shuffle(pool)
    for category, text in pool:
        source = "پایگاه داخلی AmirFacts"
        key = fact_key(text, source)
        if not has_seen(user_id, key):
            return text, category, source
    return None


TOPIC_NAMES = {
    "space": "فضا",
    "science": "علم",
    "technology": "فناوری",
    "nature": "طبیعت",
    "history": "تاریخ",
}

_last_action: dict[int, float] = {}


def rate_allowed(user_id: int) -> bool:
    now = time.time()
    last = _last_action.get(user_id, 0.0)
    if now - last < USER_COOLDOWN_SECONDS:
        return False
    _last_action[user_id] = now
    return True


async def get_new_fact(user_id: int, topic: str | None = None) -> tuple[str, str, str, str] | None:
    remember_user(user_id)
    for _ in range(6):
        online = await fetch_wikipedia_fact(topic)
        if online:
            text, title, url = online
            category = TOPIC_NAMES.get(topic, "دانستنی")
            key = fact_key(text, url)
            if not has_seen(user_id, key):
                return text, category, f"ویکی‌پدیای فارسی — {title}", key

    fallback = pick_fallback(user_id, topic)
    if fallback:
        text, category, source = fallback
        return text, category, source, fact_key(text, source)
    return None


if not BOT_TOKEN or BOT_TOKEN == "TOKEN RO INJA BEZAR":
    raise RuntimeError("Telegram bot token is missing")

bot = AsyncTeleBot(BOT_TOKEN, parse_mode="HTML")

WELCOME = (
    "🚀 <b>AmirFacts</b>\n\n"
    "اینجا هر بار یه دانستنی کوتاه، عجیب یا کاربردی می‌گیری؛ "
    "و بات فکت‌های دیده‌شده رو برای هر کاربر یادش می‌مونه.\n\n"
    "🎲 روی «فکت جدید» بزن و ببین امروز چی یاد می‌گیری!"
)


async def send_stats(chat_id: int, user_id: int) -> None:
    with db_connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM seen_facts WHERE user_id=?",
            (user_id,),
        ).fetchone()
    count = int(row[0] if row else 0)
    await bot.send_message(
        chat_id,
        f"📊 <b>آمار تو</b>\n\n🧠 فکت‌های دیده‌شده: <b>{count}</b>\n🎯 هدف: هر بار یه چیز جدید یاد بگیری!",
        reply_markup=make_keyboard(),
    )


async def send_fact(chat_id: int, user_id: int, topic: str | None = None) -> None:
    if not rate_allowed(user_id):
        await bot.send_message(chat_id, "⏳ یه ثانیه آروم‌تر! فکت بعدی رو همین الان نمی‌فرستم 😄")
        return

    await bot.send_dice(chat_id, emoji="🎲")
    status = await bot.send_message(chat_id, "🔎 <i>دارم دنبال یه فکت تازه می‌گردم...</i>")
    result = await get_new_fact(user_id, topic)

    if not result:
        await bot.edit_message_text(
            "😅 فعلاً فکت تازه‌ای پیدا نکردم. چند لحظه بعد دوباره امتحان کن.",
            chat_id=chat_id,
            message_id=status.message_id,
        )
        return

    text, category, source, key = result
    mark_seen(user_id, key)
    try:
        await bot.edit_message_text(
            make_fact_text(text, category, source),
            chat_id=chat_id,
            message_id=status.message_id,
            reply_markup=make_keyboard(),
        )
    except Exception:
        await bot.send_message(chat_id, make_fact_text(text, category, source), reply_markup=make_keyboard())


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


@bot.callback_query_handler(func=lambda call: call.data.startswith("fact:"))
async def topic_callback(call: types.CallbackQuery) -> None:
    await bot.answer_callback_query(call.id)
    topic = call.data.split(":", 1)[1]
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
