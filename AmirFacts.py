# -*- coding: utf-8 -*-
"""AmirFacts — Persian multi-source Telegram facts bot.

Production polling is intentionally OFF. GitHub Actions performs the full
validation suite, and the Telegram token is kept compatible with the
existing repository secret.
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
TIMEOUT = aiohttp.ClientTimeout(total=12, connect=5, sock_read=8)
MIN_FACT = 70
MAX_FACT = 650
COOLDOWN = 2.0

TOPICS: dict[str, tuple[str, ...]] = {
    "new": ("دانستنی", "اختراع", "کشف", "علم"),
    "space": ("فضا", "سیاره", "کهکشان", "ستاره", "ماه"),
    "science": ("فیزیک", "شیمی", "زیست", "مغز", "ژنتیک"),
    "technology": ("رایانه", "اینترنت", "هوش مصنوعی", "فناوری", "برنامه نویسی"),
    "nature": ("حیوانات", "اقیانوس", "طبیعت", "گیاه", "جانور"),
    "history": ("تاریخ", "تمدن", "باستان", "اختراع", "اکتشاف"),
    "football": ("فوتبال", "جام جهانی", "رونالدو", "مسی", "پله", "مارادونا"),
    "world": ("جمعیت", "کشورها", "اقتصاد", "آمار", "جهان"),
}
TOPIC_NAMES = {
    "new": "دانستنی",
    "space": "فضا",
    "science": "علم",
    "technology": "فناوری",
    "nature": "طبیعت",
    "history": "تاریخ",
    "football": "فوتبال",
    "world": "جهان",
}

FOOTBALL_FALLBACKS = (
    "اولین دوره جام جهانی فوتبال در سال ۱۹۳۰ در اروگوئه برگزار شد و تیم میزبان قهرمان آن دوره شد.",
    "پله تنها بازیکنی است که سه بار قهرمان جام جهانی فوتبال شده است و این رکورد در تاریخ مسابقات ثبت شده است.",
    "جام جهانی فوتبال در نخستین دوره خود با حضور ۱۳ تیم برگزار شد و مسابقات آن در کشور اروگوئه انجام شد.",
    "فینال نخستین دوره جام جهانی فوتبال در سال ۱۹۳۰ بین اروگوئه و آرژانتین برگزار شد و اروگوئه قهرمان شد.",
)
GENERAL_FALLBACKS = (
    ("علم", "نور خورشید حدود ۸ دقیقه و ۲۰ ثانیه طول می‌کشد تا از خورشید به زمین برسد.", "دانش نجوم"),
    ("طبیعت", "اختاپوس سه قلب دارد و خونش به‌دلیل وجود هموسیانین، متمایل به آبی است.", "دانش زیست‌شناسی"),
    ("فناوری", "کد پاسخ سریع می‌تواند داده را در دو بُعد ذخیره کند و برای خواندن سریع اطلاعات طراحی شده است.", "دانش فناوری"),
    ("فضا", "یک شبانه‌روز خورشیدی روی عطارد حدود ۱۷۶ روز زمینی طول می‌کشد.", "دانش نجوم"),
    ("تاریخ", "واژه الگوریتم از نام دانشمند ایرانی محمد بن موسی خوارزمی آمده است.", "تاریخ علم"),
)

_last_action: dict[int, float] = {}


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, first_seen REAL NOT NULL, last_seen REAL NOT NULL)"
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS seen_facts(
                user_id INTEGER NOT NULL,
                fact_key TEXT NOT NULL,
                created_at REAL NOT NULL,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                PRIMARY KEY(user_id, fact_key)
            )"""
        )


def remember_user(user_id: int) -> None:
    now = time.time()
    with db() as conn:
        conn.execute(
            """INSERT INTO users(user_id,first_seen,last_seen) VALUES(?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen""",
            (user_id, now, now),
        )


def fact_key(text: str, source: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().casefold())
    normalized = re.sub(r"[\u200c\u200d\u200f\u202a-\u202e]", "", normalized)
    return hashlib.sha256(f"{source.casefold()}|{normalized}".encode("utf-8")).hexdigest()


def has_seen(user_id: int, key: str) -> bool:
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM seen_facts WHERE user_id=? AND fact_key=? LIMIT 1",
            (user_id, key),
        ).fetchone()
    return row is not None


def mark_seen(user_id: int, key: str, source: str, category: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen_facts VALUES(?,?,?,?,?)",
            (user_id, key, time.time(), source, category),
        )


def seen_count(user_id: int) -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM seen_facts WHERE user_id=?", (user_id,)
        ).fetchone()
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
    # The fact body itself must not contain English words.
    return persian >= 15 and latin == 0


def usable(text: str) -> bool:
    text = clean(text)
    if not (MIN_FACT <= len(text) <= MAX_FACT):
        return False
    if "@" in text or "t.me/" in text.lower():
        return False
    return persian_only(text)


def football_fallback(user_id: int) -> tuple[str, str, str, str] | None:
    pool = list(FOOTBALL_FALLBACKS)
    random.shuffle(pool)
    for text in pool:
        source = "مجموعه پشتیبان فوتبال"
        key = fact_key(text, source)
        if usable(text) and not has_seen(user_id, key):
            return text, "فوتبال", source, key
    return None


def general_fallback(user_id: int, topic: str | None) -> tuple[str, str, str, str] | None:
    pool = [item for item in GENERAL_FALLBACKS if topic is None or item[0] == TOPIC_NAMES.get(topic)]
    if not pool:
        pool = list(GENERAL_FALLBACKS)
    random.shuffle(pool)
    for category, text, source in pool:
        key = fact_key(text, source)
        if usable(text) and not has_seen(user_id, key):
            return text, category, source, key
    return None


async def get_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict[str, Any] | None = None,
) -> Any:
    try:
        async with session.get(url, params=params, allow_redirects=True) as response:
            if response.status != 200:
                return None
            return await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return None


async def source_wikipedia(session: aiohttp.ClientSession, topic: str | None):
    query = random.choice(TOPICS.get(topic or "new", TOPICS["new"]))
    data = await get_json(
        session,
        "https://fa.wikipedia.org/w/api.php",
        {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrnamespace": 0, "gsrlimit": 10,
            "prop": "extracts|info", "exintro": 1, "explaintext": 1,
            "inprop": "url",
        },
    )
    if not isinstance(data, dict):
        return None
    pages = list(data.get("query", {}).get("pages", {}).values())
    random.shuffle(pages)
    for page in pages:
        title = clean(str(page.get("title", "")))
        text = clean(str(page.get("extract", "")))
        url = str(page.get("fullurl", ""))
        blocked = ("کاربر:", "بحث:", "الگو:", "پرونده:", "رده:")
        if title and url.startswith("https://fa.wikipedia.org/") and usable(text) and not any(x in title for x in blocked):
            return text, TOPIC_NAMES.get(topic or "new", "دانستنی"), "ویکی‌پدیای فارسی", fact_key(text, url)
    return None


async def source_football_wikipedia(session: aiohttp.ClientSession):
    pages = ["فوتبال", "جام جهانی فوتبال", "کریستیانو رونالدو", "لیونل مسی", "پله", "مارادونا", "لیگ قهرمانان اروپا"]
    random.shuffle(pages)
    for title in pages:
        data = await get_json(
            session,
            "https://fa.wikipedia.org/w/api.php",
            {
                "action": "query", "format": "json", "prop": "extracts|info",
                "explaintext": 1, "exintro": 1, "inprop": "url", "titles": title,
            },
        )
        if not isinstance(data, dict):
            continue
        for page in data.get("query", {}).get("pages", {}).values():
            text = clean(str(page.get("extract", "")))
            url = str(page.get("fullurl", ""))
            if usable(text) and url.startswith("https://fa.wikipedia.org/"):
                return text, "فوتبال", "ویکی‌پدیای فارسی — فوتبال", fact_key(text, url)
    return None


async def source_wikidata_football(session: aiohttp.ClientSession):
    data = await get_json(
        session,
        "https://www.wikidata.org/w/api.php",
        {
            "action": "wbsearchentities", "search": random.choice(TOPICS["football"]),
            "language": "fa", "uselang": "fa", "format": "json", "limit": 8, "type": "item",
        },
    )
    if not isinstance(data, dict):
        return None
    hits = data.get("search", [])
    random.shuffle(hits)
    for hit in hits:
        label = clean(str(hit.get("label", "")))
        desc = clean(str(hit.get("description", "")))
        qid = str(hit.get("id", ""))
        text = f"«{label}» {desc}."
        if qid and label and desc and usable(text):
            return text, "فوتبال", "ویکی‌داده", fact_key(text, qid)
    return None


async def source_nasa(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "space"):
        return None
    data = await get_json(
        session,
        "https://api.nasa.gov/planetary/apod",
        {"api_key": os.getenv("NASA_API_KEY", "DEMO_KEY")},
    )
    if not isinstance(data, dict) or not data.get("date"):
        return None
    date = str(data["date"])
    text = f"ناسا در برنامه «تصویر نجومی روز» برای تاریخ {date} یک محتوای نجومی منتشر کرده است."
    return text, "فضا", "ناسا", fact_key(text, date)


async def source_world_bank(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "world"):
        return None
    code, name = random.choice(tuple({"IRN": "ایران", "FRA": "فرانسه", "DEU": "آلمان", "BRA": "برزیل", "JPN": "ژاپن"}.items()))
    data = await get_json(
        session,
        f"https://api.worldbank.org/v2/country/{code}/indicator/SP.POP.TOTL",
        {"format": "json", "per_page": 12},
    )
    if not isinstance(data, list) or len(data) < 2:
        return None
    row = next((item for item in data[1] if item.get("value") is not None), None)
    if not row:
        return None
    try:
        value = f"{int(row['value']):,}".replace(",", "،")
    except (TypeError, ValueError):
        return None
    text = f"طبق داده‌های بانک جهانی، جمعیت {name} در سال {row.get('date')} حدود {value} نفر ثبت شده است."
    if not usable(text):
        return None
    return text, "جهان", "بانک جهانی", fact_key(text, f"{code}:{row.get('date')}")


async def source_usgs(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "nature"):
        return None
    data = await get_json(session, "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson")
    if not isinstance(data, dict) or not data.get("features"):
        return None
    item = random.choice(data["features"])
    magnitude = item.get("properties", {}).get("mag")
    if magnitude is None:
        return None
    text = f"در فهرست رخدادهای مهم اخیر سازمان زمین‌شناسی آمریکا، زمین‌لرزه‌ای با بزرگای حدود {float(magnitude):.1f} ثبت شده است."
    if not usable(text):
        return None
    return text, "طبیعت", "سازمان زمین‌شناسی آمریکا", fact_key(text, str(item.get("id", magnitude)))


async def source_general(session: aiohttp.ClientSession, topic: str | None):
    candidates: list[Callable[[aiohttp.ClientSession, str | None], Awaitable[Any]]] = [source_wikipedia]
    if topic in (None, "space"):
        candidates.append(source_nasa)
    if topic in (None, "world"):
        candidates.append(source_world_bank)
    if topic in (None, "nature"):
        candidates.append(source_usgs)
    random.shuffle(candidates)
    for loader in candidates:
        value = await loader(session, topic)
        if value and usable(value[0]):
            return value
    return None


async def live_fact(topic: str | None):
    """Select a source without ever changing the requested topic."""
    async with aiohttp.ClientSession(
        timeout=TIMEOUT,
        headers={"User-Agent": "AmirFacts/3.0"},
    ) as session:
        if topic == "football":
            for loader in (source_football_wikipedia, source_wikidata_football):
                value = await loader(session)
                if value and value[1] == "فوتبال" and usable(value[0]):
                    return value
            return None

        return await source_general(session, topic)


async def get_new_fact(user_id: int, topic: str | None = None):
    remember_user(user_id)
    for _ in range(3):
        value = await live_fact(topic)
        if value and usable(value[0]) and not has_seen(user_id, value[3]):
            return value

    if topic == "football":
        return football_fallback(user_id)
    return general_fallback(user_id, topic)


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
    return (
        f"✨ <b>فکت جدید</b>\n\n{html.escape(text)}\n\n"
        f"🏷️ <b>دسته:</b> {html.escape(category)}\n"
        f"📚 <b>منبع:</b> {html.escape(source)}"
    )


if not BOT_TOKEN or BOT_TOKEN == "TOKEN RO INJA BEZAR":
    raise RuntimeError("Telegram bot token is missing")

bot = AsyncTeleBot(BOT_TOKEN, parse_mode="HTML")


@bot.message_handler(commands=["start", "help"])
async def start_handler(message: types.Message) -> None:
    remember_user(message.from_user.id)
    await bot.send_message(
        message.chat.id,
        "🚀 <b>AmirFacts</b>\n\nفکت‌های فارسی، منبع‌دار و غیرتکراری. ⚽ فوتبال هم اضافه شده.",
        reply_markup=keyboard(),
    )


async def send_fact(chat_id: int, user_id: int, topic: str | None = None) -> None:
    if not allowed(user_id):
        await bot.send_message(chat_id, "⏳ یه کم آروم‌تر 😄")
        return
    await bot.send_dice(chat_id, emoji="🎲")
    status = await bot.send_message(chat_id, "🔎 <i>دارم از چند منبع دنبال فکت تازه می‌گردم...</i>")
    result = await get_new_fact(user_id, topic)
    if not result:
        await bot.edit_message_text("😕 فعلاً فکت تازه‌ای پیدا نشد.", chat_id=chat_id, message_id=status.message_id)
        return
    text, category, source, key = result
    if not usable(text):
        await bot.edit_message_text("😕 فکت فارسی معتبر پیدا نشد.", chat_id=chat_id, message_id=status.message_id)
        return
    mark_seen(user_id, key, source, category)
    await bot.edit_message_text(
        render(text, category, source),
        chat_id=chat_id,
        message_id=status.message_id,
        reply_markup=keyboard(),
    )


@bot.message_handler(commands=["fact"])
async def fact_command(message: types.Message) -> None:
    await send_fact(message.chat.id, message.from_user.id)


@bot.message_handler(commands=["stats"])
async def stats_command(message: types.Message) -> None:
    await send_stats(message.chat.id, message.from_user.id)


async def send_stats(chat_id: int, user_id: int) -> None:
    await bot.send_message(
        chat_id,
        f"📊 <b>آمار تو</b>\n\n🧠 فکت‌های دیده‌شده: <b>{seen_count(user_id)}</b>",
        reply_markup=keyboard(),
    )


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
    print("AmirFacts configured. Polling is OFF by design.")


if __name__ == "__main__":
    asyncio.run(main())
