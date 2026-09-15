from __future__ import annotations

import ast
import re
from pathlib import Path

SOURCE = Path("AmirXProxy_single.py")
OUTPUT = Path("/tmp/AmirXProxy_single_fixed.py")

WATCHDOG = r'''

# Runtime hardening: never let a Telegram scan callback remain pending
# forever. This only controls cancellation/error handling; it does not
# change the proxy discovery or validation logic itself.
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
                            "یکی از عملیات‌های شبکه پاسخ نداد. دوباره تلاش کن.",
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

# Runtime hardening: isolate source fetches so one stuck source cannot hold
# the whole collection stage indefinitely. Completed sources are kept; pending
# ones are cancelled and treated as unavailable for this scan.
async def _bounded_collect_raw_candidates(sources=None, per_source_timeout: float = 12.0):
    active_sources = sources if sources is not None else get_enabled_sources()
    if not active_sources:
        log.warning("No enabled proxy sources are configured")
        return []

    log.info("Hardened source scan started across %d source(s)", len(active_sources))
    tasks = {
        asyncio.create_task(source.collect()): source
        for source in active_sources
    }
    done, pending = await asyncio.wait(
        tasks,
        timeout=max(1.0, per_source_timeout),
    )

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

    log.info(
        "Hardened source scan finished: %d completed source(s), %d cancelled, %d raw candidate(s)",
        len(done), len(pending), len(raw_candidates),
    )
    return deduplicate(raw_candidates)
'''


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    marker = "def register(bot: AsyncTeleBot) -> None:"
    count = source.count(marker)
    if count != 4:
        raise RuntimeError(f"Expected 4 handler register() definitions, found {count}")

    names = ["register_start", "register_user", "register_status", "register_admin"]
    fixed = source
    for name in names:
        fixed = fixed.replace(marker, f"def {name}(bot: AsyncTeleBot) -> None:", 1)

    old = '''    start_handler.register(bot)\n    user_handler.register(bot)\n    status_handler.register(bot)\n    admin_handler.register(bot)'''
    new = '''    register_start(bot)\n    register_user(bot)\n    register_status(bot)\n    register_admin(bot)'''

    if old not in fixed:
        raise RuntimeError("build_bot() registration block was not found")
    fixed = fixed.replace(old, new, 1)

    if "_with_scan_timeout" not in fixed:
        fixed = fixed.replace(
            "\n\n# ===== INLINED FROM AmirXProxy/",
            WATCHDOG + "\n\n# ===== INLINED FROM AmirXProxy/",
            1,
        )

    # Replace the collection fan-out with a bounded version. This keeps the
    # normal source/parser logic intact while preventing one network operation
    # from holding the user-facing scan at the first progress stage forever.
    if "_bounded_collect_raw_candidates" not in fixed:
        anchor = "\n\n# ===== INLINED FROM AmirXProxy/repositories/proxy_repository.py ====="
        if anchor not in fixed:
            raise RuntimeError("Collector insertion anchor was not found")
        fixed = fixed.replace(anchor, SOURCE_SCAN_HARDENING + anchor, 1)

        collect_pattern = re.compile(
            r"async def collect_raw_candidates\(sources: list\[Proxy\] \| None = None\) -> list\[Proxy\]:.*?\n\n# ===== INLINED FROM AmirXProxy/repositories/proxy_repository.py =====",
            flags=re.DOTALL,
        )
        replacement = (
            "async def collect_raw_candidates(sources: list[Proxy] | None = None) -> list[Proxy]:\n"
            "    \"\"\"Collect candidates with a hard per-scan source timeout.\"\"\"\n"
            "    return await _bounded_collect_raw_candidates(sources)\n\n"
            "# ===== INLINED FROM AmirXProxy/repositories/proxy_repository.py ====="
        )
        fixed, replaced = collect_pattern.subn(replacement, fixed, count=1)
        if replaced != 1:
            raise RuntimeError(f"Collector function replacement failed: {replaced}")

    # Prevent very large candidate sets from turning validation into an
    # effectively unbounded wait. Keep a bounded work set while preserving
    # the requested result size and the existing ranking/validation pipeline.
    cap_marker = "async def _revalidate_and_store(candidates: list[Proxy]) -> list[Proxy]:\n    validated = await validate_all(candidates, MAX_CONCURRENT_CHECKS)"
    cap_replacement = (
        "async def _revalidate_and_store(candidates: list[Proxy]) -> list[Proxy]:\n"
        "    validation_cap = max(TARGET_HEALTHY_POOL_SIZE * 4, MAX_RESULTS_PER_REQUEST * 8)\n"
        "    candidates = candidates[:validation_cap]\n"
        "    validated = await validate_all(candidates, MAX_CONCURRENT_CHECKS)"
    )
    if cap_marker in fixed and "validation_cap = max(TARGET_HEALTHY_POOL_SIZE * 4" not in fixed:
        fixed = fixed.replace(cap_marker, cap_replacement, 1)

    # The real user-facing scan handlers are handle_quantity() and
    # handle_refresh(). Guard both, rather than looking for a nonexistent
    # new_search() function.
    for function_name in ("handle_quantity", "handle_refresh"):
        search_match = re.search(
            rf"^(\s*)async def {function_name}\(", fixed, flags=re.MULTILINE
        )
        if search_match:
            indent = search_match.group(1)
            decorator = f"{indent}@_with_scan_timeout(bot)\n"
            line_start = search_match.start()
            if fixed[line_start - len(decorator):line_start] != decorator:
                fixed = fixed[:line_start] + decorator + fixed[line_start:]
            print(f"Scan watchdog installed for {function_name}().")
        else:
            raise RuntimeError(f"Required scan handler {function_name}() was not found")

    # Do not let the background scheduler grab _refresh_lock immediately at
    # startup. Give normal Telegram commands first access; the scheduler then
    # performs its regular periodic refresh.
    old_loop = '''async def _loop() -> None:\n    interval = max(1, BACKGROUND_REFRESH_MINUTES) * 60\n    while True:'''
    new_loop = '''async def _loop() -> None:\n    interval = max(1, BACKGROUND_REFRESH_MINUTES) * 60\n    await asyncio.sleep(interval)\n    while True:'''
    if old_loop in fixed:
        fixed = fixed.replace(old_loop, new_loop, 1)
        print("Background refresh startup delay installed.")
    else:
        raise RuntimeError("Background scheduler loop pattern was not found")

    tree = ast.parse(fixed, filename=str(OUTPUT))
    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    required = set(names) | {"build_bot", "main", "handle_quantity", "handle_refresh", "collect_raw_candidates", "_bounded_collect_raw_candidates"}
    missing = sorted(required - function_names)
    if missing:
        raise RuntimeError(f"Runtime patch validation failed; missing: {missing}")

    OUTPUT.write_text(fixed, encoding="utf-8")
    print(f"Prepared fixed runtime: {OUTPUT}")
    print("Registered handler groups: " + ", ".join(names))


if __name__ == "__main__":
    main()
