import discord
from discord.ext import commands

# ID канала, который нужно модерировать (замените на свой ID)
MEDIA_CHANNEL_ID = 1459994386820501679


class MediaFilterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Игнорируем сообщения от самого бота
        if message.author == self.bot.user:
            return

        # Проверяем, что сообщение написано именно в целевом медиа-канале
        if message.channel.id != MEDIA_CHANNEL_ID:
            return

        # НОВАЯ ПРОВЕРКА: Если у автора есть права администратора — игнорируем
        # guild_permissions проверяет права пользователя на этом конкретном сервере
        if isinstance(message.author, discord.Member) and message.author.guild_permissions.administrator:
            return

        # Проверяем наличие вложений (картинок/видео) или ссылок на медиа
        has_attachments = len(message.attachments) > 0
        has_embeds = len(message.embeds) > 0

        # Если нет ни файлов, ни ссылок — удаляем
        if not (has_attachments or has_embeds):
            try:
                await message.delete()
                await message.author.send(
                    f"Привет, {message.author.name}! Твое сообщение в канале "
                    f"{message.channel.mention} было удалено, так как там разрешены только медиа-файлы. 📸"
                )
            except discord.Forbidden:
                print(f"[Ошибка] У бота нет прав на удаление или отправку ЛС.")
            except discord.HTTPException as e:
                print(f"[Ошибка] Не удалось удалить сообщение: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(MediaFilterCog(bot))
