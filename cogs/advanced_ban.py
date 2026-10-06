import discord
from discord.ext import commands
from discord import app_commands


class AdvancedBan(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="advanced_ban", description="Оповещает пользователя в ЛС и банит его на сервере")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(
        member="Пользователь, которого нужно забанить",
        reason="Причина бана (необязательно)"
    )
    async def advanced_ban(
            self,
            interaction: discord.Interaction,
            member: discord.Member,
            reason: str = "Причина не указана."  # Стандартная заглушка
    ):
        # Откладываем ответ, так как отправка ЛС и бан могут занять больше 3 секунд
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild

        # 1. Создаем красивый Embed для отправки в ЛС пользователю
        dm_embed = discord.Embed(
            title=f"🚨 Вы были забанены на сервере {guild.name}",
            description="Если вы считаете, что бан выдан по ошибке, обратитесь к администрации.",
            color=discord.Color.red()
        )
        dm_embed.add_field(name="📋 Причина", value=reason, inline=False)
        dm_embed.add_field(name="🛡️ Модератор", value=interaction.user.mention, inline=True)
        if guild.icon:
            dm_embed.set_thumbnail(url=guild.icon.url)
        dm_embed.timestamp = interaction.created_at

        # Попытка отправить сообщение в ЛС
        dm_sent = False
        try:
            await member.send(embed=dm_embed)
            dm_sent = True
        except discord.Forbidden:
            # Ошибка возникнет, если у пользователя закрыты ЛС или бот у него в блоке
            dm_sent = False

            # 2. Выполняем бан на сервере
        try:
            await member.ban(
                delete_message_seconds=0,
                reason=f"Модератор: {interaction.user.name} | Причина: {reason}"
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Не удалось забанить пользователя. У бота недостаточно прав (его роль должна быть выше роли нарушителя).",
                ephemeral=True
            )
            return

        # 3. Создаем красивый Embed-ответ для чата на сервере
        server_embed = discord.Embed(
            title="🔨 Пользователь успешно забанен",
            color=discord.Color.dark_red()
        )
        server_embed.add_field(name="👤 Нарушитель", value=f"{member.mention} ({member.name})", inline=True)
        server_embed.add_field(name="🛡️ Модератор", value=interaction.user.mention, inline=True)
        server_embed.add_field(name="📋 Причина", value=reason, inline=False)

        # Добавляем статус уведомления в ЛС
        dm_status = "✅ Уведомление успешно доставлено." if dm_sent else "⚠️ Не удалось отправить уведомление."
        server_embed.set_footer(text=dm_status)
        server_embed.timestamp = interaction.created_at

        # Отправляем финальный красивый ответ в канал (видимый всем)
        await interaction.channel.send(embed=server_embed)

        # Подтверждаем выполнение модератору в скрытом ответе
        await interaction.followup.send("Команда выполнена успешно!", ephemeral=True)

    # Обработчик ошибок для этой команды
    @advanced_ban.error
    async def ban_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ У вас нет прав `Использовать бан участников` для выполнения этой команды!",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdvancedBan(bot))
