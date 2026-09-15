from __future__ import annotations

import ast
import re
from pathlib import Path

SOURCE = Path("AmirXProxy_single.py")
OUTPUT = Path("/tmp/AmirXProxy_single_fixed.py")

WATCHDOG = r'''

def _with_scan_timeout(bot, seconds: float = 45.0):
    import asyncio
    from functools import wraps
    def decorator(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                log.error("Scan handler timed out after %.1fs", seconds)
                try:
                    call = args[0] if args else None
                    message = getattr(call, "message", None)
                    chat = getattr(message, "chat", None)
                    message_id = getattr(message, "message_id", None)
                    chat_id = getattr(chat, "id", None)
                    if chat_id is not None and message_id is not None:
                        await bot.edit_message_text(
                            "⏱️ بررسی بیش از حد طول کشید و متوقف شد.\n\n"
                            "مرحلهٔ بررسی تعداد زیادی کاندید طولانی شد. دوباره تلاش کن.",
                            chat_id=chat_id,
                            message_id=message_id,
                        )
                except Exception as exc:
                    log.warning("Could not update timed-out scan message: %s", exc)
                return None
        return wrapped
    return decorator
'''

SOURCE_SCAN_HARDENING = r'''

async def _bounded_collect_raw_candidates(sources=None, per_source_timeout: float = 12.0):
    active_sources = sources if sources is not None else get_enabled_sources()
    if not active_sources:
        log.warning("No enabled proxy sources are configured")
        return []
    tasks = {asyncio.create_task(source.collect()): source for source in active_sources}
    done, pending = await asyncio.wait(tasks, timeout=max(1.0, per_source_timeout))
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    raw_candidates = []
    for task in done:
        source = tasks[task]
        try:
            result = task.result()
        except Exception as exc:
            log.warning("Source '%s' failed during bounded scan: %s", source.name, exc)
            continue
        if isinstance(result, list):
            raw_candidates.extend(result)
    log.info("Bounded source scan: %d completed, %d cancelled, %d raw", len(done), len(pending), len(raw_candidates))
    return deduplicate(raw_candidates)
'''

VALIDATION_CAP_PATCH = r'''

VALIDATION_CANDIDATE_CAP = 96


def _cap_validation_candidates(candidates: list[Proxy]) -> list[Proxy]:
    if len(candidates) <= VALIDATION_CANDIDATE_CAP:
        return candidates
    ordered = sorted(
        candidates,
        key=lambda p: (
            int(getattr(p, "is_valid", False)),
            int(getattr(p, "is_alive", False)),
            int(getattr(p, "source_count", 1)),
            float(getattr(p, "score", 0.0)),
            float(getattr(p, "last_seen", 0.0)),
        ),
        reverse=True,
    )
    selected = ordered[:VALIDATION_CANDIDATE_CAP]
    log.info(
        "Validation cap applied: %d -> %d candidate(s)",
        len(candidates),
        len(selected),
    )
    return selected
'''


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    marker = "def register(bot: AsyncTeleBot) -> None:"
    if source.count(marker) != 4:
        raise RuntimeError("Expected 4 handler register() definitions")

    names = ["register_start", "register_user", "register_status", "register_admin"]
    fixed = source
    for name in names:
        fixed = fixed.replace(marker, f"def {name}(bot: AsyncTeleBot) -> None:", 1)

    old = """    start_handler.register(bot)\n    user_handler.register(bot)\n    status_handler.register(bot)\n    admin_handler.register(bot)"""
    new = """    register_start(bot)\n    register_user(bot)\n    register_status(bot)\n    register_admin(bot)"""
    if old not in fixed:
        raise RuntimeError("build_bot() registration block was not found")
    fixed = fixed.replace(old, new, 1)

    if "_with_scan_timeout" not in fixed:
        anchor = "\n\n# ===== INLINED FROM AmirXProxy/"
        if anchor not in fixed:
            raise RuntimeError("Watchdog insertion anchor not found")
        fixed = fixed.replace(anchor, WATCHDOG + anchor, 1)

    collector_marker = "\n\n# ===== INLINED FROM AmirXProxy/repositories/proxy_repository.py ====="
    if "_bounded_collect_raw_candidates" not in fixed:
        if collector_marker not in fixed:
            raise RuntimeError("Collector anchor not found")
        start = fixed.index("async def collect_raw_candidates(")
        end = fixed.index(collector_marker, start)
        replacement = (
            "async def collect_raw_candidates(sources: list[Proxy] | None = None) -> list[Proxy]:\n"
            "    return await _bounded_collect_raw_candidates(sources)\n"
        )
        fixed = fixed[:start] + replacement + fixed[end:]
        fixed = fixed.replace(collector_marker, SOURCE_SCAN_HARDENING + collector_marker, 1)

    if "VALIDATION_CANDIDATE_CAP = 96" not in fixed:
        validation_marker = "\n\nasync def _revalidate_and_store(candidates: list[Proxy]) -> list[Proxy]:"
        if validation_marker not in fixed:
            raise RuntimeError("Validation hook anchor not found")
        fixed = fixed.replace(
            validation_marker,
            VALIDATION_CAP_PATCH + validation_marker,
            1,
        )

    old_revalidate = """async def _revalidate_and_store(candidates: list[Proxy]) -> list[Proxy]:\n    validated = await validate_all(candidates, MAX_CONCURRENT_CHECKS)\n    ranked = rank(validated)"""
    new_revalidate = """async def _revalidate_and_store(candidates: list[Proxy]) -> list[Proxy]:\n    candidates = _cap_validation_candidates(candidates)\n    validated = await validate_all(candidates, MAX_CONCURRENT_CHECKS)\n    ranked = rank(validated)"""
    if old_revalidate not in fixed:
        raise RuntimeError("Validation function body pattern was not found")
    fixed = fixed.replace(old_revalidate, new_revalidate, 1)

    for function_name in ("handle_quantity", "handle_refresh"):
        match = re.search(rf"^(\s*)async def {function_name}\(", fixed, flags=re.MULTILINE)
        if not match:
            raise RuntimeError(f"Required scan handler {function_name}() was not found")
        indent = match.group(1)
        decorator = f"{indent}@_with_scan_timeout(bot)\n"
        pos = match.start()
        if fixed[max(0, pos - len(decorator)):pos] != decorator:
            fixed = fixed[:pos] + decorator + fixed[pos:]

    old_loop = """async def _loop() -> None:\n    interval = max(1, BACKGROUND_REFRESH_MINUTES) * 60\n    while True:"""
    new_loop = """async def _loop() -> None:\n    interval = max(1, BACKGROUND_REFRESH_MINUTES) * 60\n    await asyncio.sleep(interval)\n    while True:"""
    if old_loop not in fixed:
        raise RuntimeError("Background scheduler loop pattern was not found")
    fixed = fixed.replace(old_loop, new_loop, 1)

    tree = ast.parse(fixed, filename=str(OUTPUT))
    function_names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    required = set(names) | {"build_bot", "main", "collect_raw_candidates", "_bounded_collect_raw_candidates", "_cap_validation_candidates", "handle_quantity", "handle_refresh"}
    missing = sorted(required - function_names)
    if missing:
        raise RuntimeError(f"Runtime patch validation failed; missing: {missing}")

    OUTPUT.write_text(fixed, encoding="utf-8")
    print(f"Prepared fixed runtime: {OUTPUT}")
    print("Registered handler groups: " + ", ".join(names))
    print(f"Validation candidate cap: {96}")


if __name__ == "__main__":
    main()
