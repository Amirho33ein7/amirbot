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
    required = set(names) | {"build_bot", "main", "handle_quantity", "handle_refresh"}
    missing = sorted(required - function_names)
    if missing:
        raise RuntimeError(f"Runtime patch validation failed; missing: {missing}")

    OUTPUT.write_text(fixed, encoding="utf-8")
    print(f"Prepared fixed runtime: {OUTPUT}")
    print("Registered handler groups: " + ", ".join(names))


if __name__ == "__main__":
    main()
