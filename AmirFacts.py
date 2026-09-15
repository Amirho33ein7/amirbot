# -*- coding: utf-8 -*-
"""AmirFacts — Persian multi-source Telegram facts bot."""
from __future__ import annotations
import asyncio, hashlib, html, os, random, re, sqlite3, time
from pathlib import Path
from typing import Any
import aiohttp
from telebot import types
from telebot.async_telebot import AsyncTeleBot

BOT_TOKEN = "TOKEN RO INJA BEZAR"
BOT_TOKEN = os.getenv("AMIRXPROXY_BOT_TOKEN", BOT_TOKEN)
DB_PATH = Path(os.getenv("AMIRFACTS_DB", "amirfacts.sqlite3"))
TIMEOUT = aiohttp.ClientTimeout(total=12, connect=5, sock_read=8)
MIN_FACT, MAX_FACT, COOLDOWN = 60, 650, 2.0
_last_action: dict[int, float] = {}

TOPICS = {
    "new": ("دانستنی", "اختراع", "کشف", "علم"),
    "space": ("فضا", "سیاره", "کهکشان", "ستاره", "ماه"),
    "science": ("فیزیک", "شیمی", "زیست", "مغز", "ژنتیک"),
    "technology": ("رایانه", "اینترنت", "هوش مصنوعی", "فناوری", "برنامه نویسی"),
    "nature": ("حیوانات", "اقیانوس", "طبیعت", "گیاه", "جانور", "زلزله"),
    "history": ("تاریخ", "تمدن", "باستان", "اختراع", "اکتشاف"),
    "football": ("فوتبال", "جام جهانی", "لیگ قهرمانان", "رونالدو", "مسی", "پله", "مارادونا"),
    "world": ("جمعیت", "اقتصاد", "کشورها", "آمار", "جهان"),
}
NAMES = {"new":"دانستنی","space":"فضا","science":"علم","technology":"فناوری","nature":"طبیعت","history":"تاریخ","football":"فوتبال","world":"جهان"}
FOOTBALL_FALLBACKS = (
    "اولین دوره جام جهانی فوتبال در سال ۱۹۳۰ در اروگوئه برگزار شد و تیم میزبان قهرمان آن دوره شد.",
    "پله تنها بازیکنی است که سه بار قهرمان جام جهانی فوتبال شده است و این رکورد در تاریخ مسابقات ثبت شده است.",
    "جام جهانی فوتبال در نخستین دوره خود با حضور ۱۳ تیم برگزار شد و مسابقات آن در کشور اروگوئه انجام شد.",
)
FALLBACKS = (
    ("علم", "نور خورشید حدود ۸ دقیقه و ۲۰ ثانیه طول می‌کشد تا از خورشید به زمین برسد و به همین دلیل ما خورشید را کمی دیرتر از لحظه واقعی می‌بینیم.", "دانش نجوم"),
    ("طبیعت", "اختاپوس سه قلب دارد و خونش به‌دلیل وجود هموسیانین، متمایل به آبی است؛ این ماده در انتقال اکسیژن نقش دارد.", "دانش زیست‌شناسی"),
    ("فناوری", "کد QR می‌تواند داده را در دو بُعد ذخیره کند و برای خواندن سریع اطلاعات توسط دوربین تلفن همراه طراحی شده است.", "دانش فناوری"),
    ("فضا", "یک شبانه‌روز خورشیدی روی عطارد حدود ۱۷۶ روز زمینی طول می‌کشد و این نتیجه از نسبت چرخش و گردش این سیاره به‌دست می‌آید.", "دانش نجوم"),
    ("تاریخ", "واژه الگوریتم از نام دانشمند ایرانی محمد بن موسی خوارزمی آمده است و امروزه در علوم رایانه کاربرد گسترده‌ای دارد.", "تاریخ علم"),
)


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=5000")
    return c


def init_db() -> None:
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, first_seen REAL NOT NULL, last_seen REAL NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS seen_facts(user_id INTEGER NOT NULL, fact_key TEXT NOT NULL, created_at REAL NOT NULL, source TEXT NOT NULL, category TEXT NOT NULL, PRIMARY KEY(user_id,fact_key))")


def remember_user(uid:int)->None:
    now=time.time()
    with db() as c: c.execute("INSERT INTO users VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen",(uid,now,now))


def fact_key(text:str,source:str)->str:
    text=re.sub(r"\s+"," ",text.strip().casefold())
    return hashlib.sha256(f"{source.casefold()}|{text}".encode()).hexdigest()


def has_seen(uid:int,key:str)->bool:
    with db() as c: return c.execute("SELECT 1 FROM seen_facts WHERE user_id=? AND fact_key=?",(uid,key)).fetchone() is not None


def mark_seen(uid:int,key:str,source:str,category:str)->None:
    with db() as c: c.execute("INSERT OR IGNORE INTO seen_facts VALUES(?,?,?,?,?)",(uid,key,time.time(),source,category))


def seen_count(uid:int)->int:
    with db() as c: row=c.execute("SELECT COUNT(*) FROM seen_facts WHERE user_id=?",(uid,)).fetchone()
    return int(row[0] if row else 0)


def clean(text:str)->str:
    text=html.unescape(text or "")
    text=re.sub(r"\[[0-9۰-۹]+\]","",text)
    text=re.sub(r"<[^>]+>"," ",text)
    text=re.sub(r"https?://\S+"," ",text)
    text=re.sub(r"\s+"," ",text).strip()
    return text if len(text)<=MAX_FACT else text[:MAX_FACT].rsplit(" ",1)[0]+"…"


def persian_only(text:str)->bool:
    letters=re.findall(r"[A-Za-z\u0600-\u06FF]",text)
    if len(letters)<12:return False
    fa=len(re.findall(r"[\u0600-\u06FF]",text)); en=len(re.findall(r"[A-Za-z]",text))
    return fa>=12 and en<=max(8,int(len(letters)*0.18))


def usable(text:str)->bool:
    text=clean(text)
    return MIN_FACT<=len(text)<=MAX_FACT and "@" not in text and "t.me/" not in text.lower() and persian_only(text)


def football_fallback(uid:int)->tuple[str,str,str,str]|None:
    pool=list(FOOTBALL_FALLBACKS); random.shuffle(pool)
    for text in pool:
        source="مجموعه پشتیبان فوتبال"
        key=fact_key(text,source)
        if usable(text) and not has_seen(uid,key): return text,"فوتبال",source,key
    return None


async def get_json(session:aiohttp.ClientSession,url:str,params:dict[str,Any]|None=None)->Any:
    try:
        async with session.get(url,params=params,allow_redirects=True) as r:
            if r.status!=200:return None
            return await r.json(content_type=None)
    except (aiohttp.ClientError,asyncio.TimeoutError,ValueError): return None


async def wikipedia(session,topic):
    q=random.choice(TOPICS.get(topic or "new",TOPICS["new"]))
    data=await get_json(session,"https://fa.wikipedia.org/w/api.php",{"action":"query","format":"json","generator":"search","gsrsearch":q,"gsrnamespace":0,"gsrlimit":10,"prop":"extracts|info","exintro":1,"explaintext":1,"inprop":"url"})
    if not isinstance(data,dict):return None
    pages=list(data.get("query",{}).get("pages",{}).values());random.shuffle(pages)
    for p in pages:
        text,title,url=clean(str(p.get("extract",""))),clean(str(p.get("title",""))),str(p.get("fullurl",""))
        if title and url.startswith("https://fa.wikipedia.org/") and usable(text) and not any(x in title for x in ("کاربر:","بحث:","الگو:","پرونده:","رده:")):
            return text,NAMES.get(topic or "new","دانستنی"),"ویکی‌پدیای فارسی",fact_key(text,url)
    return None


async def football_wikipedia(session):
    titles=list(("فوتبال","جام جهانی فوتبال","کریستیانو رونالدو","لیونل مسی","پله","مارادونا","لیگ قهرمانان اروپا"));random.shuffle(titles)
    for title in titles:
        data=await get_json(session,"https://fa.wikipedia.org/w/api.php",{"action":"query","format":"json","prop":"extracts|info","explaintext":1,"exintro":1,"inprop":"url","titles":title})
        if not isinstance(data,dict):continue
        for p in data.get("query",{}).get("pages",{}).values():
            text,url=clean(str(p.get("extract",""))),str(p.get("fullurl",""))
            if usable(text) and url.startswith("https://fa.wikipedia.org/"):
                return text,"فوتبال","ویکی‌پدیای فارسی — فوتبال",fact_key(text,url)
    return None


async def wikidata_football(session):
    data=await get_json(session,"https://www.wikidata.org/w/api.php",{"action":"wbsearchentities","search":random.choice(TOPICS["football"]),"language":"fa","uselang":"fa","format":"json","limit":8,"type":"item"})
    if not isinstance(data,dict):return None
    hits=data.get("search",[]);random.shuffle(hits)
    for h in hits:
        label,desc,qid=clean(str(h.get("label",""))),clean(str(h.get("description",""))),str(h.get("id",""))
        text=f"«{label}» {desc}."
        if qid and label and desc and usable(text):return text,"فوتبال","ویکی‌داده",fact_key(text,qid)
    return None


async def world_bank(session):
    code,fa_name=random.choice(list({"IRN":"ایران","FRA":"فرانسه","DEU":"آلمان","BRA":"برزیل","JPN":"ژاپن"}.items()))
    data=await get_json(session,f"https://api.worldbank.org/v2/country/{code}/indicator/SP.POP.TOTL",{"format":"json","per_page":12})
    if not isinstance(data,list) or len(data)<2:return None
    row=next((x for x in data[1] if x.get("value") is not None),None)
    if not row:return None
    try:number=f"{int(row['value']):,}".replace(",","،")
    except (TypeError,ValueError):return None
    text=f"طبق داده‌های بانک جهانی، جمعیت {fa_name} در سال {row.get('date')} حدود {number} نفر ثبت شده است."
    return (text,"جهان","بانک جهانی",fact_key(text,f"{code}:{row.get('date')}")) if usable(text) else None


async def usgs(session):
    data=await get_json(session,"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson")
    if not isinstance(data,dict) or not data.get("features"):return None
    item=random.choice(data["features"]);mag=item.get("properties",{}).get("mag")
    if mag is None:return None
    text=f"در فهرست رخدادهای مهم اخیر سازمان زمین‌شناسی آمریکا، زمین‌لرزه‌ای با بزرگای حدود {float(mag):.1f} ثبت شده است."
    return (text,"طبیعت","سازمان زمین‌شناسی آمریکا",fact_key(text,str(item.get("id",mag)))) if usable(text) else None


async def nasa(session):
    data=await get_json(session,"https://api.nasa.gov/planetary/apod",{"api_key":os.getenv("NASA_API_KEY","DEMO_KEY")})
    if not isinstance(data,dict) or not data.get("date"):return None
    date=str(data["date"]);text=f"ناسا در برنامه «تصویر نجومی روز» برای تاریخ {date} یک محتوای نجومی منتشر کرده است."
    return text,"فضا","ناسا",fact_key(text,date)


async def live_fact(topic):
    async with aiohttp.ClientSession(timeout=TIMEOUT,headers={"User-Agent":"AmirFacts/2.3"}) as s:
        if topic=="football":
            for loader in (football_wikipedia,wikidata_football):
                value=await loader(s)
                if value:return value
        if topic=="world":
            value=await world_bank(s)
            if value:return value
        if topic=="nature":
            value=await usgs(s)
            if value:return value
        if topic=="space":
            value=await nasa(s)
            if value:return value
        for loader in (lambda x:wikipedia(x,topic),world_bank,usgs,nasa):
            value=await loader(s)
            if value:return value
    return None


def generic_fallback(uid,topic):
    pool=[x for x in FALLBACKS if topic is None or x[0]==NAMES.get(topic)] or list(FALLBACKS);random.shuffle(pool)
    for category,text,source in pool:
        key=fact_key(text,source)
        if usable(text) and not has_seen(uid,key):return text,category,source,key
    return None


async def get_new_fact(uid,topic=None):
    remember_user(uid)
    for _ in range(3):
        value=await live_fact(topic)
        if value and usable(value[0]) and not has_seen(uid,value[3]):return value
    if topic=="football":return football_fallback(uid)
    return generic_fallback(uid,topic)


def allowed(uid):
    now=time.time()
    if now-_last_action.get(uid,0.0)<COOLDOWN:return False
    _last_action[uid]=now;return True


def keyboard():
    kb=types.InlineKeyboardMarkup(row_width=2)
    for row in ((("🎲 فکت جدید","fact:new"),("⚽ فوتبال","fact:football")),(("🌌 فضا","fact:space"),("🧠 علم","fact:science")),(("💻 فناوری","fact:technology"),("🌿 طبیعت","fact:nature")),(("🏛️ تاریخ","fact:history"),("🌍 جهان","fact:world"))):kb.add(*[types.InlineKeyboardButton(a,callback_data=b) for a,b in row])
    kb.add(types.InlineKeyboardButton("📊 آمار من",callback_data="stats"));return kb


def render(text,category,source):return f"✨ <b>فکت جدید</b>\n\n{html.escape(text)}\n\n🏷️ <b>دسته:</b> {html.escape(category)}\n📚 <b>منبع:</b> {html.escape(source)}"

if not BOT_TOKEN or BOT_TOKEN=="TOKEN RO INJA BEZAR":raise RuntimeError("Telegram bot token is missing")
bot=AsyncTeleBot(BOT_TOKEN,parse_mode="HTML")

@bot.message_handler(commands=["start","help"])
async def start_handler(message):
    remember_user(message.from_user.id);await bot.send_message(message.chat.id,"🚀 <b>AmirFacts</b>\n\nفکت‌های فارسی، منبع‌دار و غیرتکراری. ⚽ فوتبال هم اضافه شده.",reply_markup=keyboard())

async def send_fact(chat_id,uid,topic=None):
    if not allowed(uid):await bot.send_message(chat_id,"⏳ یه کم آروم‌تر 😄");return
    await bot.send_dice(chat_id,emoji="🎲");status=await bot.send_message(chat_id,"🔎 <i>دارم از چند منبع دنبال فکت تازه می‌گردم...</i>")
    result=await get_new_fact(uid,topic)
    if not result:await bot.edit_message_text("😕 فعلاً فکت تازه‌ای پیدا نشد.",chat_id=chat_id,message_id=status.message_id);return
    text,category,source,key=result
    if not usable(text):await bot.edit_message_text("😕 فکت فارسی معتبر پیدا نشد.",chat_id=chat_id,message_id=status.message_id);return
    mark_seen(uid,key,source,category);await bot.edit_message_text(render(text,category,source),chat_id=chat_id,message_id=status.message_id,reply_markup=keyboard())

@bot.message_handler(commands=["fact"])
async def fact_command(message):await send_fact(message.chat.id,message.from_user.id)

@bot.message_handler(commands=["stats"])
async def stats_command(message):await send_stats(message.chat.id,message.from_user.id)

async def send_stats(chat_id,uid):await bot.send_message(chat_id,f"📊 <b>آمار تو</b>\n\n🧠 فکت‌های دیده‌شده: <b>{seen_count(uid)}</b>",reply_markup=keyboard())

@bot.callback_query_handler(func=lambda call:call.data=="fact:new")
async def new_fact_callback(call):await bot.answer_callback_query(call.id);await send_fact(call.message.chat.id,call.from_user.id)

@bot.callback_query_handler(func=lambda call:call.data.startswith("fact:") and call.data!="fact:new")
async def topic_callback(call):
    await bot.answer_callback_query(call.id);topic=call.data.split(":",1)[1]
    if topic in TOPICS:await send_fact(call.message.chat.id,call.from_user.id,topic)

@bot.callback_query_handler(func=lambda call:call.data=="stats")
async def stats_callback(call):await bot.answer_callback_query(call.id);await send_stats(call.message.chat.id,call.from_user.id)

async def main():init_db();print("AmirFacts configured. Polling is OFF by design.")
if __name__=="__main__":asyncio.run(main())
