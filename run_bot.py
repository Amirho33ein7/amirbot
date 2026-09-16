import asyncio

from AmirFacts import bot, init_db


async def main() -> None:
    init_db()
    print("AmirFacts bot is RUNNING.")
    await bot.polling(non_stop=True, skip_pending=True)


if __name__ == "__main__":
    asyncio.run(main())
