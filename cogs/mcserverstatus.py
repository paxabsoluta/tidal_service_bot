import discord
from discord import app_commands
from discord.ext import commands
from mcstatus import JavaServer


class MinecraftStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Вспомогательная функция для удаления ВСЕХ цветовых кодов вроде §c, §4, §l
    def clean_minecraft_text(self, text: str) -> str:
            import re
            if not text:
                return ""
            return re.sub(r'§.', '', text)

    @app_commands.command(name="status", description="Показывает детальный статус игрового сервера Minecraft")
    async def server_status(self, interaction: discord.Interaction):
        # 🔔 ВАЖНО: Замените на IP вашего сервера
        SERVER_ADDRESS = "play.tidalmc.net"

        await interaction.response.defer()

        try:
            # Опрашиваем игровой сервер
            server = JavaServer.lookup(SERVER_ADDRESS)
            status = await server.async_status()

            # Секция 1: Статус сервера (если ответил — значит включен)
            status_text = "🟢 **ВКЛЮЧЕН**"

            # Очищаем MOTD и версию от майнкрафтовских цветовых кодов (§4, §l) для проверки текста
            motd_raw = status.description.to_plaintext() if hasattr(status.description, 'to_plaintext') else str(
                status.description)
            motd_clean = self.clean_minecraft_text(motd_raw)
            version_clean = self.clean_minecraft_text(status.version.name)

            # Секция 2: Статус тех.работ (Авто-определение)
            MAINTENANCE_KEYWORD = "техработы"

            # Проверяем наличие ключевого слова в MOTD или слова "ожидайте" в строке версии
            is_maintenance = (MAINTENANCE_KEYWORD in motd_clean.lower() or
                              "ожидайте" in version_clean.lower())

            if is_maintenance:
                maintenance_text = "⚠️ **ИДУТ** (Вход ограничен)"
                embed_color = discord.Color.orange()  # Оранжевый цвет во время тех. работ
            else:
                maintenance_text = "✅ **НЕ ИДУТ** (Сервер доступен для всех)"
                embed_color = discord.Color.green()  # Зеленый цвет в обычном режиме

            # Секция 3: Количество игроков
            players_online = status.players.online
            players_max = status.players.max
            players_count_text = f"`{players_online}`"

            # Секция 4: Список никнеймов игроков
            if players_online > 0 and status.players.sample:
                player_list = [player.name for player in status.players.sample]
                players_names_text = ", ".join(f"`{self.clean_minecraft_text(name)}`" for name in player_list)
            elif players_online > 0:
                players_names_text = "ℹ️ _Сервер скрывает имена игроков_"
            else:
                players_names_text = "_На сервере никого нет_"

            # Собираем красивый Эмбед
            embed = discord.Embed(
                title=f"⛏️ Статус сервера {SERVER_ADDRESS}",
                color=embed_color
            )
            embed.add_field(name="1. Статус сервера", value=status_text, inline=False)
            embed.add_field(name="2. Технические работы", value=maintenance_text, inline=False)
            embed.add_field(name="3. Игроков онлайн", value=players_count_text, inline=False)
            embed.add_field(name="4. Игроки на сервере", value=players_names_text, inline=False)

            from datetime import datetime
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
            embed.set_footer(
                text=f"Tidal • all rights reserved © 2026 • {current_time}",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )

            # Если идут тех. работы, подменяем MOTD на тот, что выдает плагин
            if is_maintenance:
                embed.add_field(name="📝 Сообщение тех.работ", value=f"```\n{motd_clean}\n```", inline=False)

            await interaction.followup.send(embed=embed)

        except Exception:
            # Если сервер полностью выключен (хостинг майнкрафта остановлен)
            embed = discord.Embed(
                title=f"⛏️ Статус сервера {SERVER_ADDRESS}",
                color=discord.Color.red()  # Красный цвет, если сервер выключен
            )
            embed.add_field(name="1. Статус сервера", value="🔴 **ВЫКЛЮЧЕН**", inline=False)
            embed.add_field(name="2. Технические работы", value="❓ **Неизвестно** (Сервер недоступен)", inline=False)
            embed.add_field(name="3. Игроков онлайн", value="`0` / `0`", inline=False)
            embed.add_field(name="4. Игроки на сервере", value="_Сервер офлайн_", inline=False)

            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MinecraftStatus(bot))
