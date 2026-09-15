from __future__ import annotations

import ast
from pathlib import Path

SOURCE = Path("AmirXProxy_single.py")
OUTPUT = Path("/tmp/AmirXProxy_single_fixed.py")


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

    tree = ast.parse(fixed, filename=str(OUTPUT))
    function_names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    required = set(names) | {"build_bot", "main"}
    missing = sorted(required - function_names)
    if missing:
        raise RuntimeError(f"Runtime patch validation failed; missing: {missing}")

    OUTPUT.write_text(fixed, encoding="utf-8")
    print(f"Prepared fixed runtime: {OUTPUT}")
    print("Registered handler groups: " + ", ".join(names))


if __name__ == "__main__":
    main()
