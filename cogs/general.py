import discord
from discord import app_commands
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # 📋 СПИСОК АВТООТВЕТОВ (Словарь)
        # Слева — что пишет пользователь (маленькими буквами), справа — что отвечает бот.
        self.auto_replies = {
            "?айпи": "🔑 IP нашего сервера: **play.tidalmc.net**",
            "?ip": "🔑 IP нашего сервера: **play.tidalmc.net**",
            "?версия": "🎮 Версия нашего сервера: **1.21.11**",
            "?плюк": "🔆 Плюк - Чатланская планета. Поэтому мы, пацаки, должны цаки носить",
            "?MattWhiskers": "🚫 MattWhiskers (он же Матео, doomanyeo) - **известный мошенник, словоблуд и вор**",
            "?матео": "🚫 MattWhiskers (он же Матео, doomanyeo) - **известный мошенник, словоблуд и вор**",
            "?думанео": "🚫 MattWhiskers (он же Матео, doomanyeo) - **известный мошенник, словоблуд и вор**",
            "?думанье": "🚫 MattWhiskers (он же Матео, doomanyeo) - **известный мошенник, словоблуд и вор**",
            "?не ванильно": "Если что-то на сервере кажется вам слишком неестественным и выбивающимся из духа майнкрафта - запомните, что сервер **не позиционируется как ванильный**. Мы создаем прикольные механики, а не консервируем старое барахло. Всех благ. _Ваш, Tidal Service._"
            # Сюда можно легко добавлять новые ответы, например:
            # "?сайт": "🌐 Наш сайт: https://tidalmc.net",
            # "?донат": "💎 Купить донат: https://tidalmc.net"
        }

    # Слэш-команда /ping
    @app_commands.command(name="ping", description="Проверить задержку бота")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 Понг! Задержка: {latency}мс")

    # Перехватчик сообщений для автоответов
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Игнорируем сообщения от самого бота
        if message.author == self.bot.user:
            return

        # Приводим текст к нижнему регистру и убираем лишние пробелы по бокам
        text = message.content.lower().strip()

        # Ищем, есть ли написанный текст в нашем списке автоответов
        if text in self.auto_replies:
            # Если нашли — отправляем готовый ответ
            await message.channel.send(self.auto_replies[text])


# Функция подключения модуля
async def setup(bot):
    await bot.add_cog(General(bot))

