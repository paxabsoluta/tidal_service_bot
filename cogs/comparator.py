import os
import re
import struct
import asyncio
import discord
from discord import app_commands
from discord.ext import commands


# Класс для кнопок управления в чате
class WhitelistConfirmView(discord.ui.View):
    def __init__(self, cog, players_to_remove, players_to_add, author):
        super().__init__(timeout=300) # Кнопки активны 5 минут
        self.cog = cog
        self.players_to_remove = players_to_remove
        self.players_to_add = players_to_add
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Вы не можете использовать эти кнопки.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Удалить «мусор»", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def remove_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("⏳ Начинаю удаление игроков через RCON...")

        for player in self.players_to_remove:
            await self.cog.run_rcon_cmd(f"swl remove {player}")

        await interaction.followup.send(f"✅ Успешно удалено игроков: **{len(self.players_to_remove)}**.")

    @discord.ui.button(label="Добавить «потеряшек»", style=discord.ButtonStyle.success, emoji="➕")
    async def add_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("⏳ Начинаю добавление игроков в вайтлист...")

        for player in self.players_to_add:
            await self.cog.run_rcon_cmd(f"swl add {player}")

        await interaction.followup.send(f"✅ Успешно добавлено игроков: **{len(self.players_to_add)}**.")

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ Действие отменено.", view=self)
        self.stop()


# Основной класс кога
class Comparator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rcon_host = str(os.getenv("RCON_HOST", ""))
        self.rcon_port = int(os.getenv("RCON_PORT", 25575))
        self.rcon_password = str(os.getenv("RCON_PASSWORD", ""))
        self.member_role_id = 1459994385289711828

    async def run_rcon_cmd(self, command: str) -> str:
        """Автономная реализация RCON без внешних библиотек"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.rcon_host, self.rcon_port), timeout=5.0
            )
            auth_packet = struct.pack('<iii', 10 + len(self.rcon_password), 1, 3) + self.rcon_password.encode(
                'utf-8') + b'\x00\x00'
            writer.write(auth_packet)
            await writer.drain()
            await reader.read(4096)

            cmd_packet = struct.pack('<iii', 10 + len(command), 2, 2) + command.encode('utf-8') + b'\x00\x00'
            writer.write(cmd_packet)
            await writer.drain()

            response_header = await reader.read(12)
            if len(response_header) < 12:
                writer.close()
                await writer.wait_closed()
                return "Ошибка RCON"

            packet_len, packet_id, packet_type = struct.unpack('<iii', response_header)
            response_body = await reader.read(packet_len - 8)

            writer.close()
            await writer.wait_closed()
            return response_body.decode('utf-8', errors='ignore').strip()
        except Exception:
            return "Ошибка RCON"

    def clean_minecraft_colors(self, text: str) -> str:
        """Удаляет цветовые коды Майнкрафта"""
        return re.sub(r'§[0-9a-fk-orx]', '', text)

    @app_commands.command(name="sync_whitelist", description="Двусторонняя сверка вайтлиста игры с Discord")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync_whitelist(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳ Запускаю двусторонний аудит. Пожалуйста, подождите...")

        # 1. Получаем список игроков из Майнкрафта
        rcon_response = await self.run_rcon_cmd("swl list")

        if "Ошибка RCON" in rcon_response:
            await interaction.followup.send("❌ Не удалось подключиться к серверу через RCON. Проверьте .env данные.")
            return

        clean_response = self.clean_minecraft_colors(rcon_response).strip()

        keyword = "in whitelist:"
        if keyword in clean_response.lower():
            start_index = clean_response.lower().find(keyword) + len(keyword)
            players_string = clean_response[start_index:].strip()
        else:
            players_string = clean_response

        # Список ников из игры (сохраняем оригинальный регистр для команд, но чистим пробелы)
        mc_players = [p.strip() for p in players_string.split(",") if p.strip()]
        mc_players_lower = {p.lower() for p in mc_players}

        # 2. Сбор данных из Discord (сопоставляем нижний регистр и реальное отображаемое имя)
        guild = interaction.guild
        discord_members_map = {}  # {нижний_регистр: оригинальное_отображаемое_имя}

        async for member in guild.fetch_members(limit=None):
            if any(role.id == self.member_role_id for role in member.roles):
                name = member.display_name.strip()
                if name:
                    discord_members_map[name.lower()] = name

        # 3. Двусторонняя сверка
        suspicious_to_remove = []  # Есть в игре, но нет в ДС
        suspicious_to_add = []  # Есть в ДС, но нет в игре

        # Ищем кого удалить из игры
        for player in mc_players:
            if player.lower() not in discord_members_map:
                suspicious_to_remove.append(player)

        # Ищем кого добавить в игру
        for doc_lower, orig_name in discord_members_map.items():
            if doc_lower not in mc_players_lower:
                suspicious_to_add.append(orig_name)

        # 4. Формирование отчета
        if not suspicious_to_remove and not suspicious_to_add:
            await interaction.followup.send("✅ **Полная синхронизация!** Списки игры и Discord абсолютно идентичны.")
            return

        report_lines = ["📊 **Результаты двустороннего аудита:**\n"]

        if suspicious_to_remove:
            rm_str = ", ".join(suspicious_to_remove)
            report_lines.append(f"🗑️ **Есть в игре, но нет в Discord ({len(suspicious_to_remove)} чел.):**")
            report_lines.append(f"`{rm_str if len(rm_str) < 800 else rm_str[:800] + '...'}`\n")

        if suspicious_to_add:
            add_str = ", ".join(suspicious_to_add)
            report_lines.append(f"➕ **Есть в Discord, но нет в игре ({len(suspicious_to_add)} чел.):**")
            report_lines.append(f"`{add_str if len(add_str) < 800 else add_str[:800] + '...'}`\n")

        report_lines.append("Выберите действие на панелях ниже:")
        full_report = "\n".join(report_lines)

        # Создаем объект кнопок
        view = WhitelistConfirmView(self, suspicious_to_remove, suspicious_to_add, interaction.user)

        # Отключаем кнопки через явную проверку их текста, чтобы PyCharm не ругался
        for child in view.children:
            if isinstance(child, discord.ui.Button):
                if child.label == "Удалить «мусор»" and not suspicious_to_remove:
                    child.disabled = True
                elif child.label == "Добавить «потеряшек»" and not suspicious_to_add:
                    child.disabled = True

        # Отправляем отчет вместе с настроенными кнопками
        await interaction.followup.send(full_report, view=view)

    @sync_whitelist.error
    async def sync_whitelist_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ Команда доступна только администраторам.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Comparator(bot))