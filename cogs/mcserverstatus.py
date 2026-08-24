import discord
from discord import app_commands
from discord.ext import commands
from mcstatus import JavaServer
import os
from rcon.source import rcon


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

            # ПРОВЕРКА НА ЗАГЛУШКУ ХОСТИНГА (Если сервер реально выключен)
            HOSTING_KEYWORDS = ["hosting-minecraft", "minecraft.pro", "сервер отключен", "offline", "вероятно", "hm proxy", "недоступен"]
            is_hosting_fallback = any(word in motd_clean.lower() or word in version_clean.lower() for word in HOSTING_KEYWORDS)
            if is_hosting_fallback:
                raise ConnectionRefusedError("Заглушка Anycast")

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
                embed_color = discord.Color.teal()  # Зеленый цвет в обычном режиме

            # Секция 3: Количество игроков
            players_online = status.players.online
            players_max = status.players.max
            players_count_text = f"`{players_online}`"

            # Секция 4: Список никнеймов игроков
            if is_maintenance:
                players_names_text = "⚙ _Доступ временно ограничен_"
            elif players_online > 0:
                try:
                    # Читаем переменные и гарантируем, что это строки (добавляя пустую строку '' на крайний случай)
                    rcon_ip = os.getenv('MINECRAFT_RCON_IP', '')
                    rcon_port = int(os.getenv('MINECRAFT_RCON_PORT', 25575))
                    rcon_pass = os.getenv('MINECRAFT_RCON_PASS', '')

                    # Теперь PyCharm спокоен, так как rcon_pass гарантированно является строкой
                    rcon_response = await rcon(
                        "list",
                        host=rcon_ip,
                        port=rcon_port,
                        passwd=rcon_pass
                    )

                    # Майнкрафт обычно отвечает: "Игроков онлайн: X из Y: ник1, ник2"
                    if ":" in rcon_response:
                        # Исправлено: берем элемент [1] (все что после двоеточия) и только потом очищаем пробелы
                        raw_names = rcon_response.split(":", 1)[1].strip()
                        if raw_names:
                            # Разделяем ники запятыми, очищаем от пробелов и мусора
                            player_list = [name.strip() for name in raw_names.split(",")]
                            # Создаем нумерованный список, где каждый игрок с новой строки
                            numbered_list = [
                                f"{i}. `{self.clean_minecraft_text(name)}`"
                                for i, name in enumerate(player_list, start=1)
                            ]
                            players_names_text = "\n".join(numbered_list)
                        else:
                            players_names_text = "_На сервере никого нет_"
                    else:
                        players_names_text = f"```\n{self.clean_minecraft_text(rcon_response)}\n```"

                except Exception as rcon_error:
                    # Если RCON не ответил, выводим ошибку, чтобы не ломать команду
                    players_names_text = f"⚠ _Ошибка RCON: не удалось получить список игроков_"
                    print(f"[RCON Error]: {rcon_error}")
            else:
                players_names_text = "_На сервере никого нет_"

            # Собираем красивый Эмбед
            embed = discord.Embed(
                title=f"🌊️ Статус сервера {SERVER_ADDRESS}",
                color=embed_color
            )
            embed.add_field(name="1. Статус сервера", value=status_text, inline=False)
            embed.add_field(name="2. Технические работы", value=maintenance_text, inline=False)
            embed.add_field(name="3. Игроков онлайн", value=players_count_text, inline=False)
            embed.add_field(name="4. Игроки на сервере", value=players_names_text, inline=False)

            from datetime import datetime
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M UTC")
            embed.set_footer(
                text=f"Tidal • all rights reserved © 2026 • {current_time}",
                icon_url=self.bot.user.display_avatar.url
            )

            # Если идут тех. работы, подменяем MOTD на тот, что выдает плагин
            if is_maintenance:
                embed.add_field(name="📝 Сообщение тех.работ", value=f"```\n{motd_clean}\n```", inline=False)

            await interaction.followup.send(embed=embed)

        except Exception:
            # Если сервер полностью выключен (хостинг майнкрафта остановлен)
            embed = discord.Embed(
                title=f"🌊️️ Статус сервера {SERVER_ADDRESS}",
                color=discord.Color.red()  # Красный цвет, если сервер выключен
            )
            embed.add_field(name="1. Статус сервера", value="🔴 **ВЫКЛЮЧЕН**", inline=False)
            embed.add_field(name="2. Технические работы", value="❓ **Неизвестно** (Сервер недоступен)", inline=False)
            embed.add_field(name="3. Игроков онлайн", value="-", inline=False)
            embed.add_field(name="4. Игроки на сервере", value="-", inline=False)

            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MinecraftStatus(bot))
