# ⚡ AmirXProxy - Single File Edition
# فقط همین فایل را با پسوند .py ذخیره کن.
#
# TOKEN RO INJA BEZAR:
# توکن واقعی BotFather را فقط در خط BOT_TOKEN قرار بده و آن را منتشر نکن.
#
# نصب وابستگی‌ها:
# pip install pyTelegramBotAPI aiohttp cryptography
#
# اجرا:
# python AmirXProxy_single.py
#
from __future__ import annotations

# ===== INLINED FROM AmirXProxy/config.py =====
"""
==================================================
AMIRXPROXY CONFIG
==================================================

This is the ONLY file you need to touch to get the bot running.
Everything important is at the top of this file.
"""

# ==================================================
# TOKEN RO INJA BEZAR
# ==================================================
# 1. Open a chat with @BotFather on Telegram.
# 2. Create a bot (or reuse one) and copy the token it gives you.
# 3. Paste it between the quotes below, replacing the placeholder text.
# ==================================================
BOT_TOKEN = "TOKEN RO INJA BEZAR"
# ==================================================


# ==================================================
# ADMIN ID RO INJA BEZAR
# ==================================================
# Put your numeric Telegram user id(s) here to unlock /admin.
# You can get your id from @userinfobot on Telegram.
# Example: ADMIN_IDS = [123456789]
# ==================================================
ADMIN_IDS: list[int] = []
# ==================================================


# --------------------------------------------------
# Optional: environment variable overrides.
# This block is OPTIONAL and only used if you set the matching
# environment variables yourself. If you don't know what an
# environment variable is, ignore this completely -- the values
# above are enough to run the bot.
# --------------------------------------------------
import os

if os.getenv("AMIRXPROXY_BOT_TOKEN"):
    BOT_TOKEN = os.getenv("AMIRXPROXY_BOT_TOKEN", BOT_TOKEN)

if os.getenv("AMIRXPROXY_ADMIN_IDS"):
    try:
        ADMIN_IDS = [
            int(x.strip())
            for x in os.getenv("AMIRXPROXY_ADMIN_IDS", "").split(",")
            if x.strip()
        ]
    except ValueError:
        pass


# ==================================================
# GENERAL BEHAVIOUR SETTINGS
# ==================================================

# How long a validated/scored proxy result stays "fresh" in the cache.
CACHE_TTL_MINUTES: int = 10

# Minimum seconds a single user must wait between heavy actions
# (starting a new scan, forcing a refresh, ...).
USER_COOLDOWN_SECONDS: int = 15

# Network timeouts (seconds). No network call is allowed to hang forever.
CONNECT_TIMEOUT: float = 3.0
READ_TIMEOUT: float = 3.0

# How many proxies may be validated over the network at the same time.
MAX_CONCURRENT_CHECKS: int = 20

# Hard ceiling on how many results a single user request can return.
# The bot only exposes 2 / 4 / 6 as buttons, but this constant is the
# real, enforced maximum used everywhere in the code.
MAX_RESULTS_PER_REQUEST: int = 6

# The quantities offered to the user as inline buttons on /start.
RESULT_QUANTITY_OPTIONS: list[int] = [2, 4, 6]

# How often (minutes) the optional background refresh job runs.
BACKGROUND_REFRESH_MINUTES: int = 15

# Enable/disable the periodic background refresh job entirely.
ENABLE_BACKGROUND_REFRESH: bool = True

# How many candidates we try to keep "healthy" in cache before we stop
# aggressively refreshing (keeps the bot from hammering sources).
TARGET_HEALTHY_POOL_SIZE: int = 24

# ==================================================
# WHERE THE RANKING SCORE IS CALCULATED
# ==================================================
# The actual formula lives in services/scorer.py -> calculate_score().
# These weights (must sum to 1.0) control how much each factor matters.
SCORE_WEIGHT_HEALTH: float = 0.50
SCORE_WEIGHT_LATENCY: float = 0.25
SCORE_WEIGHT_FRESHNESS: float = 0.15
SCORE_WEIGHT_CONFIDENCE: float = 0.10

# Latency (ms) considered "instant" (score contribution saturates here).
LATENCY_EXCELLENT_MS: int = 100
# Latency (ms) beyond which the latency score contribution is ~0.
LATENCY_WORST_MS: int = 1200

# A candidate older than this (minutes since last_checked) is treated as
# stale for freshness scoring purposes.
FRESHNESS_STALE_AFTER_MINUTES: int = 30

# How many independent sources a proxy needs to be seen in before it gets
# full "confidence" credit.
CONFIDENCE_SOURCE_CAP: int = 3

# ==================================================
# LOGGING
# ==================================================
LOG_LEVEL: str = "INFO"
LOG_FILE: str | None = None  # e.g. "amirxproxy.log", or None for console only

# ==================================================
# NETWORKING / HTTP
# ==================================================
HTTP_USER_AGENT: str = "AmirXProxy/1.0 (+https://github.com) source-fetcher"
SOURCE_FETCH_TIMEOUT: float = 8.0



# ===== INLINED FROM AmirXProxy/utils/logging.py =====
"""Central logging setup.

Never logs BOT_TOKEN or secrets. Use :func:`redact_secret` whenever a
proxy secret might end up in a log line.
"""


import logging
import sys



def setup_logging() -> logging.Logger:
    logger = logging.getLogger("amirxproxy")
    if logger.handlers:
        return logger  # already configured (avoid duplicate handlers)

    level = getattr(logging, str(LOG_LEVEL).upper(), logging.INFO)
    logger.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    if LOG_FILE:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


def redact_secret(secret: str | None) -> str:
    """Return a short, safe-to-log fingerprint of a proxy secret."""
    if not secret:
        return "<none>"
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}…{secret[-4:]} ({len(secret)} chars)"


log = setup_logging()


# ===== INLINED FROM AmirXProxy/utils/time.py =====
"""Small time helpers shared across the project."""


import time


def now() -> float:
    return time.time()


def seconds_since(timestamp: float | None) -> float | None:
    if timestamp is None:
        return None
    return max(0.0, now() - timestamp)


def humanize_ago(timestamp: float | None) -> str:
    """Human readable Persian "time ago" string for status/results screens."""
    if timestamp is None:
        return "هرگز"

    delta = seconds_since(timestamp)
    if delta is None:
        return "هرگز"

    if delta < 20:
        return "همین الان"
    if delta < 60:
        return f"{int(delta)} ثانیه پیش"
    minutes = int(delta // 60)
    if minutes < 60:
        return f"{minutes} دقیقه پیش"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours} ساعت پیش"
    days = int(hours // 24)
    return f"{days} روز پیش"


def clock_hhmm(timestamp: float | None) -> str:
    if timestamp is None:
        return "--:--"
    return time.strftime("%H:%M", time.localtime(timestamp))


# ===== INLINED FROM AmirXProxy/models/proxy.py =====
"""Data model for a proxy candidate/record tracked by AmirXProxy."""


import time
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum


class ProxyScheme(str, Enum):
    """Supported proxy "kinds" the bot knows how to parse/validate."""

    MTPROTO = "mtproto"
    SOCKS5 = "socks5"
    HTTP = "http"


class ValidationState(str, Enum):
    """Result of the validation pipeline for a single candidate."""

    UNKNOWN = "UNKNOWN"
    VALID = "VALID"
    INVALID = "INVALID"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"


class Quality(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    SLOW = "slow"
    UNAVAILABLE = "unavailable"

    @property
    def label_fa(self) -> str:
        return {
            Quality.EXCELLENT: "🟢 عالی",
            Quality.GOOD: "🟢 خوب",
            Quality.FAIR: "🟡 متوسط",
            Quality.SLOW: "🟠 کند",
            Quality.UNAVAILABLE: "🔴 غیرفعال",
        }[self]


@dataclass
class Proxy:
    """A single, deduplicated, logical proxy record.

    ``id`` / ``raw_hash`` identify the *logical* connection (server, port,
    secret, scheme). Everything else is state accumulated while the bot
    collects, validates and ranks candidates.
    """

    server: str
    port: int
    scheme: ProxyScheme
    secret: str | None = None

    # provenance
    source: set[str] = field(default_factory=set)
    source_count: int = 1
    raw_hash: str = ""

    # timestamps (unix seconds)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    last_checked: float | None = None

    # validation / quality
    latency_ms: float | None = None
    is_valid: bool = False
    is_alive: bool = False
    state: ValidationState = ValidationState.UNKNOWN
    verification_error: str | None = None
    score: float = 0.0
    quality: Quality = Quality.UNAVAILABLE

    @property
    def id(self) -> str:
        return self.raw_hash

    def connect_link(self) -> str:
        """Return the tg:// deep link users can tap to add the proxy."""
        if self.scheme == ProxyScheme.MTPROTO:
            params = {"server": self.server, "port": str(self.port)}
            if self.secret:
                params["secret"] = self.secret
            return "https://t.me/proxy?" + urllib.parse.urlencode(params)
        if self.scheme == ProxyScheme.SOCKS5:
            params = {"server": self.server, "port": str(self.port)}
            return "https://t.me/socks?" + urllib.parse.urlencode(params)
        # generic http proxy has no official tg:// scheme, expose raw info
        return f"http://{self.server}:{self.port}"

    def scheme_label(self) -> str:
        return {
            ProxyScheme.MTPROTO: "📡 MTProto",
            ProxyScheme.SOCKS5: "🧦 SOCKS5",
            ProxyScheme.HTTP: "🌐 HTTP",
        }[self.scheme]

    def merge_source(self, other_source: str, seen_at: float | None = None) -> None:
        """Fold another discovery of the same logical proxy into this one."""
        if other_source not in self.source:
            self.source.add(other_source)
            self.source_count += 1
        self.last_seen = max(self.last_seen, seen_at or time.time())


# ===== INLINED FROM AmirXProxy/services/normalizer.py =====
"""Parsing + normalization of raw source text into :class:`Proxy` objects.

This module is the only place that understands the various "shapes" a
public proxy list can come in. It tolerates unrelated surrounding text,
HTML fragments, markdown, extra whitespace and URL-encoding, and never
raises on malformed input -- bad lines are simply skipped.
"""


import hashlib
import re
import urllib.parse


# tg://proxy?server=...&port=...&secret=...  OR  https://t.me/proxy?...
_MTPROTO_LINK_RE = re.compile(
    r"(?:tg://proxy|https?://t\.me/proxy)\?([^\s\"'<>\)\]]+)", re.IGNORECASE
)

# tg://socks?server=...&port=...  OR  https://t.me/socks?...
_SOCKS_LINK_RE = re.compile(
    r"(?:tg://socks|https?://t\.me/socks)\?([^\s\"'<>\)\]]+)", re.IGNORECASE
)

# bare "ip:port" lines used by several plain-text SOCKS/HTTP aggregators
_BARE_IP_PORT_RE = re.compile(
    r"(?<![\w.])((?:\d{1,3}\.){3}\d{1,3}):(\d{1,5})(?![\d])"
)

# server:port:secret "triplet" style lines some lists publish for MTProto
_TRIPLET_RE = re.compile(
    r"(?<![\w.])([a-zA-Z0-9][a-zA-Z0-9\-.]{0,253}):(\d{1,5}):([a-fA-F0-9]{16,34}|[A-Za-z0-9_\-]{16,64})(?![\w-])"
)

_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9\-.]{0,253}[a-zA-Z0-9])?$")
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def _valid_port(raw: str) -> int | None:
    try:
        port = int(raw)
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def _valid_server(raw: str) -> str | None:
    if not raw:
        return None
    server = raw.strip().strip(".").lower()
    if not server or len(server) > 255:
        return None
    if not _HOSTNAME_RE.match(server):
        return None
    return server


def _clean_secret(raw: str | None) -> str | None:
    if not raw:
        return None
    secret = urllib.parse.unquote(raw).strip()
    # normalize hex secrets to lowercase; base64url secrets are case sensitive
    if _HEX_RE.match(secret):
        secret = secret.lower()
    return secret or None


def compute_fingerprint(scheme: ProxyScheme, server: str, port: int, secret: str | None) -> str:
    """Deterministic identity of a *logical* proxy, used for deduplication."""
    payload = f"{scheme.value}|{server}|{port}|{secret or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_proxy(scheme: ProxyScheme, server_raw: str, port_raw: str,
                  secret_raw: str | None, source_name: str) -> Proxy | None:
    server = _valid_server(server_raw)
    port = _valid_port(port_raw)
    if server is None or port is None:
        return None

    secret = _clean_secret(secret_raw)
    if scheme == ProxyScheme.MTPROTO and not secret:
        return None  # an MTProto proxy without a secret is not usable

    fingerprint = compute_fingerprint(scheme, server, port, secret)
    proxy = Proxy(server=server, port=port, scheme=scheme, secret=secret, raw_hash=fingerprint)
    proxy.source.add(source_name)
    return proxy


def _parse_mtproto_links(text: str, source_name: str) -> list[Proxy]:
    results: list[Proxy] = []
    for match in _MTPROTO_LINK_RE.finditer(text):
        query = urllib.parse.parse_qs(match.group(1), keep_blank_values=True)
        server_raw = query.get("server", [""])[0]
        port_raw = query.get("port", [""])[0]
        secret_raw = query.get("secret", [""])[0]
        proxy = _build_proxy(ProxyScheme.MTPROTO, server_raw, port_raw, secret_raw, source_name)
        if proxy:
            results.append(proxy)
    return results


def _parse_socks_links(text: str, source_name: str) -> list[Proxy]:
    results: list[Proxy] = []
    for match in _SOCKS_LINK_RE.finditer(text):
        query = urllib.parse.parse_qs(match.group(1), keep_blank_values=True)
        server_raw = query.get("server", [""])[0]
        port_raw = query.get("port", [""])[0]
        proxy = _build_proxy(ProxyScheme.SOCKS5, server_raw, port_raw, None, source_name)
        if proxy:
            results.append(proxy)
    return results


def _parse_triplets(text: str, source_name: str) -> list[Proxy]:
    results: list[Proxy] = []
    for server_raw, port_raw, secret_raw in _TRIPLET_RE.findall(text):
        proxy = _build_proxy(ProxyScheme.MTPROTO, server_raw, port_raw, secret_raw, source_name)
        if proxy:
            results.append(proxy)
    return results


def _parse_bare_ip_port(text: str, source_name: str) -> list[Proxy]:
    """Bare ``ip:port`` lines are ambiguous (SOCKS5 vs HTTP). Public lists
    that publish this shape for Telegram are, in practice, SOCKS5 lists,
    so that is the heuristic used here. This is documented, not silently
    assumed to be perfect."""
    results: list[Proxy] = []
    for server_raw, port_raw in _BARE_IP_PORT_RE.findall(text):
        proxy = _build_proxy(ProxyScheme.SOCKS5, server_raw, port_raw, None, source_name)
        if proxy:
            results.append(proxy)
    return results


def extract_candidates(text: str, source_name: str) -> list[Proxy]:
    """Extract every recognizable proxy candidate out of arbitrary text."""
    if not text:
        return []

    candidates: list[Proxy] = []
    candidates.extend(_parse_mtproto_links(text, source_name))
    candidates.extend(_parse_socks_links(text, source_name))
    candidates.extend(_parse_triplets(text, source_name))

    # Only fall back to the ambiguous bare ip:port heuristic when nothing
    # more specific was found, to avoid double-counting hosts that also
    # appear inside a proper tg://proxy link.
    if not candidates:
        candidates.extend(_parse_bare_ip_port(text, source_name))

    return candidates


# ===== INLINED FROM AmirXProxy/services/mtproto_probe.py =====
"""Real protocol-level probe for Telegram MTProto proxies.

This performs the actual "obfuscated2" handshake described by Telegram's
own transport documentation (https://core.telegram.org/mtproto/mtproto-transports)
and then sends a genuine ``req_pq_multi`` request. If the remote endpoint
answers with a correctly framed, correctly encrypted ``resPQ`` response
that echoes back our nonce, we have cryptographic proof that:

  1. the host+port is a real MTProto endpoint, and
  2. the supplied secret is the one actually configured on that endpoint.

This goes well beyond "is the TCP port open" -- a closed/wrong secret or
a non-MTProto service will simply not produce a valid response and the
probe is reported as failed/unsupported instead of guessed.

Limitation (documented, not hidden): proxies using the "fake-TLS" secret
format (``ee``-prefixed secrets bound to a domain) use a different,
TLS-ClientHello based handshake that is not implemented in v1. For those,
callers fall back to a plain TCP reachability check -- this is explicitly
surfaced to the user/admin rather than pretended to be a full check.
"""


import asyncio
import base64
import hashlib
import os
import re
import struct
import time
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_REQ_PQ_MULTI = 0xBE7E8EF1
_RES_PQ = 0x05162463

_BANNED_FIRST_INTS = {0x44414548, 0x54534F50, 0x20544547, 0x4954504F, 0x02010316, 0xDDDDDDDD, 0xEEEEEEEE}
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


class ProbeUnsupported(Exception):
    """Raised when the secret format cannot be probed at the protocol level."""


@dataclass
class ProbeResult:
    success: bool
    unsupported: bool = False
    error: str | None = None


def _decode_secret(secret: str) -> bytes:
    s = secret.strip()
    if s and len(s) % 2 == 0 and _HEX_RE.match(s):
        return bytes.fromhex(s)
    padded = s + "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(padded)


def _secret16(secret: str) -> bytes:
    raw = _decode_secret(secret)
    if len(raw) == 16:
        return raw
    if len(raw) == 17 and raw[0] == 0xDD:
        return raw[1:]
    if len(raw) >= 17 and raw[0] == 0xEE:
        raise ProbeUnsupported("fake-TLS (ee-prefixed) secrets are not probed in v1")
    raise ProbeUnsupported(f"unsupported secret length: {len(raw)} bytes")


def _build_obfuscated_keys(secret16: bytes):
    while True:
        rnd = os.urandom(56)
        if rnd[0] == 0xEF:
            continue
        first_int = struct.unpack("<I", rnd[0:4])[0]
        second_int = struct.unpack("<I", rnd[4:8])[0]
        if first_int in _BANNED_FIRST_INTS or second_int == 0:
            continue
        break

    protocol = struct.pack("<I", 0xDDDDDDDD)  # "intermediate" transport marker
    dc_marker = struct.pack("<H", 0xFCFF)
    tail = os.urandom(2)
    init = rnd + protocol + dc_marker + tail  # 64 bytes total
    init_rev = init[::-1]

    encrypt_key = hashlib.sha256(init[8:40] + secret16).digest()
    encrypt_iv = init[40:56]
    decrypt_key = hashlib.sha256(init_rev[8:40] + secret16).digest()
    decrypt_iv = init_rev[40:56]
    return init, encrypt_key, encrypt_iv, decrypt_key, decrypt_iv


async def probe_mtproto(server: str, port: int, secret: str,
                         connect_timeout: float, read_timeout: float) -> ProbeResult:
    """Attempt a real MTProto handshake + req_pq round trip.

    Never raises to the caller: all failure modes are captured in the
    returned :class:`ProbeResult`.
    """
    try:
        secret16 = _secret16(secret)
    except ProbeUnsupported as exc:
        return ProbeResult(success=False, unsupported=True, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - malformed secret encoding
        return ProbeResult(success=False, unsupported=True, error=f"bad secret encoding: {exc}")

    writer = None
    try:
        init, enc_key, enc_iv, dec_key, dec_iv = _build_obfuscated_keys(secret16)

        encryptor = Cipher(algorithms.AES(enc_key), modes.CTR(enc_iv)).encryptor()
        decryptor = Cipher(algorithms.AES(dec_key), modes.CTR(dec_iv)).decryptor()

        encrypted_init = encryptor.update(init)
        final_init = init[:56] + encrypted_init[56:64]

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(server, port), timeout=connect_timeout
        )
        writer.write(final_init)
        await writer.drain()

        nonce = os.urandom(16)
        body = struct.pack("<I", _REQ_PQ_MULTI) + nonce
        message_id = int(time.time() * (2 ** 32)) & ~3
        message = struct.pack("<Q", 0) + struct.pack("<Q", message_id) + struct.pack("<I", len(body)) + body
        frame = struct.pack("<I", len(message)) + message

        writer.write(encryptor.update(frame))
        await writer.drain()

        raw_len = await asyncio.wait_for(reader.readexactly(4), timeout=read_timeout)
        resp_len = struct.unpack("<I", decryptor.update(raw_len))[0]
        if not (0 < resp_len <= 65536):
            return ProbeResult(success=False, error="invalid response frame length")

        raw_body = await asyncio.wait_for(reader.readexactly(resp_len), timeout=read_timeout)
        decoded = decryptor.update(raw_body)
        if len(decoded) < 40:
            return ProbeResult(success=False, error="response too short")

        constructor = struct.unpack("<I", decoded[20:24])[0]
        if constructor != _RES_PQ:
            return ProbeResult(success=False, error=f"unexpected constructor 0x{constructor:08x}")

        resp_nonce = decoded[24:40]
        if resp_nonce != nonce:
            return ProbeResult(success=False, error="nonce mismatch in response")

        return ProbeResult(success=True)

    except asyncio.TimeoutError:
        return ProbeResult(success=False, error="timeout")
    except (ConnectionError, OSError) as exc:
        return ProbeResult(success=False, error=f"connection error: {exc}")
    except asyncio.IncompleteReadError:
        return ProbeResult(success=False, error="connection closed early")
    except Exception as exc:  # noqa: BLE001 - defensive: never crash the scan
        return ProbeResult(success=False, error=f"unexpected error: {exc}")
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass


# ===== INLINED FROM AmirXProxy/services/deduplicator.py =====
"""Deduplication of normalized proxy candidates.

The fingerprint (``raw_hash``) already identifies a logical proxy (same
scheme + server + port + secret regardless of how the source formatted
the URL). This module folds repeated discoveries into one record while
preserving source history and the most recent discovery time.
"""




def deduplicate(candidates: list[Proxy]) -> list[Proxy]:
    """Collapse a list of raw candidates into unique logical proxies."""
    by_fingerprint: dict[str, Proxy] = {}

    for candidate in candidates:
        existing = by_fingerprint.get(candidate.raw_hash)
        if existing is None:
            by_fingerprint[candidate.raw_hash] = candidate
            continue

        # merge: keep the first record, fold in the new discovery
        for source_name in candidate.source:
            existing.merge_source(source_name, seen_at=candidate.last_seen)
        existing.first_seen = min(existing.first_seen, candidate.first_seen)

    unique = list(by_fingerprint.values())
    removed = len(candidates) - len(unique)
    if removed:
        log.info("Removed %d duplicate candidate(s), %d unique remain", removed, len(unique))
    return unique


# ===== INLINED FROM AmirXProxy/services/scorer.py =====
"""Quality score calculation.

This is the ONLY place that decides how "good" a proxy looks. The
formula is intentionally simple and easy to tune from py:

    score = 100 * (
        HEALTH_WEIGHT      * health_component      +
        LATENCY_WEIGHT     * latency_component      +
        FRESHNESS_WEIGHT   * freshness_component    +
        CONFIDENCE_WEIGHT  * confidence_component
    )

Every component is normalized to the 0..1 range before weighting.
"""


import time



def _health_component(proxy: Proxy) -> float:
    if not proxy.is_alive:
        return 0.0
    if not proxy.is_valid:
        return 0.25  # reachable but failed protocol validation
    return 1.0


def _latency_component(proxy: Proxy) -> float:
    if proxy.latency_ms is None:
        return 0.0
    if proxy.latency_ms <= LATENCY_EXCELLENT_MS:
        return 1.0
    if proxy.latency_ms >= LATENCY_WORST_MS:
        return 0.0
    span = LATENCY_WORST_MS - LATENCY_EXCELLENT_MS
    return max(0.0, 1.0 - (proxy.latency_ms - LATENCY_EXCELLENT_MS) / span)


def _freshness_component(proxy: Proxy) -> float:
    if proxy.last_checked is None:
        return 0.0
    age_minutes = (time.time() - proxy.last_checked) / 60.0
    if age_minutes <= 0:
        return 1.0
    if age_minutes >= FRESHNESS_STALE_AFTER_MINUTES:
        return 0.0
    return max(0.0, 1.0 - age_minutes / FRESHNESS_STALE_AFTER_MINUTES)


def _confidence_component(proxy: Proxy) -> float:
    cap = max(1, CONFIDENCE_SOURCE_CAP)
    return min(1.0, proxy.source_count / cap)


def calculate_score(proxy: Proxy) -> float:
    """Return a 0..100 quality score for a proxy. Health always dominates:
    an unreachable proxy scores 0 regardless of every other factor."""
    if not proxy.is_alive:
        return 0.0

    score = (
        SCORE_WEIGHT_HEALTH * _health_component(proxy)
        + SCORE_WEIGHT_LATENCY * _latency_component(proxy)
        + SCORE_WEIGHT_FRESHNESS * _freshness_component(proxy)
        + SCORE_WEIGHT_CONFIDENCE * _confidence_component(proxy)
    )
    return round(score * 100, 2)


def classify_quality(proxy: Proxy) -> Quality:
    """Human-friendly label. Health/validity always takes priority over
    raw latency numbers -- a fast but invalid proxy is never "excellent"."""
    if not proxy.is_alive or not proxy.is_valid:
        return Quality.UNAVAILABLE

    latency = proxy.latency_ms if proxy.latency_ms is not None else float("inf")
    if latency <= 100:
        return Quality.EXCELLENT
    if latency <= 200:
        return Quality.GOOD
    if latency <= 350:
        return Quality.FAIR
    if latency <= 700:
        return Quality.SLOW
    return Quality.SLOW if proxy.score > 0 else Quality.UNAVAILABLE


def score_and_classify(proxy: Proxy) -> Proxy:
    proxy.score = calculate_score(proxy)
    proxy.quality = classify_quality(proxy)
    return proxy


def rank(proxies: list[Proxy]) -> list[Proxy]:
    """Score, classify and sort candidates best-first."""
    for proxy in proxies:
        score_and_classify(proxy)
    return sorted(proxies, key=lambda p: p.score, reverse=True)


# ===== INLINED FROM AmirXProxy/services/cache.py =====
"""In-memory cache of every proxy AmirXProxy currently knows about.

Version 1 keeps everything in a process-local dict guarded by an
``asyncio.Lock``. The public interface is intentionally small so this
can later be swapped for Redis or a database without touching callers.
"""


import asyncio
import time



class ProxyCache:
    def __init__(self, ttl_minutes: int | None = None) -> None:
        self.ttl_seconds = (ttl_minutes or CACHE_TTL_MINUTES) * 60
        self._store: dict[str, Proxy] = {}
        self._lock = asyncio.Lock()
        self.last_refresh: float | None = None
        self.last_refresh_stats: dict[str, int] = {}

    async def upsert_many(self, proxies: list[Proxy]) -> None:
        async with self._lock:
            for proxy in proxies:
                existing = self._store.get(proxy.raw_hash)
                if existing is None:
                    self._store[proxy.raw_hash] = proxy
                    continue
                # keep the freshest validation state, merge provenance
                existing.source |= proxy.source
                existing.source_count = max(existing.source_count, proxy.source_count)
                existing.first_seen = min(existing.first_seen, proxy.first_seen)
                existing.last_seen = max(existing.last_seen, proxy.last_seen)
                existing.last_checked = proxy.last_checked
                existing.latency_ms = proxy.latency_ms
                existing.is_alive = proxy.is_alive
                existing.is_valid = proxy.is_valid
                existing.state = proxy.state
                existing.verification_error = proxy.verification_error
                existing.score = proxy.score
                existing.quality = proxy.quality
            self.last_refresh = time.time()

    async def get_all(self) -> list[Proxy]:
        async with self._lock:
            return list(self._store.values())

    async def get_fresh_healthy(self, limit: int | None = None) -> list[Proxy]:
        """Currently healthy proxies whose last check is still within TTL."""
        cutoff = time.time() - self.ttl_seconds
        async with self._lock:
            healthy = [
                p for p in self._store.values()
                if p.is_alive and p.is_valid and p.last_checked and p.last_checked >= cutoff
            ]
        healthy.sort(key=lambda p: p.score, reverse=True)
        return healthy[:limit] if limit else healthy

    async def get_stale(self, limit: int | None = None) -> list[Proxy]:
        """Everything that is not currently 'fresh & healthy' -- candidates
        worth re-validating before we give up and collect from scratch."""
        cutoff = time.time() - self.ttl_seconds
        async with self._lock:
            stale = [
                p for p in self._store.values()
                if not (p.is_alive and p.is_valid and p.last_checked and p.last_checked >= cutoff)
            ]
        stale.sort(key=lambda p: p.last_checked or 0)
        return stale[:limit] if limit else stale

    async def size(self) -> int:
        async with self._lock:
            return len(self._store)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
        self.last_refresh = None

    async def stats(self) -> dict:
        async with self._lock:
            values = list(self._store.values())
        healthy = [p for p in values if p.is_alive and p.is_valid]
        unavailable = [p for p in values if not p.is_alive]
        latencies = [p.latency_ms for p in healthy if p.latency_ms is not None]
        return {
            "total": len(values),
            "healthy": len(healthy),
            "unavailable": len(unavailable),
            "validated": sum(1 for p in values if p.state.value not in ("UNKNOWN",)),
            "average_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
            "last_refresh": self.last_refresh,
        }


# a single process-wide cache instance shared by the whole bot
proxy_cache = ProxyCache()


# ===== INLINED FROM AmirXProxy/services/validator.py =====
"""Independent, per-candidate proxy validation.

Validation is intentionally separate from parsing: a URL "looking"
correct says nothing about whether the endpoint is actually alive. Each
candidate is validated on its own -- one bad/unreachable candidate can
never abort the rest of the scan.
"""


import asyncio
import time



async def _tcp_latency_check(server: str, port: int) -> tuple[bool, float | None, str | None]:
    """Bare TCP connect + latency measurement. Always attempted first."""
    started = time.perf_counter()
    writer = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(server, port), timeout=CONNECT_TIMEOUT
        )
        latency_ms = (time.perf_counter() - started) * 1000
        return True, latency_ms, None
    except asyncio.TimeoutError:
        return False, None, "timeout"
    except (ConnectionError, OSError) as exc:
        return False, None, f"connection error: {exc}"
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass


async def _socks5_handshake_check(server: str, port: int) -> tuple[bool, str | None]:
    """Real SOCKS5 method-negotiation handshake (RFC 1928, first message)."""
    writer = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(server, port), timeout=CONNECT_TIMEOUT
        )
        # version 5, 1 auth method offered: 0x00 (no auth)
        writer.write(b"\x05\x01\x00")
        await writer.drain()
        response = await asyncio.wait_for(reader.readexactly(2), timeout=READ_TIMEOUT)
        if response[0] != 0x05:
            return False, "not a SOCKS5 endpoint"
        if response[1] == 0xFF:
            return False, "no acceptable auth method"
        return True, None
    except asyncio.TimeoutError:
        return False, "timeout"
    except (ConnectionError, OSError, asyncio.IncompleteReadError) as exc:
        return False, f"connection error: {exc}"
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass


async def _http_proxy_check(server: str, port: int) -> tuple[bool, str | None]:
    """Send a minimal HTTP CONNECT and inspect the status line."""
    writer = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(server, port), timeout=CONNECT_TIMEOUT
        )
        request = (
            b"CONNECT example.com:443 HTTP/1.1\r\n"
            b"Host: example.com:443\r\n"
            b"Proxy-Connection: Keep-Alive\r\n\r\n"
        )
        writer.write(request)
        await writer.drain()
        status_line = await asyncio.wait_for(reader.readline(), timeout=READ_TIMEOUT)
        if not status_line.startswith(b"HTTP/"):
            return False, "no HTTP response"
        return True, None
    except asyncio.TimeoutError:
        return False, "timeout"
    except (ConnectionError, OSError) as exc:
        return False, f"connection error: {exc}"
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass


async def validate_proxy(proxy: Proxy, semaphore: asyncio.Semaphore) -> Proxy:
    """Validate a single proxy candidate. Mutates and returns it."""
    async with semaphore:
        proxy.last_checked = time.time()

        alive, latency_ms, tcp_error = await _tcp_latency_check(proxy.server, proxy.port)
        if not alive:
            proxy.is_alive = False
            proxy.is_valid = False
            proxy.state = ValidationState.TIMEOUT if tcp_error == "timeout" else ValidationState.UNAVAILABLE
            proxy.verification_error = tcp_error
            return proxy

        proxy.is_alive = True
        proxy.latency_ms = latency_ms

        try:
            if proxy.scheme == ProxyScheme.MTPROTO and proxy.secret:
                result = await probe_mtproto(
                    proxy.server, proxy.port, proxy.secret,
                    connect_timeout=CONNECT_TIMEOUT, read_timeout=READ_TIMEOUT,
                )
                if result.unsupported:
                    # protocol probe not implemented for this secret style;
                    # honestly fall back to "alive, but unverified protocol"
                    proxy.is_valid = True
                    proxy.state = ValidationState.VALID
                    proxy.verification_error = f"partial check only: {result.error}"
                elif result.success:
                    proxy.is_valid = True
                    proxy.state = ValidationState.VALID
                    proxy.verification_error = None
                else:
                    proxy.is_valid = False
                    proxy.state = ValidationState.INVALID
                    proxy.verification_error = result.error

            elif proxy.scheme == ProxyScheme.SOCKS5:
                ok, err = await _socks5_handshake_check(proxy.server, proxy.port)
                proxy.is_valid = ok
                proxy.state = ValidationState.VALID if ok else ValidationState.INVALID
                proxy.verification_error = err

            elif proxy.scheme == ProxyScheme.HTTP:
                ok, err = await _http_proxy_check(proxy.server, proxy.port)
                proxy.is_valid = ok
                proxy.state = ValidationState.VALID if ok else ValidationState.INVALID
                proxy.verification_error = err

            else:
                proxy.is_valid = False
                proxy.state = ValidationState.UNKNOWN
                proxy.verification_error = "unsupported scheme"

        except Exception as exc:  # noqa: BLE001 - one bad candidate must never abort the scan
            proxy.is_valid = False
            proxy.state = ValidationState.INVALID
            proxy.verification_error = f"unexpected validation error: {exc}"
            log.warning(
                "Validation crashed for %s:%s secret=%s -> %s",
                proxy.server, proxy.port, redact_secret(proxy.secret), exc,
            )

        return proxy


async def validate_all(proxies: list[Proxy], max_concurrency: int | None = None) -> list[Proxy]:
    """Validate many candidates with bounded concurrency."""
    if not proxies:
        return []
    semaphore = asyncio.Semaphore(max_concurrency or MAX_CONCURRENT_CHECKS)
    results = await asyncio.gather(*(validate_proxy(p, semaphore) for p in proxies))
    healthy = sum(1 for p in results if p.is_valid and p.is_alive)
    log.info("Validated %d candidate(s), %d passed", len(results), healthy)
    return list(results)


# ===== INLINED FROM AmirXProxy/sources/base.py =====
"""Common abstraction every proxy source must implement.

A "source" is nothing more than: fetch some public text, hand it to the
shared parser, and return whatever proxy candidates were found in it.
No parsing/scraping logic should live in the Telegram handlers -- it all
goes through this class (or a subclass of it).
"""


import time
from dataclasses import dataclass, field
from enum import Enum

import aiohttp



class SourceHealth(str, Enum):
    HEALTHY = "🟢 Healthy"
    DEGRADED = "🟡 Degraded"
    UNAVAILABLE = "🔴 Unavailable"


@dataclass
class SourceStats:
    """Runtime health bookkeeping for one source."""

    last_success: float | None = None
    last_error: str | None = None
    last_response_time: float | None = None
    consecutive_failures: int = 0
    last_candidate_count: int = 0
    parser_errors: int = 0

    @property
    def health(self) -> SourceHealth:
        if self.consecutive_failures == 0 and self.last_success is not None:
            return SourceHealth.HEALTHY
        if 0 < self.consecutive_failures < 3:
            return SourceHealth.DEGRADED
        return SourceHealth.UNAVAILABLE


class ProxySource:
    """Base class for every configured proxy source."""

    #: human readable name shown to admins/users
    name: str = "unnamed-source"
    #: where the public content lives
    url: str = ""
    #: category label, purely informational (github / public_web / ...)
    type: str = "generic"
    #: administrators can disable a source without deleting its config
    enabled: bool = True
    #: per-request timeout (seconds)
    timeout: float = SOURCE_FETCH_TIMEOUT
    #: higher priority sources are collected first
    priority: int = 0

    def __init__(self) -> None:
        self.stats = SourceStats()

    async def _fetch_text(self) -> str:
        """Download the raw text this source publishes. Real HTTP GET."""
        headers = {"User-Agent": HTTP_USER_AGENT}
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(self.url) as response:
                response.raise_for_status()
                return await response.text(errors="ignore")

    async def collect(self) -> list[Proxy]:
        """Fetch + parse this source. Never raises: failures are recorded
        on ``self.stats`` and an empty list is returned instead."""
        if not self.enabled:
            return []

        started = time.time()
        try:
            raw_text = await self._fetch_text()
        except Exception as exc:  # noqa: BLE001 - any network failure is expected here
            self.stats.consecutive_failures += 1
            self.stats.last_error = f"{type(exc).__name__}: {exc}"
            log.warning("Source '%s' failed: %s", self.name, self.stats.last_error)
            return []

        self.stats.last_response_time = time.time() - started

        try:
            candidates = extract_candidates(raw_text, source_name=self.name)
        except Exception as exc:  # noqa: BLE001 - never let a bad feed kill the scan
            self.stats.parser_errors += 1
            self.stats.consecutive_failures += 1
            self.stats.last_error = f"parser error: {exc}"
            log.warning("Source '%s' parser error: %s", self.name, exc)
            return []

        self.stats.consecutive_failures = 0
        self.stats.last_success = time.time()
        self.stats.last_candidate_count = len(candidates)
        log.info("Source '%s' returned %d candidate(s)", self.name, len(candidates))
        return candidates


# ===== INLINED FROM AmirXProxy/sources/github_source.py =====
"""Source implementation for public, unauthenticated GitHub raw files.

These are plain-text files (e.g. raw.githubusercontent.com/...) that list
proxy links one per line (or embedded inside other text). No GitHub API
token is required or used -- only public, anonymous HTTP GET requests.
"""




class GithubSource(ProxySource):
    type = "github"

    def __init__(self, name: str, url: str, enabled: bool = True,
                 timeout: float | None = None, priority: int = 0) -> None:
        super().__init__()
        self.name = name
        self.url = url
        self.enabled = enabled
        if timeout is not None:
            self.timeout = timeout
        self.priority = priority


# ===== INLINED FROM AmirXProxy/sources/public_web_source.py =====
"""Source implementation for generic public web pages / text endpoints.

Anything that is openly reachable without login, tokens or bypassing
access controls can be registered as this type: public aggregator pages,
open datasets, plain-text mirrors, etc.
"""




class PublicWebSource(ProxySource):
    type = "public_web"

    def __init__(self, name: str, url: str, enabled: bool = True,
                 timeout: float | None = None, priority: int = 0) -> None:
        super().__init__()
        self.name = name
        self.url = url
        self.enabled = enabled
        if timeout is not None:
            self.timeout = timeout
        self.priority = priority


# ===== INLINED FROM AmirXProxy/sources/registry.py =====
"""Centralised, admin-editable list of proxy sources.

To add a new source later: add one more entry to ``PROXY_SOURCES`` below.
Nothing else in the bot needs to change. Every source is a plain public
URL fetched with a normal HTTP GET -- no login, no private channels, no
bypassing of any access control.
"""



# NOTE: these are examples of real, publicly reachable aggregator files.
# Free/public proxy lists change ownership and uptime constantly -- if a
# source goes offline the bot will simply mark it 🔴 Unavailable and keep
# working from whatever sources remain healthy. Feel free to replace,
# disable or add entries.
PROXY_SOURCES: list[ProxySource] = [
    GithubSource(
        name="Argh94/Proxy-List (MTProto)",
        url="https://raw.githubusercontent.com/Argh94/Proxy-List/main/MTProto.txt",
        enabled=True,
        priority=10,
    ),
    GithubSource(
        name="SoliSpirit/mtproto",
        url="https://raw.githubusercontent.com/SoliSpirit/mtproto/master/all_proxies.txt",
        enabled=True,
        priority=8,
    ),
    GithubSource(
        name="iwh3n/tg-proxy",
        url="https://raw.githubusercontent.com/iwh3n/tg-proxy/main/proxys/All_Proxys.txt",
        enabled=True,
        priority=6,
    ),
    GithubSource(
        name="hookzof/socks5_list",
        url="https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        enabled=True,
        priority=5,
    ),
    PublicWebSource(
        name="clarketm/proxy-list (HTTP)",
        url="https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        enabled=False,  # generic HTTP proxies are usually irrelevant for Telegram; kept as an example
        priority=1,
    ),
]


def get_enabled_sources() -> list[ProxySource]:
    return sorted((s for s in PROXY_SOURCES if s.enabled), key=lambda s: -s.priority)


def get_all_sources() -> list[ProxySource]:
    return list(PROXY_SOURCES)


# ===== INLINED FROM AmirXProxy/services/collector.py =====
"""Fan-out collection across every enabled proxy source.

One failing source must never take down the scan: sources are awaited
with ``return_exceptions=True`` and each source already protects itself
internally (see :class:`sources.base.ProxySource`).
"""


import asyncio



async def collect_raw_candidates(sources: list[ProxySource] | None = None) -> list[Proxy]:
    """Collect + deduplicate candidates from every enabled source."""
    active_sources = sources if sources is not None else get_enabled_sources()
    if not active_sources:
        log.warning("No enabled proxy sources are configured")
        return []

    log.info("Source scan started across %d source(s)", len(active_sources))
    results = await asyncio.gather(
        *(source.collect() for source in active_sources), return_exceptions=True
    )

    raw_candidates: list[Proxy] = []
    for source, result in zip(active_sources, results):
        if isinstance(result, Exception):
            log.warning("Source '%s' raised unexpectedly: %s", source.name, result)
            continue
        raw_candidates.extend(result)

    log.info("Collected %d raw candidate(s) before deduplication", len(raw_candidates))
    unique = deduplicate(raw_candidates)
    return unique


# ===== INLINED FROM AmirXProxy/repositories/proxy_repository.py =====
"""Smart-cache orchestration layer.

This is the single entry point handlers use to get ranked proxies. It
implements the strategy described in the project spec:

1. Look at fresh, cached, healthy candidates first.
2. If there are enough, rank + return them (no network calls at all).
3. If not, re-validate stale cached candidates.
4. If still not enough, collect from sources, validate the new pool.
5. Score + rank everything, update the cache, return the requested amount.

A single ``asyncio.Lock`` prevents two refreshes from running at once
(e.g. a user request overlapping with the background scheduler).
"""


import asyncio
from typing import Awaitable, Callable


ProgressCallback = Callable[[str], Awaitable[None]]

_refresh_lock = asyncio.Lock()


async def _notify(progress_cb: ProgressCallback | None, stage: str) -> None:
    if progress_cb is not None:
        try:
            await progress_cb(stage)
        except Exception as exc:  # noqa: BLE001 - a UI hiccup must not break the pipeline
            log.debug("progress callback failed: %s", exc)


async def _revalidate_and_store(candidates: list[Proxy]) -> list[Proxy]:
    validated = await validate_all(candidates, MAX_CONCURRENT_CHECKS)
    ranked = rank(validated)
    await proxy_cache.upsert_many(ranked)
    return ranked


async def refresh_pool(progress_cb: ProgressCallback | None = None,
                        target_pool_size: int | None = None) -> list[Proxy]:
    """Force a full collect -> validate -> score -> cache cycle.

    Overlap-safe: if a refresh is already running, this call waits for it
    and reuses its result instead of starting a second one.
    """
    target_pool_size = target_pool_size or TARGET_HEALTHY_POOL_SIZE

    async with _refresh_lock:
        await _notify(progress_cb, "collect")
        fresh_candidates = await collect_raw_candidates()

        await _notify(progress_cb, "dedupe")  # already deduped inside collect_raw_candidates
        stale = await proxy_cache.get_stale(limit=max(0, target_pool_size))
        pool = _merge_by_fingerprint(fresh_candidates, stale)

        await _notify(progress_cb, "validate")
        ranked = await _revalidate_and_store(pool)

        await _notify(progress_cb, "rank")
        return ranked


def _merge_by_fingerprint(*groups: list[Proxy]) -> list[Proxy]:
    merged: dict[str, Proxy] = {}
    for group in groups:
        for proxy in group:
            existing = merged.get(proxy.raw_hash)
            if existing is None:
                merged[proxy.raw_hash] = proxy
            else:
                existing.source |= proxy.source
    return list(merged.values())


async def get_results(requested: int, progress_cb: ProgressCallback | None = None) -> list[Proxy]:
    """Main entry point for the user-facing "give me N proxies" flow."""
    requested = min(requested, MAX_RESULTS_PER_REQUEST)

    await _notify(progress_cb, "cache_lookup")
    fresh_healthy = await proxy_cache.get_fresh_healthy(limit=None)
    if len(fresh_healthy) >= requested:
        await _notify(progress_cb, "rank")
        await _notify(progress_cb, "finalize")
        return fresh_healthy[:requested]

    # not enough fresh data -- run a real refresh cycle
    ranked = await refresh_pool(progress_cb)
    healthy = [p for p in ranked if p.is_alive and p.is_valid]
    healthy.sort(key=lambda p: p.score, reverse=True)

    await _notify(progress_cb, "finalize")
    return healthy[:requested]


async def force_refresh(progress_cb: ProgressCallback | None = None) -> list[Proxy]:
    """Used by the 🔄 refresh button and the admin panel."""
    return await refresh_pool(progress_cb)


# ===== INLINED FROM AmirXProxy/services/rate_limiter.py =====
"""Very small per-user cooldown to prevent button-mashing abuse."""


import time



class RateLimiter:
    def __init__(self, cooldown_seconds: int | None = None) -> None:
        self.cooldown_seconds = cooldown_seconds or USER_COOLDOWN_SECONDS
        self._last_action: dict[int, float] = {}

    def check(self, user_id: int) -> tuple[bool, float]:
        """Return (allowed, seconds_left). Does NOT record the action --
        call :meth:`record` once the action actually starts."""
        last = self._last_action.get(user_id)
        if last is None:
            return True, 0.0
        elapsed = time.time() - last
        remaining = self.cooldown_seconds - elapsed
        return remaining <= 0, max(0.0, remaining)

    def record(self, user_id: int) -> None:
        self._last_action[user_id] = time.time()


rate_limiter = RateLimiter()


# ===== INLINED FROM AmirXProxy/services/scheduler.py =====
"""Optional periodic background refresh.

Keeps the cache warm so most user requests can be answered instantly
from :func:`repositories.proxy_repository.get_results` without a live
scan. Guarded against overlapping runs by the lock already inside
``refresh_pool``.
"""


import asyncio


_task: asyncio.Task | None = None


async def _loop() -> None:
    interval = max(1, BACKGROUND_REFRESH_MINUTES) * 60
    while True:
        try:
            log.info("Background refresh starting")
            ranked = await refresh_pool()
            healthy = sum(1 for p in ranked if p.is_alive and p.is_valid)
            log.info("Background refresh finished: %d healthy / %d total", healthy, len(ranked))
        except Exception as exc:  # noqa: BLE001 - the loop must survive any single failure
            log.error("Background refresh crashed: %s", exc)
        await asyncio.sleep(interval)


def start_background_refresh() -> None:
    global _task
    if not ENABLE_BACKGROUND_REFRESH:
        log.info("Background refresh disabled in config")
        return
    if _task is not None and not _task.done():
        return
    _task = asyncio.ensure_future(_loop())
    log.info("Background refresh scheduled every %d minute(s)", BACKGROUND_REFRESH_MINUTES)


def stop_background_refresh() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        _task = None


# ===== INLINED FROM AmirXProxy/utils/formatting.py =====
"""Persian-facing text formatting helpers.

Keeping the wording centralised here makes it easy to tweak the bot's
tone without hunting through handler logic.
"""



WELCOME_TEXT = (
    "⚡ *AmirXProxy*\n\n"
    "پروکسی‌های عمومی را از منابع مشخص‌شده بررسی می‌کنم، "
    "موارد تکراری را حذف می‌کنم و گزینه‌های قابل‌استفاده را بر اساس "
    "وضعیت و کیفیت *فعلی* رتبه‌بندی می‌کنم.\n\n"
    "چند پروکسی می‌خوای؟"
)

HELP_TEXT = (
    "🆘 *راهنمای AmirXProxy*\n\n"
    "*این ربات چیکار می‌کنه؟*\n"
    "از یک فهرست منابع عمومیِ از پیش تعریف‌شده (فایل‌های GitHub و صفحات وب "
    "عمومی) پروکسی جمع‌آوری می‌کنه، رکوردهای تکراری رو حذف می‌کنه و "
    "سالم‌بودنشون رو همین الان تست می‌کنه.\n\n"
    "*یعنی چی وقتی می‌گم یه پروکسی 🟢 عالیه؟*\n"
    "یعنی در آخرین بررسی، اتصال به سرور برقرار شده، تاخیر (لتنسی) پایینی "
    "داشته و به‌تازگی هم دیده شده. کیفیت هیچ‌وقت فقط بر اساس سرعت تعیین "
    "نمی‌شه؛ سلامت اتصال همیشه اولویت اول هست.\n\n"
    "*چرا نتایج تغییر می‌کنن؟*\n"
    "پروکسی‌های عمومی و رایگان معمولاً پایدار نیستن؛ ممکنه صاحبشون "
    "خاموششون کنه یا بار زیادی روشون باشه. به همین دلیل هر بار وضعیتشون "
    "دوباره چک می‌شه.\n\n"
    "*چرا گاهی تعداد نتایج کمتر از درخواستمه؟*\n"
    "اگه تعداد کافی پروکسیِ *واقعاً سالم* در دسترس نباشه، ربات به جای پر "
    "کردن لیست با گزینه‌های ناسالم، فقط همونایی که واقعاً کار می‌کنن رو "
    "نشون می‌ده.\n\n"
    "*چرا کشف‌شدن یه پروکسی به معنی سالم‌بودنش نیست؟*\n"
    "خیلی از فهرست‌های عمومی، آدرس‌ها رو بدون تست واقعی منتشر می‌کنن. "
    "AmirXProxy هر رکورد رو جدا از بقیه، با یک بررسی شبکه‌ای واقعی، از نو "
    "اعتبارسنجی می‌کنه.\n\n"
    "دستورها:\n"
    "/start شروع و انتخاب تعداد پروکسی\n"
    "/status وضعیت کلی سرویس\n"
    "/help همین راهنما"
)

SOURCES_INFO_TEMPLATE = (
    "📡 *منابع بررسی‌شده*\n\n"
    "این‌ها منابع عمومی *فعال* تنظیم‌شده برای این ربات هستن. ربات فقط "
    "همین منابع مشخص را می‌خواند؛ ادعایی درباره‌ی بررسیِ «تمام کانال‌های "
    "تلگرام» وجود ندارد چون از نظر فنی با Bot API ممکن نیست.\n\n"
    "{rows}"
)


def scanning_stage_text(stage_index: int, total: int, label: str) -> str:
    dots = "▓" * (stage_index + 1) + "░" * (total - stage_index - 1)
    return f"🛰️ *در حال آماده‌سازی نتایج...*\n\n{label}\n`{dots}`"


def quality_summary_line(proxy: Proxy) -> str:
    latency = f"{int(proxy.latency_ms)} ms" if proxy.latency_ms is not None else "نامشخص"
    return (
        f"{proxy.quality.label_fa}\n"
        f"⚡ {latency}\n"
        f"{proxy.scheme_label()}\n"
        f"🕒 بررسی: {humanize_ago(proxy.last_checked)}\n"
        f"📍 منبع: {next(iter(proxy.source), 'نامشخص')}"
    )


def format_result_item(rank: int, proxy: Proxy) -> str:
    medal = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}.get(rank, f"{rank}.")
    return f"{medal} {quality_summary_line(proxy)}"


def format_results_header(requested: int, returned: int) -> str:
    header = "🏆 *AmirXProxy*\n\nبهترین نتایج بررسی‌شده:\n"
    if returned < requested:
        header += (
            f"\n_توجه: در حال حاضر فقط {returned} پروکسیِ واقعاً سالم پیدا شد "
            f"(از {requested} درخواستی). به‌جای پرکردن لیست با گزینه‌های "
            f"ناسالم، فقط نتایج معتبر نمایش داده می‌شن._\n"
        )
    return header


def format_empty_results() -> str:
    return (
        "😕 در حال حاضر هیچ پروکسیِ سالمی در منابع فعال پیدا نشد.\n\n"
        "این به معنی خرابی ربات نیست؛ منابع عمومی رایگان می‌تونن موقتاً "
        "بدون گزینه‌ی سالم باشن. چند دقیقه دیگه دوباره امتحان کن."
    )


def format_no_dependency_warning(scheme: str) -> str:
    return f"⚠️ بررسی پروتکلی برای {scheme} به‌طور کامل در دسترس نیست؛ فقط بررسی TCP انجام شد."


# ===== INLINED FROM AmirXProxy/keyboards/main.py =====
"""Inline keyboards shown to normal users."""


from telebot import types


_QUANTITY_EMOJI = {2: "2️⃣", 4: "4️⃣", 6: "6️⃣"}


def quantity_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    for qty in RESULT_QUANTITY_OPTIONS:
        emoji = _QUANTITY_EMOJI.get(qty, "🔹")
        markup.add(types.InlineKeyboardButton(f"{emoji} {qty} پروکسی", callback_data=f"qty:{qty}"))
    markup.add(types.InlineKeyboardButton("📡 منابع بررسی‌شده", callback_data="sources"))
    return markup


def results_keyboard(proxies: list[Proxy], requested: int) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    for index, proxy in enumerate(proxies, start=1):
        markup.add(
            types.InlineKeyboardButton(f"🔗 اتصال به گزینه {index}", url=proxy.connect_link())
        )
    markup.add(
        types.InlineKeyboardButton("🔄 بررسی دوباره", callback_data=f"refresh:{requested}"),
        types.InlineKeyboardButton("🔍 جست‌وجوی جدید", callback_data="new_search"),
    )
    return markup


def back_to_menu_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔍 جست‌وجوی جدید", callback_data="new_search"))
    return markup


# ===== INLINED FROM AmirXProxy/keyboards/admin.py =====
"""Inline keyboards for the admin panel (/admin, only ADMIN_IDS)."""


from telebot import types


def admin_menu_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 آمار", callback_data="admin:stats"),
        types.InlineKeyboardButton("🔄 بروزرسانی اجباری", callback_data="admin:force_refresh"),
    )
    markup.add(
        types.InlineKeyboardButton("📡 سلامت منابع", callback_data="admin:source_health"),
        types.InlineKeyboardButton("🧪 تست اعتبارسنجی", callback_data="admin:validation_test"),
    )
    markup.add(
        types.InlineKeyboardButton("🧹 پاک‌سازی کش", callback_data="admin:clear_cache"),
        types.InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin:settings"),
    )
    return markup


def admin_back_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ بازگشت به پنل ادمین", callback_data="admin:menu"))
    return markup


# ===== INLINED FROM AmirXProxy/handlers/start.py =====
"""``/start`` command and the initial "which quantity" screen."""


from telebot import types
from telebot.async_telebot import AsyncTeleBot



async def _send_welcome(bot: AsyncTeleBot, chat_id: int) -> None:
    await bot.send_message(chat_id, WELCOME_TEXT, reply_markup=quantity_keyboard())


def _sources_overview_text() -> str:
    rows = []
    for source in get_all_sources():
        state = "✅ فعال" if source.enabled else "⛔️ غیرفعال"
        rows.append(f"• *{source.name}*  —  {state}  ({source.type})")
    body = "\n".join(rows) if rows else "منبعی تنظیم نشده است."
    return SOURCES_INFO_TEMPLATE.format(rows=body)


def register(bot: AsyncTeleBot) -> None:
    @bot.message_handler(commands=["start"])
    async def handle_start(message: types.Message) -> None:
        await _send_welcome(bot, message.chat.id)

    @bot.callback_query_handler(func=lambda call: call.data == "new_search")
    async def handle_new_search(call: types.CallbackQuery) -> None:
        await bot.answer_callback_query(call.id)
        try:
            await bot.edit_message_text(
                WELCOME_TEXT,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=quantity_keyboard(),
            )
        except Exception:  # noqa: BLE001 - message may be unchanged/too old to edit
            await _send_welcome(bot, call.message.chat.id)

    @bot.callback_query_handler(func=lambda call: call.data == "sources")
    async def handle_sources(call: types.CallbackQuery) -> None:
        await bot.answer_callback_query(call.id)
        await bot.send_message(call.message.chat.id, _sources_overview_text())


# ===== INLINED FROM AmirXProxy/handlers/user.py =====
"""Core user flow: pick a quantity -> scan -> show ranked results."""


from telebot import types
from telebot.async_telebot import AsyncTeleBot


_STAGE_ORDER = ["cache_lookup", "collect", "dedupe", "validate", "rank", "finalize"]
_STAGE_LABEL = {
    "cache_lookup": "🔎 در حال بررسی منابع...",
    "collect": "🔎 در حال جمع‌آوری از منابع فعال...",
    "dedupe": "🧹 در حال حذف موارد تکراری...",
    "validate": "🧪 در حال بررسی وضعیت هر پروکسی...",
    "rank": "⚡ در حال رتبه‌بندی...",
    "finalize": "🏆 در حال آماده‌سازی نتیجه...",
}


def _render_results_text(proxies: list[Proxy], requested: int) -> str:
    if not proxies:
        return format_empty_results()
    header = format_results_header(requested, len(proxies))
    body = "\n\n".join(format_result_item(i, p) for i, p in enumerate(proxies, start=1))
    return f"{header}\n{body}"


async def _run_scan_with_progress(bot: AsyncTeleBot, chat_id: int, message_id: int,
                                   requested: int, refresh_only: bool = False) -> list[Proxy]:
    async def progress_cb(stage: str) -> None:
        try:
            index = _STAGE_ORDER.index(stage)
        except ValueError:
            return
        label = _STAGE_LABEL.get(stage, stage)
        text = scanning_stage_text(index, len(_STAGE_ORDER), label)
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)
        except Exception:  # noqa: BLE001 - "message not modified" or similar, safe to ignore
            pass

    if refresh_only:
        ranked = await force_refresh(progress_cb)
        healthy = [p for p in ranked if p.is_alive and p.is_valid]
        healthy.sort(key=lambda p: p.score, reverse=True)
        return healthy[:requested]

    return await get_results(requested, progress_cb)


def register(bot: AsyncTeleBot) -> None:
    @bot.message_handler(commands=["help"])
    async def handle_help(message: types.Message) -> None:
        await bot.send_message(message.chat.id, HELP_TEXT)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("qty:"))
    async def handle_quantity(call: types.CallbackQuery) -> None:
        user_id = call.from_user.id
        allowed, remaining = rate_limiter.check(user_id)
        if not allowed:
            await bot.answer_callback_query(
                call.id, text=f"⏳ لطفاً {int(remaining) + 1} ثانیه صبر کن و دوباره امتحان کن.",
                show_alert=True,
            )
            return

        try:
            requested = min(int(call.data.split(":", 1)[1]), MAX_RESULTS_PER_REQUEST)
        except (IndexError, ValueError):
            requested = RESULT_QUANTITY_OPTIONS[0]

        rate_limiter.record(user_id)
        await bot.answer_callback_query(call.id)

        chat_id = call.message.chat.id
        message_id = call.message.message_id
        await bot.edit_message_text(
            scanning_stage_text(0, len(_STAGE_ORDER), _STAGE_LABEL["cache_lookup"]),
            chat_id=chat_id, message_id=message_id,
        )

        try:
            results = await _run_scan_with_progress(bot, chat_id, message_id, requested)
        except Exception as exc:  # noqa: BLE001 - never let a scan failure kill the bot
            log.error("Scan failed for user %s: %s", user_id, exc)
            await bot.edit_message_text(
                "⚠️ در حین بررسی خطایی رخ داد. لطفاً چند لحظه دیگر دوباره امتحان کن.",
                chat_id=chat_id, message_id=message_id, reply_markup=back_to_menu_keyboard(),
            )
            return

        text = _render_results_text(results, requested)
        markup = results_keyboard(results, requested) if results else back_to_menu_keyboard()
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("refresh:"))
    async def handle_refresh(call: types.CallbackQuery) -> None:
        user_id = call.from_user.id
        allowed, remaining = rate_limiter.check(user_id)
        if not allowed:
            await bot.answer_callback_query(
                call.id, text=f"⏳ لطفاً {int(remaining) + 1} ثانیه صبر کن و دوباره امتحان کن.",
                show_alert=True,
            )
            return

        try:
            requested = min(int(call.data.split(":", 1)[1]), MAX_RESULTS_PER_REQUEST)
        except (IndexError, ValueError):
            requested = RESULT_QUANTITY_OPTIONS[0]

        rate_limiter.record(user_id)
        await bot.answer_callback_query(call.id, text="🔄 در حال بررسی دوباره...")

        chat_id = call.message.chat.id
        message_id = call.message.message_id
        await bot.edit_message_text(
            scanning_stage_text(1, len(_STAGE_ORDER), _STAGE_LABEL["collect"]),
            chat_id=chat_id, message_id=message_id,
        )

        try:
            results = await _run_scan_with_progress(bot, chat_id, message_id, requested, refresh_only=True)
        except Exception as exc:  # noqa: BLE001
            log.error("Refresh failed for user %s: %s", user_id, exc)
            await bot.edit_message_text(
                "⚠️ بروزرسانی با خطا مواجه شد. کمی بعد دوباره تلاش کن.",
                chat_id=chat_id, message_id=message_id, reply_markup=back_to_menu_keyboard(),
            )
            return

        text = _render_results_text(results, requested)
        markup = results_keyboard(results, requested) if results else back_to_menu_keyboard()
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup)

    # Fallback: if a user types 2 / 4 / 6 as plain text instead of tapping a button.
    @bot.message_handler(func=lambda message: message.text and message.text.strip() in {"2", "4", "6"})
    async def handle_plain_quantity(message: types.Message) -> None:
        await bot.send_message(
            message.chat.id,
            "برای دقت بیشتر، لطفاً از دکمه‌های زیر استفاده کن 👇",
            reply_markup=quantity_keyboard(),
        )


# ===== INLINED FROM AmirXProxy/handlers/status.py =====
"""``/status`` command: a public, non-sensitive service health summary."""


from telebot import types
from telebot.async_telebot import AsyncTeleBot



async def _status_text() -> str:
    stats = await proxy_cache.stats()
    active_sources = len(get_enabled_sources())
    last_refresh = clock_hhmm(stats["last_refresh"])

    return (
        "⚡ *AmirXProxy Status*\n\n"
        "🟢 Service: Online\n"
        f"📡 Active Sources: {active_sources}\n"
        f"🧪 Healthy Cached Results: {stats['healthy']}\n"
        f"🕒 Last Refresh: {last_refresh}\n\n"
        "_نتایج فقط از منابع عمومیِ فعال‌شده جمع‌آوری و همین الان اعتبارسنجی می‌شوند._"
    )


def register(bot: AsyncTeleBot) -> None:
    @bot.message_handler(commands=["status"])
    async def handle_status(message: types.Message) -> None:
        await bot.send_message(message.chat.id, await _status_text())


# ===== INLINED FROM AmirXProxy/handlers/admin.py =====
"""``/admin`` panel. Restricted to Telegram user ids listed in
``ADMIN_IDS`` (see the "ADMIN ID RO INJA BEZAR" section of
py)."""


from telebot import types
from telebot.async_telebot import AsyncTeleBot


ADMIN_MENU_TEXT = "🛠️ *پنل مدیریت AmirXProxy*\n\nیکی از گزینه‌ها رو انتخاب کن:"


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def _stats_text() -> str:
    stats = await proxy_cache.stats()
    sources = get_all_sources()
    active = sum(1 for s in sources if s.enabled)
    failed = sum(1 for s in sources if s.stats.consecutive_failures > 0)
    avg_latency = f"{stats['average_latency_ms']} ms" if stats["average_latency_ms"] else "نامشخص"

    return (
        "📊 *AmirXProxy Statistics*\n\n"
        f"Collected (cache size): {stats['total']}\n"
        f"Healthy: {stats['healthy']}\n"
        f"Unavailable: {stats['unavailable']}\n"
        f"Validated so far: {stats['validated']}\n"
        f"Active sources: {active}/{len(sources)}\n"
        f"Sources with recent failures: {failed}\n"
        f"Average latency: {avg_latency}\n"
        f"Last refresh: {clock_hhmm(stats['last_refresh'])}"
    )


async def _source_health_text() -> str:
    lines = ["📡 *سلامت منابع*\n"]
    for source in get_all_sources():
        s = source.stats
        lines.append(
            f"{s.health.value} *{source.name}*\n"
            f"   نوع: {source.type} | فعال: {'بله' if source.enabled else 'خیر'}\n"
            f"   آخرین موفقیت: {humanize_ago(s.last_success)}\n"
            f"   شکست‌های متوالی: {s.consecutive_failures}\n"
            f"   آخرین تعداد یافته: {s.last_candidate_count}\n"
            f"   خطای اخیر: {s.last_error or '—'}"
        )
    return "\n\n".join(lines)


async def _validation_test_text() -> str:
    sample = (await proxy_cache.get_all())[:5]
    if not sample:
        return "کش هنوز خالیه. اول یک «بروزرسانی اجباری» انجام بده."

    fresh = await validate_all(sample)
    lines = ["🧪 *تست اعتبارسنجی (۵ نمونه از کش)*\n"]
    for proxy in fresh:
        lines.append(
            f"• {proxy.server}:{proxy.port} [{proxy.scheme.value}] "
            f"secret={redact_secret(proxy.secret)}\n"
            f"   وضعیت: {proxy.state.value} | زنده: {proxy.is_alive} | معتبر: {proxy.is_valid}\n"
            f"   لتنسی: {proxy.latency_ms and round(proxy.latency_ms, 1)} ms\n"
            f"   خطا: {proxy.verification_error or '—'}"
        )
    return "\n".join(lines)


async def _settings_text() -> str:
    return (
        "⚙️ *تنظیمات فعلی*\n\n"
        f"CACHE_TTL_MINUTES: {CACHE_TTL_MINUTES}\n"
        f"USER_COOLDOWN_SECONDS: {USER_COOLDOWN_SECONDS}\n"
        f"CONNECT_TIMEOUT: {CONNECT_TIMEOUT}s\n"
        f"READ_TIMEOUT: {READ_TIMEOUT}s\n"
        f"MAX_CONCURRENT_CHECKS: {MAX_CONCURRENT_CHECKS}\n"
        f"MAX_RESULTS_PER_REQUEST: {MAX_RESULTS_PER_REQUEST}\n"
        f"TARGET_HEALTHY_POOL_SIZE: {TARGET_HEALTHY_POOL_SIZE}\n"
        f"BACKGROUND_REFRESH_MINUTES: {BACKGROUND_REFRESH_MINUTES}\n"
        f"ENABLE_BACKGROUND_REFRESH: {ENABLE_BACKGROUND_REFRESH}\n"
        f"Admins configured: {len(ADMIN_IDS)}\n\n"
        "_برای تغییر این مقادیر، فایل py رو ویرایش کن._"
    )


def register(bot: AsyncTeleBot) -> None:
    @bot.message_handler(commands=["admin"])
    async def handle_admin(message: types.Message) -> None:
        if not _is_admin(message.from_user.id):
            await bot.send_message(message.chat.id, "⛔️ این دستور فقط برای مدیران در دسترس است.")
            return
        await bot.send_message(message.chat.id, ADMIN_MENU_TEXT, reply_markup=admin_menu_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin:"))
    async def handle_admin_callback(call: types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            await bot.answer_callback_query(call.id, text="⛔️ دسترسی غیرمجاز.", show_alert=True)
            return

        action = call.data.split(":", 1)[1]
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        if action == "menu":
            await bot.answer_callback_query(call.id)
            await bot.edit_message_text(ADMIN_MENU_TEXT, chat_id=chat_id, message_id=message_id,
                                         reply_markup=admin_menu_keyboard())
            return

        if action == "stats":
            await bot.answer_callback_query(call.id)
            await bot.edit_message_text(await _stats_text(), chat_id=chat_id, message_id=message_id,
                                         reply_markup=admin_back_keyboard())
            return

        if action == "source_health":
            await bot.answer_callback_query(call.id)
            await bot.edit_message_text(await _source_health_text(), chat_id=chat_id, message_id=message_id,
                                         reply_markup=admin_back_keyboard())
            return

        if action == "validation_test":
            await bot.answer_callback_query(call.id, text="در حال تست...")
            await bot.edit_message_text(await _validation_test_text(), chat_id=chat_id, message_id=message_id,
                                         reply_markup=admin_back_keyboard())
            return

        if action == "clear_cache":
            await proxy_cache.clear()
            await bot.answer_callback_query(call.id, text="🧹 کش پاک شد.")
            await bot.edit_message_text("🧹 کش با موفقیت پاک شد.", chat_id=chat_id, message_id=message_id,
                                         reply_markup=admin_back_keyboard())
            return

        if action == "settings":
            await bot.answer_callback_query(call.id)
            await bot.edit_message_text(await _settings_text(), chat_id=chat_id, message_id=message_id,
                                         reply_markup=admin_back_keyboard())
            return

        if action == "force_refresh":
            await bot.answer_callback_query(call.id, text="🔄 شروع بروزرسانی...")

            async def progress_cb(stage: str) -> None:
                try:
                    await bot.edit_message_text(f"🔄 در حال بروزرسانی... ({stage})",
                                                 chat_id=chat_id, message_id=message_id)
                except Exception:  # noqa: BLE001
                    pass

            try:
                ranked = await force_refresh(progress_cb)
                healthy = sum(1 for p in ranked if p.is_alive and p.is_valid)
                text = f"✅ بروزرسانی کامل شد.\n\nمجموع: {len(ranked)} | سالم: {healthy}"
            except Exception as exc:  # noqa: BLE001
                log.error("Admin force refresh failed: %s", exc)
                text = f"⚠️ بروزرسانی با خطا مواجه شد: {exc}"

            await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                         reply_markup=admin_back_keyboard())
            return

        await bot.answer_callback_query(call.id)


# ===== INLINED FROM AmirXProxy/bot.py =====
"""AmirXProxy entry point.

Run with:

    python bot.py

Before running, open py and paste your BotFather token where it
says "TOKEN RO INJA BEZAR".
"""


import asyncio

from telebot.async_telebot import AsyncTeleBot



def build_bot() -> AsyncTeleBot:
    if not BOT_TOKEN or BOT_TOKEN.strip() == "TOKEN RO INJA BEZAR":
        raise RuntimeError(
            "توکن ربات تنظیم نشده است.\n"
            "فایل py را باز کن، خط:\n"
            '    BOT_TOKEN = "TOKEN RO INJA BEZAR"\n'
            "را پیدا کن و متن TOKEN RO INJA BEZAR را با توکن واقعی BotFather جایگزین کن."
        )

    bot = AsyncTeleBot(BOT_TOKEN, parse_mode="Markdown")

    start_handler.register(bot)
    user_handler.register(bot)
    status_handler.register(bot)
    admin_handler.register(bot)

    return bot


async def main() -> None:
    bot = build_bot()
    log.info("⚡ AmirXProxy در حال راه‌اندازی است...")
    log.info("Admins configured: %d", len(ADMIN_IDS))

    start_background_refresh()

    try:
        await bot.infinity_polling(skip_pending=True, timeout=20)
    finally:
        log.info("AmirXProxy در حال خاموش شدن...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as exc:
        # Friendly message for the most common beginner mistake: forgetting
        # to paste the token. Never prints the token itself.
        print(f"\n❌ {exc}\n")
    except KeyboardInterrupt:
        pass
