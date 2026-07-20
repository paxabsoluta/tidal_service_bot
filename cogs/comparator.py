import os
import re
import discord
from discord import app_commands
from discord.ext import commands
from rcon.source import rcon  # Используем вашу готовую и рабочую библиотеку


# Класс для кнопок управления в чате
class WhitelistConfirmView(discord.ui.View):
    def __init__(self, cog, players_to_remove, players_to_add, author):
        super().__init__(timeout=300)  # Кнопки активны 5 минут
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
        self.rcon_host = str(os.getenv("MINECRAFT_RCON_IP", ""))
        self.rcon_port = int(os.getenv("MINECRAFT_RCON_PORT", 25575))
        self.rcon_password = str(os.getenv("MINECRAFT_RCON_PASS", ""))
        self.member_role_id = 1459994385289711828

    async def run_rcon_cmd(self, command: str) -> str:
        """Безопасная отправка команд с использованием вашей библиотеки rcon"""
        try:
            # Поскольку библиотека rcon асинхронная, вызываем её через await
            # Аргументы host и port передаются стандартно, пароль передается через passwd
            return await rcon(
                command,
                host=self.rcon_host,
                port=self.rcon_port,
                passwd=self.rcon_password
            )
        except Exception as e:
            return f"Ошибка RCON: {e}"

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
            await interaction.followup.send(f"❌ Не удалось подключиться к серверу через RCON: {rcon_response}")
            return

        clean_response = self.clean_minecraft_colors(rcon_response).strip()

        keyword = "in whitelist:"
        if keyword in clean_response.lower():
            start_index = clean_response.lower().find(keyword) + len(keyword)
            players_string = clean_response[start_index:].strip()
        else:
            players_string = clean_response

        # Список ников из игры
        mc_players = [p.strip() for p in players_string.split(",") if p.strip()]
        mc_players_lower = {p.lower() for p in mc_players}

        # 2. Сбор данных из Discord (по отображаемым именам пользователей)
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

        view = WhitelistConfirmView(self, suspicious_to_remove, suspicious_to_add, interaction.user)

        # Отключаем кнопки через явную проверку их текста, чтобы PyCharm не ругался
        for child in view.children:
            if isinstance(child, discord.ui.Button):
                if child.label == "Удалить «мусор»" and not suspicious_to_remove:
                    child.disabled = True
                elif child.label == "Добавить «потеряшек»" and not suspicious_to_add:
                    child.disabled = True

        await interaction.followup.send(full_report, view=view)

    @sync_whitelist.error
    async def sync_whitelist_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ Команда доступна только администраторам.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Comparator(bot))
