from __future__ import annotations

import ast
import re
from pathlib import Path

SOURCE = Path("AmirXProxy_single.py")
OUTPUT = Path("/tmp/AmirXProxy_single_fixed.py")

WATCHDOG = r'''

# Runtime hardening: never let one source/search operation keep a Telegram
# callback alive forever. The wrapper turns a stuck scan into a controlled
# failure and keeps the polling loop healthy.
def _with_search_timeout(bot, seconds: float = 45.0):
    import asyncio
    from functools import wraps

    def decorator(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                log.exception("Search handler timed out after %.1fs", seconds)
                try:
                    call = args[0] if args else None
                    message = getattr(call, "message", None)
                    chat = getattr(message, "chat", None)
                    message_id = getattr(message, "message_id", None)
                    chat_id = getattr(chat, "id", None)
                    if chat_id is not None and message_id is not None:
                        await bot.edit_message_text(
                            "⏱️ بررسی منابع بیش از حد طول کشید.\n\n"
                            "یکی از منابع پاسخ نداد و اسکن متوقف شد؛ دوباره تلاش کن.",
                            chat_id=chat_id,
                            message_id=message_id,
                        )
                except Exception:
                    log.exception("Could not update timed-out search message")
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

    if "_with_search_timeout" not in fixed:
        fixed = fixed.replace(
            "\n\n# ===== INLINED FROM AmirXProxy/",
            WATCHDOG + "\n\n# ===== INLINED FROM AmirXProxy/",
            1,
        )

    search_match = re.search(r"^(\s*)async def new_search\(", fixed, flags=re.MULTILINE)
    if search_match:
        indent = search_match.group(1)
        decorator = f"{indent}@_with_search_timeout(bot)\n"
        line_start = search_match.start()
        if fixed[line_start - len(decorator):line_start] != decorator:
            fixed = fixed[:line_start] + decorator + fixed[line_start:]
        print("Search watchdog installed for new_search().")
    else:
        print("WARNING: new_search() was not found; startup fix still applied.")

    tree = ast.parse(fixed, filename=str(OUTPUT))
    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    required = set(names) | {"build_bot", "main"}
    missing = sorted(required - function_names)
    if missing:
        raise RuntimeError(f"Runtime patch validation failed; missing: {missing}")

    OUTPUT.write_text(fixed, encoding="utf-8")
    print(f"Prepared fixed runtime: {OUTPUT}")
    print("Registered handler groups: " + ", ".join(names))


if __name__ == "__main__":
    main()
