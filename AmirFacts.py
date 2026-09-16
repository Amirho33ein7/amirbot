# -*- coding: utf-8 -*-
"""AmirFacts — Persian multi-source fact bot.

Polling is intentionally OFF. The fact engine is designed for high-reuse,
source-independent deduplication and graceful offline fallback per topic.
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
MIN_FACT = 55
MAX_FACT = 700
COOLDOWN = 2.0

TOPICS: dict[str, tuple[str, ...]] = {
    "new": ("دانستنی", "اختراع", "کشف", "علم", "دانشمند", "تاریخ علم", "فرهنگ", "جهان", "طبیعت"),
    "space": ("فضا", "سیاره", "کهکشان", "ستاره", "ماه", "مریخ", "زمین", "خورشید", "نجوم", "کیهان", "سیارک", "سحابی", "مدار"),
    "science": ("فیزیک", "شیمی", "زیست", "مغز", "ژنتیک", "سلول", "اتم", "مولکول", "زیست شناسی", "پزشکی", "ریاضی", "آزمایش", "ماده", "انرژی", "اعصاب"),
    "technology": ("رایانه", "اینترنت", "هوش مصنوعی", "فناوری", "برنامه نویسی", "شبکه", "پردازنده", "نرم افزار", "سخت افزار", "ربات", "داده", "الگوریتم", "رمزنگاری"),
    "nature": ("حیوانات", "اقیانوس", "طبیعت", "گیاه", "جانور", "پرندگان", "پستانداران", "دریا", "جنگل", "زیست بوم", "زمین شناسی", "اقلیم", "حشرات"),
    "history": ("تاریخ", "تمدن", "باستان", "اختراع", "اکتشاف", "امپراتوری", "پادشاه", "جنگ", "باستان شناسی", "فرهنگ", "ایران باستان", "موزه", "سلسله"),
    "football": ("فوتبال", "جام جهانی", "رونالدو", "مسی", "پله", "مارادونا", "لیگ قهرمانان", "باشگاه", "بازیکن", "مربی", "تیم ملی", "ورزشگاه", "لیگ"),
    "world": ("جمعیت", "کشورها", "اقتصاد", "آمار", "جهان", "تولید ناخالص", "انرژی", "اینترنت", "سلامت", "آموزش", "آب", "جغرافیا"),
}
TOPIC_NAMES = {"new":"دانستنی", "space":"فضا", "science":"علم", "technology":"فناوری", "nature":"طبیعت", "history":"تاریخ", "football":"فوتبال", "world":"جهان"}
TOPIC_SIGNALS = {
    "space": ("فضا", "سیاره", "کهکشان", "ستاره", "ماه", "مریخ", "خورشید", "نجوم", "کیهان", "سیارک", "سحابی", "مدار", "فضاپیما"),
    "science": ("علم", "فیزیک", "شیمی", "زیست", "سلول", "ژن", "مغز", "اتم", "مولکول", "پزشکی", "ریاضی", "آزمایش", "ماده", "انرژی", "اعصاب", "حافظه"),
    "technology": ("رایانه", "اینترنت", "هوش مصنوعی", "فناوری", "برنامه نویسی", "شبکه", "پردازنده", "نرم افزار", "سخت افزار", "ربات", "داده", "الگوریتم", "رمزنگاری"),
    "nature": ("حیوان", "جانور", "گیاه", "اقیانوس", "دریا", "جنگل", "اقلیم", "زیست بوم", "پرنده", "پستاندار", "زمین شناسی", "طبیعت", "حشرات", "ماهی"),
    "history": ("تاریخ", "تمدن", "باستان", "امپراتوری", "پادشاه", "جنگ", "باستان شناسی", "ایران باستان", "موزه", "فرهنگ", "سلسله", "قرن"),
    "football": ("فوتبال", "جام جهانی", "رونالدو", "مسی", "پله", "مارادونا", "لیگ قهرمانان", "باشگاه", "بازیکن", "مربی", "تیم ملی", "ورزشگاه", "لیگ"),
    "world": ("جمعیت", "کشور", "اقتصاد", "تولید ناخالص", "انرژی", "اینترنت", "سلامت", "آموزش", "آب", "جهان", "آمار", "جغرافیا", "قاره"),
}

FALLBACK_BANK: dict[str, tuple[str, ...]] = {
    "new": (
        "عدد پی نسبت محیط دایره به قطر آن است و مقدار تقریبی آن ۳٫۱۴۱۵۹ در نظر گرفته می‌شود.",
        "نور سفید خورشید از ترکیب طول موج‌های گوناگون تشکیل شده و منشور می‌تواند آن را به رنگ‌های طیف مرئی جدا کند.",
        "زنبورهای عسل برای پیدا کردن مسیر منابع غذایی می‌توانند از الگوهای حرکتی و جهت خورشید استفاده کنند.",
        "آب در شرایط معمولی در دمای صفر درجه سلسیوس یخ می‌زند و در صد درجه سلسیوس می‌جوشد.",
        "قطب‌نما با استفاده از میدان مغناطیسی زمین برای تشخیص جهت‌ها به کار می‌رود.",
        "رعد و برق درون ابرهای توفانی از جابه‌جایی بارهای الکتریکی ایجاد می‌شود.",
        "بارکدهای دوبعدی مانند کد کیوآر می‌توانند اطلاعات را در الگویی از مربع‌های کوچک ذخیره کنند.",
        "واژه الگوریتم به نام خوارزمی، دانشمند ایرانی، ارتباط تاریخی دارد.",
        "درختان حلقه‌های رشد سالانه دارند و این حلقه‌ها در شرایط مناسب می‌توانند اطلاعاتی درباره رشد درخت نشان دهند.",
        "برخی حشرات چرخه زندگی خود را از چند مرحله مانند تخم، لارو و شفیره عبور می‌دهند.",
        "صدای انسان نتیجه ارتعاش تارهای صوتی و شکل‌دهی موج صوتی توسط مجرای گفتار است.",
        "مغز برای کارکرد طبیعی خود به انرژی و اکسیژن نیاز دارد و جریان خون نقش مهمی در این تأمین دارد.",
        "ماه نور تولید نمی‌کند و بخش روشن آن از بازتاب نور خورشید دیده می‌شود.",
        "فشار هوا با افزایش ارتفاع از سطح دریا معمولاً کاهش پیدا می‌کند و همین تغییر در هواشناسی اهمیت دارد.",
        "یخ چگالی کمتری از آب مایع دارد و به همین دلیل روی آب شناور می‌شود.",
        "پنجره‌های دو جداره با ایجاد یک لایه گاز بین دو شیشه می‌توانند انتقال گرما را کاهش دهند.",
        "رودخانه‌ها در طول مسیر خود با فرسایش و جابه‌جایی رسوبات می‌توانند شکل سطح زمین را تغییر دهند.",
        "بسیاری از دوربین‌های دیجیتال نور را به وسیله حسگرهای الکترونیکی به داده تبدیل می‌کنند.",
        "مغناطیس و الکتریسیته دو پدیده به‌هم‌پیوسته‌اند و جریان الکتریکی می‌تواند میدان مغناطیسی ایجاد کند.",
        "ابرها از قطره‌های بسیار ریز آب، بلورهای یخ یا ترکیبی از هر دو تشکیل می‌شوند.",
    ),
    "space": (
        "زمین سومین سیاره از خورشید و تنها سیاره شناخته‌شده دارای حیات در منظومه شمسی است.",
        "مریخ به دلیل وجود اکسیدهای آهن روی سطح خود به سیاره سرخ مشهور است.",
        "مشتری بزرگ‌ترین سیاره منظومه شمسی است و جرم آن از جرم مجموع بسیاری از سیارات دیگر بیشتر است.",
        "زحل به حلقه‌های گسترده‌ای از ذرات یخ و سنگ شناخته می‌شود.",
        "اورانوس نسبت به بسیاری از سیارات حالت چرخش متفاوتی دارد و محور چرخش آن به‌طور زیادی متمایل است.",
        "نپتون دورترین سیاره اصلی منظومه شمسی از خورشید است.",
        "ماه تنها قمر طبیعی بزرگ زمین است و تقریباً هر ۲۷٫۳ روز یک بار نسبت به ستارگان یک دور به دور زمین می‌زند.",
        "جزر و مد اقیانوس‌های زمین به‌ویژه تحت تأثیر گرانش ماه و تا حدی خورشید قرار دارد.",
        "خورشید یک ستاره است و بیشتر انرژی آن از واکنش‌های همجوشی هسته‌ای در بخش مرکزی آن تأمین می‌شود.",
        "سال نوری یک واحد مسافت است و به مسافتی گفته می‌شود که نور در یک سال در خلأ طی می‌کند.",
        "کهکشان راه شیری یک کهکشان مارپیچی است که منظومه شمسی در یکی از بازوهای آن قرار دارد.",
        "سیاه‌چاله ناحیه‌ای از فضاست که گرانش آن به اندازه‌ای شدید است که نور نیز نمی‌تواند از افق رویدادش بگریزد.",
        "شهاب‌واره جسمی کوچک در فضاست و وقتی بخشی از آن در جو می‌سوزد و می‌درخشد، شهاب دیده می‌شود.",
        "سحابی‌ها ابرهای گسترده‌ای از گاز و غبار میان‌ستاره‌ای هستند و برخی محل تولد ستاره‌ها هستند.",
        "گرفت خورشید زمانی رخ می‌دهد که ماه در مسیر دید میان زمین و خورشید قرار می‌گیرد.",
        "گرفت ماه زمانی رخ می‌دهد که زمین میان خورشید و ماه قرار بگیرد و سایه زمین روی ماه بیفتد.",
        "فضاپیماهای بدون سرنشین برای مطالعه سیارات، قمرها و اجرام دوردست اطلاعات علمی ارزشمندی ارسال کرده‌اند.",
        "سرعت نور در خلأ دقیقاً ۲۹۹۷۹۲۴۵۸ متر بر ثانیه تعریف شده است و در فیزیک بنیادی اهمیت دارد.",
        "عطارد نزدیک‌ترین سیاره به خورشید است و سال آن تنها حدود ۸۸ روز زمینی طول می‌کشد.",
        "زهره داغ‌ترین سیاره منظومه شمسی در سطح خود است و جو ضخیم آن گرما را در خود نگه می‌دارد.",
    ),
    "science": (
        "سرعت نور در خلأ دقیقاً ۲۹۹۷۹۲۴۵۸ متر بر ثانیه تعریف شده است و یکی از ثابت‌های بنیادی فیزیک است.",
        "صفر مطلق برابر با منفی ۲۷۳٫۱۵ درجه سلسیوس است و رسیدن کامل به آن از نظر ترمودینامیکی ممکن نیست.",
        "عدد اتمی هر عنصر برابر با تعداد پروتون‌های هسته اتم آن عنصر است.",
        "الکترون بار الکتریکی منفی و پروتون بار الکتریکی مثبت دارد و این تفاوت در ساختار اتم مهم است.",
        "نوترون در حالت معمول بار الکتریکی خالص ندارد و در هسته بسیاری از اتم‌ها یافت می‌شود.",
        "سلول واحد بنیادی ساختاری و عملکردی جانداران به شمار می‌رود و بسیاری از فرایندهای زیستی در آن انجام می‌شود.",
        "دی‌ان‌ای مولکولی است که اطلاعات ژنتیکی بسیاری از جانداران را ذخیره می‌کند.",
        "ژن بخشی از ماده ژنتیکی است که می‌تواند با یک ویژگی یا عملکرد زیستی ارتباط داشته باشد.",
        "هموگلوبین پروتئینی در گلبول قرمز است که به حمل اکسیژن در خون کمک می‌کند.",
        "میتوکندری در بسیاری از یاخته‌های یوکاریوتی در تولید انرژی شیمیایی قابل استفاده نقش مهمی دارد.",
        "کلروفیل رنگدانه‌ای است که در جذب نور مورد استفاده برای فتوسنتز گیاهان نقش دارد.",
        "فتوسنتز فرایندی است که در آن گیاهان و برخی جانداران با استفاده از نور ترکیبات آلی می‌سازند.",
        "نیتروژن فراوان‌ترین گاز موجود در جو خشک زمین است و نزدیک به چهار پنجم آن را تشکیل می‌دهد.",
        "اکسیژن حدود یک پنجم حجم هوای خشک زمین را تشکیل می‌دهد و برای تنفس هوازی بسیاری از جانداران مهم است.",
        "قانون دوم نیوتن رابطه میان نیرو، جرم و شتاب را بیان می‌کند و به صورت F=ma شناخته می‌شود.",
        "انرژی جنبشی یک جسم با جرم و مربع سرعت آن ارتباط دارد و با افزایش سرعت رشد زیادی می‌کند.",
        "فرکانس تعداد چرخه‌های یک پدیده تناوبی در هر ثانیه است و واحد آن هرتز است.",
        "طول موج فاصله بین دو نقطه هم‌فاز متوالی در یک موج است و با فرکانس رابطه دارد.",
        "جمع زاویه‌های داخلی مثلث در هندسه اقلیدسی ۱۸۰ درجه است و یکی از نتایج پایه هندسه محسوب می‌شود.",
        "باکتری‌ها جانداران تک‌یاخته‌ای هستند و سلول آن‌ها هسته غشادار ندارد.",
    ),
    "technology": (
        "پردازنده مرکزی رایانه دستورهای برنامه را اجرا می‌کند و عملیات منطقی و محاسباتی را انجام می‌دهد.",
        "حافظه رم محل نگهداری موقت داده‌ها و برنامه‌هایی است که رایانه در حال استفاده از آن‌هاست.",
        "حافظه‌های اس‌اس‌دی از تراشه‌های حافظه فلش استفاده می‌کنند و قطعه مکانیکی چرخان ندارند.",
        "بیت کوچک‌ترین واحد رایج اطلاعات در رایانش است و می‌تواند مقدار صفر یا یک داشته باشد.",
        "هشت بیت یک بایت را تشکیل می‌دهد و بایت برای نمایش بسیاری از داده‌های دیجیتال استفاده می‌شود.",
        "سیستم‌عامل میان سخت‌افزار رایانه و برنامه‌های کاربردی هماهنگی ایجاد می‌کند و منابع دستگاه را مدیریت می‌کند.",
        "مرورگر وب برنامه‌ای است که برای دریافت و نمایش صفحات و برنامه‌های وب استفاده می‌شود.",
        "پروتکل اچ‌تی‌تی‌پی برای انتقال درخواست و پاسخ در وب به کار می‌رود و پایه بسیاری از ارتباطات وب است.",
        "اچ‌تی‌تی‌پی‌اس نسخه‌ای امن‌تر از ارتباط وب است که از رمزنگاری ارتباط استفاده می‌کند.",
        "دی‌ان‌اس نام دامنه را به اطلاعات لازم برای پیدا کردن مقصد شبکه ترجمه می‌کند.",
        "آدرس آی‌پی برای شناسایی یک رابط شبکه در یک محدوده شبکه‌ای استفاده می‌شود.",
        "الگوریتم مجموعه‌ای مرحله‌به‌مرحله از دستورها برای حل مسئله یا پردازش داده است.",
        "یادگیری ماشین شاخه‌ای از هوش مصنوعی است که در آن مدل‌ها از داده برای یادگیری الگو استفاده می‌کنند.",
        "شبکه عصبی مصنوعی ساختاری محاسباتی است که از واحدهایی به نام نورون مصنوعی تشکیل می‌شود.",
        "رمزنگاری نامتقارن از یک جفت کلید عمومی و خصوصی برای عملیات رمزنگاری یا امضای دیجیتال استفاده می‌کند.",
        "کد کیوآر می‌تواند اطلاعات متنی یا یک نشانی وب را در قالب یک الگوی دوبعدی ذخیره کند.",
        "گیت کنترل نسخه تغییرات پروژه‌های نرم‌افزاری را ساده می‌کند و تاریخچه تغییرات را نگه می‌دارد.",
        "پایگاه داده برای ذخیره، جست‌وجو و مدیریت ساختاریافته اطلاعات استفاده می‌شود.",
        "پایتون یک زبان برنامه‌نویسی سطح بالا است که برای اسکریپت، وب، تحلیل داده و کاربردهای گوناگون استفاده می‌شود.",
        "کامپایلر یا مفسر کد برنامه را به شکلی تبدیل یا اجرا می‌کند که رایانه بتواند آن را پردازش کند.",
    ),
    "nature": (
        "اختاپوس سه قلب دارد و خون آن به دلیل استفاده از هموسیانین رنگی متمایل به آبی دارد.",
        "زرافه و انسان هر دو هفت مهره گردنی دارند، هرچند طول مهره‌ها بسیار متفاوت است.",
        "خفاش تنها گروه پستانداران است که توانایی پرواز فعال و واقعی دارد.",
        "دلفین‌ها پستاندارند و برای تنفس باید به سطح آب بیایند.",
        "نهنگ آبی بزرگ‌ترین جانور شناخته‌شده در تاریخ زمین است.",
        "زنبور عسل با انجام گرده‌افشانی به تولیدمثل بسیاری از گیاهان کمک می‌کند.",
        "بعضی گونه‌های مورچه می‌توانند شبکه‌های پیچیده‌ای برای یافتن و حمل غذا ایجاد کنند.",
        "کاکتوس‌ها سازگاری‌هایی برای کاهش از دست رفتن آب در محیط‌های خشک دارند.",
        "برگ گیاهان محل مهمی برای فتوسنتز است و بسیاری از آن‌ها کلروفیل در خود دارند.",
        "جنگل‌های بارانی استوایی از زیست‌بوم‌های بسیار متنوع زمین از نظر شمار گونه‌ها هستند.",
        "صخره‌های مرجانی از اجتماعات جانوران مرجانی و موجودات وابسته به آن‌ها تشکیل می‌شوند.",
        "زمین‌لرزه‌ها می‌توانند در اثر آزاد شدن ناگهانی انرژی در پوسته زمین رخ دهند.",
        "آتشفشان‌ها می‌توانند مواد مذاب، خاکستر و گاز را از بخش‌های درونی زمین به سطح برسانند.",
        "لایه اوزون در بخش بالایی جو زمین مقدار زیادی از پرتو فرابنفش خورشید را جذب می‌کند.",
        "قطب شمال پوشیده از خشکی قاره‌ای نیست و بیشتر آن را اقیانوس منجمد شمالی تشکیل می‌دهد.",
        "پنگوئن‌ها پرنده‌اند اما بیشتر گونه‌های آن برای شنا و زندگی در آب سازگاری یافته‌اند.",
        "شترمرغ بزرگ‌ترین پرنده زنده امروزی از نظر قد و وزن است و قادر به پرواز نیست.",
        "پروانه‌ها چرخه دگردیسی دارند و از مرحله‌هایی مانند تخم، لارو و حشره بالغ عبور می‌کنند.",
        "گیاهان برای رشد به آب، مواد معدنی، نور و دی‌اکسیدکربن نیاز دارند.",
        "در اقیانوس‌ها بخش بزرگی از تنوع زیستی زمین زندگی می‌کند و زنجیره‌های غذایی گسترده‌ای شکل گرفته است.",
    ),
    "history": (
        "خط میخی از نخستین نظام‌های نوشتاری شناخته‌شده است و در میان تمدن‌های باستانی بین‌النهرین استفاده می‌شد.",
        "تمدن مصر باستان در کنار رود نیل رشد کرد و کشاورزی آن به چرخه آب این رود وابسته بود.",
        "اهرام جیزه در مصر از شناخته‌شده‌ترین سازه‌های باقی‌مانده از جهان باستان هستند.",
        "شهر باستانی بابل در میان‌رودان قرار داشت و در تاریخ منطقه بین‌النهرین اهمیت زیادی داشته است.",
        "جاده ابریشم شبکه‌ای از مسیرهای بازرگانی بود که شرق و غرب آسیا و بخش‌هایی از اروپا را به هم پیوند می‌داد.",
        "کاغذ در چین باستان توسعه یافت و سپس در مناطق دیگر جهان گسترش پیدا کرد.",
        "قطب‌نما پیش از ورود به اروپا در چین استفاده می‌شد و بعدها به ابزار مهمی برای دریانوردی تبدیل شد.",
        "دانشگاه جندی‌شاپور در دوره ساسانی یکی از مراکز مهم علمی و پزشکی منطقه بود.",
        "ابن‌سینا کتاب قانون در طب را نوشت و این اثر قرن‌ها در آموزش پزشکی مورد توجه بود.",
        "خوارزمی در شکل‌گیری دانش جبر نقش مهمی داشت و نام او در واژه الگوریتم بازتاب یافته است.",
        "چاپ با حروف متحرک در اروپا در سده پانزدهم با نام یوهانس گوتنبرگ پیوند خورده است.",
        "انقلاب صنعتی با گسترش ماشین‌آلات و کارخانه‌ها، شیوه تولید را در بخش‌هایی از اروپا دگرگون کرد.",
        "کانال سوئز ارتباط دریایی میان دریای مدیترانه و دریای سرخ را کوتاه‌تر کرد.",
        "بسیاری از شهرهای باستانی در مسیر رودخانه‌ها شکل گرفتند زیرا آب برای کشاورزی و زندگی ضروری بود.",
        "باستان‌شناسی با بررسی آثار مادی گذشته به شناخت جوامع تاریخی کمک می‌کند.",
        "سکه‌های فلزی از ابزارهای مهم اقتصادی در بسیاری از تمدن‌های باستانی بودند.",
        "المپیک باستان در یونان برگزار می‌شد و به یکی از شناخته‌شده‌ترین رویدادهای ورزشی جهان باستان تبدیل شد.",
        "رصدخانه‌های تاریخی در تمدن‌های مختلف برای ثبت حرکت ستارگان و محاسبه زمان به کار می‌رفتند.",
        "بسیاری از نقشه‌های قدیمی علاوه بر کاربرد جغرافیایی، اطلاعاتی درباره تجارت و مسیرهای دریایی ثبت می‌کردند.",
        "موزه‌ها با نگهداری و نمایش آثار می‌توانند به حفظ میراث فرهنگی و علمی کمک کنند.",
    ),
    "football": (
        "نخستین دوره جام جهانی فوتبال در سال ۱۹۳۰ در اروگوئه برگزار شد و تیم میزبان قهرمان شد.",
        "پله تنها بازیکنی است که سه بار قهرمان جام جهانی فوتبال شده است.",
        "جام جهانی ۱۹۵۰ در برزیل برگزار شد و اروگوئه در بازی پایانی گروهی مقابل برزیل قهرمان شد.",
        "مارادونا با تیم ملی آرژانتین در جام جهانی ۱۹۸۶ قهرمان شد.",
        "کریستیانو رونالدو از معدود بازیکنانی است که در چند دوره جام جهانی برای پرتغال گل زده است.",
        "لیونل مسی در سال ۲۰۲۲ همراه آرژانتین قهرمان جام جهانی شد.",
        "اولین فینال جام جهانی فوتبال بین اروگوئه و آرژانتین برگزار شد و اروگوئه قهرمان شد.",
        "لیگ قهرمانان اروپا بالاترین رقابت باشگاهی فوتبال اروپا زیر نظر یوفاست.",
        "باشگاه رئال مادرید از موفق‌ترین باشگاه‌های تاریخ رقابت‌های اروپایی به شمار می‌رود.",
        "آفساید یکی از قوانین فوتبال است که برای محدود کردن موقعیت مهاجم نسبت به خط دفاع تعریف شده است.",
        "در فوتبال هر تیم در حالت معمول با یازده بازیکن بازی را آغاز می‌کند.",
        "دروازه‌بان تنها بازیکنی است که در چارچوب قوانین می‌تواند در محوطه جریمه توپ را با دست لمس کند.",
        "کارت زرد در فوتبال اخطار داور به بازیکن است و دو کارت زرد در یک مسابقه می‌تواند به اخراج منجر شود.",
        "ضربه کرنر زمانی اعلام می‌شود که توپ پس از برخورد آخرین بازیکن مدافع از خط دروازه بیرون برود و گل نشده باشد.",
        "ورزشگاه ومبلی در لندن یکی از شناخته‌شده‌ترین ورزشگاه‌های فوتبال جهان است.",
        "توپ فوتبال مدرن معمولاً از چندین پنل با شکل هندسی مشخص ساخته می‌شود.",
        "وقت اضافه در برخی مسابقات حذفی برای تعیین برنده پس از مساوی شدن در زمان معمول استفاده می‌شود.",
        "پنالتی از فاصله یازده متری دروازه زده می‌شود و ضربه بدون حضور دیوار دفاعی انجام می‌گیرد.",
        "کاپیتان تیم در بسیاری از مسابقات بازوبند مخصوصی روی بازو دارد.",
        "فوتبال به‌عنوان ورزش تیمی به هماهنگی، پاس‌کاری، جای‌گیری و تصمیم‌گیری سریع نیاز دارد.",
    ),
    "world": (
        "آسیا بزرگ‌ترین قاره زمین از نظر مساحت و جمعیت است.",
        "اقیانوس آرام بزرگ‌ترین اقیانوس زمین از نظر مساحت است.",
        "روسیه از نظر مساحت بزرگ‌ترین کشور جهان است.",
        "واتیکان از نظر مساحت کوچک‌ترین کشور مستقل جهان است.",
        "صحرا بزرگ‌ترین بیابان گرم جهان است و در شمال آفریقا قرار دارد.",
        "قطب جنوب یک قاره است و بخش بزرگی از سطح آن را یخ پوشانده است.",
        "خط استوا زمین را به نیمکره شمالی و جنوبی تقسیم می‌کند.",
        "آمازون یکی از بزرگ‌ترین سامانه‌های رودخانه‌ای جهان است و حوضه آن بخش وسیعی از آمریکای جنوبی را دربر می‌گیرد.",
        "قله اورست بلندترین نقطه سطح زمین نسبت به سطح دریا است.",
        "گرینلند بزرگ‌ترین جزیره جهان است و بخش زیادی از آن با یخ پوشیده شده است.",
        "دریای خزر بزرگ‌ترین پهنه آبی محصور در خشکی جهان از نظر مساحت است.",
        "اقیانوس اطلس میان قاره‌های آمریکا از یک سو و اروپا و آفریقا از سوی دیگر قرار گرفته است.",
        "مقیاس سلسیوس یکی از مقیاس‌های رایج برای بیان دما است و با نقطه انجماد و جوش آب تعریف تاریخی دارد.",
        "سال کبیسه برای هماهنگ نگه داشتن تقویم خورشیدی با طول واقعی سال اعتدالی استفاده می‌شود.",
        "زمین تقریباً ۲۴ ساعت برای یک چرخش نسبت به خورشید نیاز دارد و همین چرخش چرخه شب و روز را ایجاد می‌کند.",
        "یک سال زمین تقریباً ۳۶۵ روز و حدود ۶ ساعت طول می‌کشد و همین کسری به تقویم کبیسه منجر می‌شود.",
        "طول جغرافیایی برای تعیین موقعیت شرق و غرب یک مکان نسبت به نصف‌النهار مبدأ استفاده می‌شود.",
        "عرض جغرافیایی برای تعیین موقعیت شمال و جنوب یک مکان نسبت به خط استوا استفاده می‌شود.",
        "منطقه زمانی به نواحی‌ای گفته می‌شود که زمان استاندارد مشابه یا نزدیک دارند.",
        "سازمان ملل متحد در سال ۱۹۴۵ تأسیس شد و مقر اصلی آن در شهر نیویورک قرار دارد.",
    ),
}

FALLBACK_FACTS = tuple(
    (TOPIC_NAMES[topic], text, f"بانک پشتیبان {TOPIC_NAMES[topic]}")
    for topic, texts in FALLBACK_BANK.items()
    for text in texts
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_user_created ON seen_facts(user_id, created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_user_category ON seen_facts(user_id, category)")


def remember_user(user_id: int) -> None:
    now = time.time()
    with db() as conn:
        conn.execute("INSERT INTO users(user_id,first_seen,last_seen) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen", (user_id, now, now))


def normalize_fact(text: str) -> str:
    text = html.unescape(text or "").casefold()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[\u200c\u200d\u200f\u202a-\u202e]", "", text)
    text = text.translate(str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه"}))
    text = text.replace("٫", ".").replace("٬", ",")
    text = re.sub(r"[«»\"'“”`()\[\]{}،,؛:!؟?./\\|_+=*-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fact_key(text: str, source: str = "") -> str:
    return hashlib.sha256(normalize_fact(text).encode("utf-8")).hexdigest()


def has_seen(user_id: int, key: str) -> bool:
    with db() as conn:
        return conn.execute("SELECT 1 FROM seen_facts WHERE user_id=? AND fact_key=? LIMIT 1", (user_id, key)).fetchone() is not None


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


def word_shingles(text: str) -> set[str]:
    stop = {"است", "در", "از", "به", "با", "برای", "و", "که", "را", "این", "آن", "یک", "های", "می", "شود", "دارد"}
    return {w for w in normalize_fact(text).split() if len(w) > 1 and w not in stop}


def char_shingles(text: str, size: int = 4) -> set[str]:
    value = normalize_fact(text).replace(" ", "")
    if len(value) <= size:
        return {value} if value else set()
    return {value[i:i + size] for i in range(len(value) - size + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity_score(a: str, b: str) -> float:
    if fact_key(a) == fact_key(b):
        return 1.0
    return max(jaccard(word_shingles(a), word_shingles(b)), jaccard(char_shingles(a), char_shingles(b)))


def is_user_duplicate(user_id: int, text: str) -> bool:
    if has_seen(user_id, fact_key(text)):
        return True
    with db() as conn:
        rows = conn.execute("SELECT text FROM seen_facts WHERE user_id=? AND text!='' ORDER BY created_at DESC LIMIT 750", (user_id,)).fetchall()
    return any(similarity_score(text, row[0]) >= 0.84 for row in rows)


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
    windows = [(0, 2), (1, 3), (2, 4), (0, 3), (1, 4)]
    random.shuffle(windows)
    for a, b in windows:
        candidate = " ".join(sentences[a:b]).strip()
        if candidate and candidate not in result:
            result.append(candidate)
    return result


async def source_wikipedia(session: aiohttp.ClientSession, topic: str | None):
    queries = list(TOPICS.get(topic or "new", TOPICS["new"]))
    random.shuffle(queries)
    for query in queries[:12]:
        data = await get_json(session, "https://fa.wikipedia.org/w/api.php", {"action":"query","format":"json","generator":"search","gsrsearch":query,"gsrnamespace":0,"gsrlimit":25,"prop":"extracts|info","exintro":1,"explaintext":1,"inprop":"url"})
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
            if any(prefix in title for prefix in ("کاربر:", "بحث:", "الگو:", "پرونده:", "رده:", "فهرست ")):
                continue
            if not is_relevant(title + " " + extract, topic):
                continue
            for text in variants(extract):
                if usable(text):
                    return text, TOPIC_NAMES.get(topic or "new", "دانستنی"), "ویکی‌پدیای فارسی", fact_key(text)
    return None


async def source_wikipedia_random(session: aiohttp.ClientSession, topic: str | None):
    for _ in range(3):
        data = await get_json(session, "https://fa.wikipedia.org/w/api.php", {"action":"query","format":"json","generator":"random","grnnamespace":0,"grnlimit":35,"prop":"extracts|info","exintro":1,"explaintext":1,"inprop":"url"})
        if not isinstance(data, dict):
            continue
        pages = list(data.get("query", {}).get("pages", {}).values())
        random.shuffle(pages)
        for page in pages:
            title = clean(str(page.get("title", "")))
            extract = clean(str(page.get("extract", "")))
            url = str(page.get("fullurl", ""))
            if not url.startswith("https://fa.wikipedia.org/") or any(prefix in title for prefix in ("کاربر:", "بحث:", "الگو:", "پرونده:", "رده:", "فهرست ")):
                continue
            if not is_relevant(title + " " + extract, topic):
                continue
            for text in variants(extract):
                if usable(text):
                    return text, TOPIC_NAMES.get(topic or "new", "دانستنی"), "ویکی‌پدیای فارسی — تصادفی", fact_key(text)
    return None


async def source_wikidata_topic(session: aiohttp.ClientSession, topic: str | None):
    topic = topic or "new"
    queries = list(TOPICS.get(topic, TOPICS["new"]))
    random.shuffle(queries)
    for query in queries[:12]:
        data = await get_json(session, "https://www.wikidata.org/w/api.php", {"action":"wbsearchentities","search":query,"language":"fa","uselang":"fa","format":"json","limit":25,"type":"item"})
        if not isinstance(data, dict):
            continue
        hits = data.get("search", [])
        random.shuffle(hits)
        for hit in hits:
            label = clean(str(hit.get("label", "")))
            desc = clean(str(hit.get("description", "")))
            if not (label and desc):
                continue
            text = clean(f"در موضوع {TOPIC_NAMES.get(topic, 'دانستنی')}، «{label}» {desc} است.")
            if usable(text) and is_relevant(text, topic):
                return text, TOPIC_NAMES.get(topic, "دانستنی"), "ویکی‌داده", fact_key(text)
    return None


async def source_football(session: aiohttp.ClientSession):
    for loader in (source_wikipedia, source_wikipedia_random, source_wikidata_topic):
        try:
            value = await loader(session, "football")
        except Exception:
            value = None
        if value and value[1] == "فوتبال" and usable(value[0]) and is_relevant(value[0], "football"):
            return value[0], "فوتبال", value[2] + " — فوتبال", value[3]
    return None


async def source_nasa(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "space"):
        return None
    for _ in range(6):
        offset = random.randint(1, 3500)
        day = time.strftime("%Y-%m-%d", time.gmtime(time.time() - offset * 86400))
        data = await get_json(session, "https://api.nasa.gov/planetary/apod", {"api_key": os.getenv("NASA_API_KEY", "DEMO_KEY"), "date": day})
        if not isinstance(data, dict) or not data.get("date"):
            continue
        title = clean(str(data.get("title", "محتوای نجومی")))
        media = "تصویر" if data.get("media_type") == "image" else "رسانه"
        text = clean(f"ناسا در آرشیو تصویر نجومی روز، در تاریخ {data['date']} محتوایی با عنوان «{title}» ثبت کرده است؛ نوع این محتوا {media} است.")
        if usable(text):
            return text, "فضا", "ناسا", fact_key(text)
    return None


WORLD_COUNTRIES = {"IRN":"ایران","FRA":"فرانسه","DEU":"آلمان","BRA":"برزیل","JPN":"ژاپن","IND":"هند","CAN":"کانادا","ESP":"اسپانیا","ITA":"ایتالیا","TUR":"ترکیه","EGY":"مصر","AUS":"استرالیا","MEX":"مکزیک","KOR":"کره جنوبی","ZAF":"آفریقای جنوبی","GBR":"بریتانیا","USA":"ایالات متحده","NOR":"نروژ","SWE":"سوئد","CHN":"چین"}
WORLD_INDICATORS = {"SP.POP.TOTL":"جمعیت","NY.GDP.MKTP.CD":"تولید ناخالص داخلی","SP.DYN.LE00.IN":"امید به زندگی","IT.NET.USER.ZS":"درصد استفاده از اینترنت","EG.ELC.ACCS.ZS":"درصد دسترسی به برق","EN.ATM.CO2E.PC":"انتشار سرانه دی‌اکسیدکربن"}


async def source_world_bank(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "world"):
        return None
    indicator, name = random.choice(list(WORLD_INDICATORS.items()))
    code, country = random.choice(list(WORLD_COUNTRIES.items()))
    data = await get_json(session, f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}", {"format":"json", "per_page":40})
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
        return None
    rows = [r for r in data[1] if r.get("value") is not None]
    if not rows:
        return None
    row = random.choice(rows)
    try:
        value = float(row["value"])
        number = f"{value:,.2f}" if indicator not in ("SP.POP.TOTL", "NY.GDP.MKTP.CD") else f"{int(value):,}"
        number = number.replace(",", "،").replace(".", "٫")
    except (TypeError, ValueError):
        return None
    if indicator in ("IT.NET.USER.ZS", "EG.ELC.ACCS.ZS"):
        number += " درصد"
    text = clean(f"طبق داده‌های بانک جهانی، شاخص {name} برای کشور {country} در سال {row.get('date')} حدود {number} ثبت شده است.")
    return (text, "جهان", "بانک جهانی", fact_key(text)) if usable(text) else None


async def source_usgs(session: aiohttp.ClientSession, topic: str | None):
    if topic not in (None, "nature"):
        return None
    feed = random.choice(("significant_month", "4.5_month", "2.5_month", "1.0_month"))
    data = await get_json(session, f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson")
    if not isinstance(data, dict) or not data.get("features"):
        return None
    item = random.choice(data["features"])
    props = item.get("properties", {})
    magnitude = props.get("mag")
    event_id = str(item.get("id", ""))
    place = clean(str(props.get("place", "یک نقطه ثبت‌شده")))
    if magnitude is None or not event_id:
        return None
    text = clean(f"در داده‌های سازمان زمین‌شناسی آمریکا، زمین‌لرزه‌ای در {place} با بزرگای حدود {float(magnitude):.1f} و شناسه رویداد {event_id} ثبت شده است.")
    return (text, "طبیعت", "سازمان زمین‌شناسی آمریکا", fact_key(text)) if usable(text) else None


async def _try_loader(loader, session, topic):
    try:
        return await loader(session, topic)
    except Exception:
        return None


async def get_new_fact(user_id: int, topic: str | None = None):
    remember_user(user_id)
    if topic not in TOPICS:
        topic = "new"
    if topic == "football":
        loaders: list[Callable[..., Awaitable[Any]]] = [source_football]
    else:
        loaders = [source_wikipedia, source_wikipedia_random, source_wikidata_topic]
        if topic in (None, "space"):
            loaders.append(source_nasa)
        if topic in (None, "world"):
            loaders.append(source_world_bank)
        if topic in (None, "nature"):
            loaders.append(source_usgs)

    async with aiohttp.ClientSession(timeout=TIMEOUT, headers={"User-Agent":"AmirFacts/8.0"}) as session:
        for _ in range(12):
            order = list(loaders)
            random.shuffle(order)
            results = await asyncio.gather(*[_try_loader(loader, session, topic) for loader in order], return_exceptions=False)
            for value in results:
                if not value:
                    continue
                text, category, source, _ = value
                if topic != "new" and category != TOPIC_NAMES[topic]:
                    continue
                if not usable(text) or not is_relevant(text, topic):
                    continue
                if is_user_duplicate(user_id, text):
                    continue
                return text, category, source, fact_key(text)

    if topic == "new":
        offline_candidates = [(TOPIC_NAMES["new"], text, "بانک پشتیبان دانستنی") for text in FALLBACK_BANK["new"]]
    else:
        offline_candidates = [(TOPIC_NAMES[topic], text, f"بانک پشتیبان {TOPIC_NAMES[topic]}") for text in FALLBACK_BANK[topic]]
    random.shuffle(offline_candidates)
    for category, text, source in offline_candidates:
        if not usable(text) or (topic != "new" and not is_relevant(text, topic)):
            continue
        if is_user_duplicate(user_id, text):
            continue
        return text, category, source, fact_key(text)

    async with aiohttp.ClientSession(timeout=TIMEOUT, headers={"User-Agent":"AmirFacts/8.0-last-chance"}) as session:
        for _ in range(48):
            order = list(loaders)
            random.shuffle(order)
            value = await _try_loader(random.choice(order), session, topic)
            if not value:
                continue
            text, category, source, _ = value
            if topic != "new" and category != TOPIC_NAMES[topic]:
                continue
            if usable(text) and is_relevant(text, topic) and not is_user_duplicate(user_id, text):
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
    rows = ((("🎲 فکت جدید", "fact:new"), ("⚽ فوتبال", "fact:football")), (("🌌 فضا", "fact:space"), ("🧠 علم", "fact:science")), (("💻 فناوری", "fact:technology"), ("🌿 طبیعت", "fact:nature")), (("🏛️ تاریخ", "fact:history"), ("🌍 جهان", "fact:world")))
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
    await bot.send_message(message.chat.id, "🚀 <b>AmirFacts</b>\n\nفکت‌های فارسی، منبع‌دار و غیرتکراری.", reply_markup=keyboard())


async def send_fact(chat_id: int, user_id: int, topic: str | None = None) -> None:
    if not allowed(user_id):
        await bot.send_message(chat_id, "⏳ یه کم آروم‌تر 😄")
        return
    await bot.send_dice(chat_id, emoji="🎲")
    status = await bot.send_message(chat_id, "🔎 <i>از چند منبع دنبال یک فکت تازه و غیرتکراری می‌گردم...</i>")
    result = await get_new_fact(user_id, topic)
    if not result:
        await bot.edit_message_text("🔄 فعلاً یک فکت قابل‌اعتماد و کاملاً جدید برای این عنوان پیدا نشد.", chat_id=chat_id, message_id=status.message_id, reply_markup=keyboard())
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
