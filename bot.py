import asyncio
import os
from discord.ext import commands
import discord
from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Настраиваем доступы (Intents), которые мы включили на сайте
intents = discord.Intents.default()
intents.message_content = True  # Разрешаем читать текст сообщений
intents.members = True          # Разрешаем видеть участников сервера

# Создаем движок бота с префиксом команд "!"
# хотя в будущем мы настроим современные слэш-команды "/"
bot = commands.Bot(command_prefix="!", intents=intents)


# Событие: когда бот успешно подключился к Discord
@bot.event
async def on_ready():
    print(f"📦 Модули проверены. Синхронизируем команды...")
    try:
        # Эта строчка регистрирует ВСЕ слэш-команды в самом Discord
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")

    print(f"✅ Бот {bot.user.name} успешно запущен и готов к работе!")


# Функция для автоматического поиска и загрузки модулей (команд) из папки cogs
async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            # Загружаем файл, отрезая ".py" с конца названия
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"📦 Модуль cogs.{filename[:-3]} успешно загружен")


# Главная функция запуска проекта
async def main():
    async with bot:
        await load_extensions()  # Сначала подключаем команды
        await bot.start(TOKEN)   # Затем включаем самого бота


# Запуск программы
if __name__ == "__main__":
    asyncio.run(main())
