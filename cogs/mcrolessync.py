import os
import discord
from discord import app_commands  # Импортируем модуль слэш-команд
from discord.ext import commands
from rcon.source import rcon
from dotenv import load_dotenv

load_dotenv()


class MCRolesSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Настройки RCON
        self.RCON_IP = os.getenv("MINECRAFT_RCON_IP", "127.0.0.1")
        self.RCON_PORT = int(os.getenv("MINECRAFT_RCON_PORT", 25575))
        self.RCON_PASS = os.getenv("MINECRAFT_RCON_PASS")

        # Исключения для Администрации (ID: "Ник")
        self.ADMIN_EXCEPTIONS = {
            1095418179012014160: "PaxAbsoluta",
        }

        # Настройка пар "РОЛЬ -> ПРАВА"
        self.ROLE_MAPPING = {
            111111111111111111: {"type": "group", "name": "vip"},
            222222222222222222: {"type": "temp_group", "name": "moder", "duration": "30d"},
            333333333333333333: {"type": "permission", "name": "cmi.command.fly"}
        }

    async def send_rcon_command(self, command: str):
        """Отправка команд в консоль Minecraft"""
        if not self.RCON_PASS:
            print(f"[MCRolesSync Ошибка] Пароль RCON отсутствует.")
            return None
        try:
            return await rcon(command, host=self.RCON_IP, port=self.RCON_PORT, passwd=self.RCON_PASS)
        except Exception as e:
            print(f"[MCRolesSync Ошибка RCON] Команда '{command}': {e}")
            return None

    def get_minecraft_name(self, member: discord.Member) -> str:
        """Определяет игровой ник с учетом исключений админов"""
        if member.id in self.ADMIN_EXCEPTIONS:
            return self.ADMIN_EXCEPTIONS[member.id]
        return member.display_name

    # ==========================================
    # ЧАСТЬ 1: ФУНКЦИЯ ДЛЯ ТИKЕТ-СИСТЕМЫ (ПРОХОДКИ)
    # ==========================================
    async def process_accepted_player(self, nickname: str):
        """Добавляет игрока в вайтлист при одобрении заявки"""
        await self.send_rcon_command(f"swl add {nickname}")
        print(f"[MCRolesSync] Игрок {nickname} добавлен в SimpleWhiteList через тикет.")

    # ==========================================
    # ЧАСТЬ 2: АВТОМАТИЧЕСКАЯ СИНХРОНИЗАЦИЯ РОЛЕЙ
    # ==========================================
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles:
            return

        mc_nickname = self.get_minecraft_name(after)
        added_roles = [r for r in after.roles if r not in before.roles]
        removed_roles = [r for r in before.roles if r not in after.roles]

        # Выдача ролей
        for role in added_roles:
            if role.id in self.ROLE_MAPPING:
                cfg = self.ROLE_MAPPING[role.id]
                if cfg["type"] == "group":
                    await self.send_rcon_command(f"lp user {mc_nickname} parent add {cfg['name']}")
                elif cfg["type"] == "temp_group":
                    await self.send_rcon_command(
                        f"lp user {mc_nickname} parent addtemp {cfg['name']} {cfg['duration']}")
                elif cfg["type"] == "permission":
                    await self.send_rcon_command(f"lp user {mc_nickname} permission set {cfg['name']} true")
                print(f"[MCRolesSync] Выдано {cfg['type']} {cfg['name']} для {mc_nickname}")

        # Снятие ролей
        for role in removed_roles:
            if role.id in self.ROLE_MAPPING:
                cfg = self.ROLE_MAPPING[role.id]
                if cfg["type"] in ["group", "temp_group"]:
                    await self.send_rcon_command(f"lp user {mc_nickname} parent remove {cfg['name']}")
                elif cfg["type"] == "permission":
                    await self.send_rcon_command(f"lp user {mc_nickname} permission unset {cfg['name']}")
                print(f"[MCRolesSync] Снято {cfg['type']} {cfg['name']} у {mc_nickname}")

    # ==========================================
    # ЧАСТЬ 3: ИГРОК ПОКИНУЛ ДИСКОРД (ВЫШЕЛ / БАН)
    # ==========================================
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.id in self.ADMIN_EXCEPTIONS:
            print(f"[MCRolesSync] Администратор {member.name} покинул Discord. Действия пропущены.")
            return

        mc_nickname = member.display_name
        print(
            f"[MCRolesSync] Пользователь {member.name} (Игровой ник: {mc_nickname}) покинул Discord. Аннулирую доступ...")

        await self.send_rcon_command(f"swl remove {mc_nickname}")
        await self.send_rcon_command(f"lp user {mc_nickname} clear")

    # ==========================================
    # ВРЕМЕННАЯ СЛЭШ-КОМАНДА ДЛЯ ТЕСТА СВЯЗИ
    # ==========================================
    @app_commands.command(name="rcon_test", description="Тестирует RCON-подключение к Майнкрафт серверу")
    @app_commands.checks.has_permissions(administrator=True)
    async def rcon_test(self, interaction: discord.Interaction, test_cmd: str = "list"):
        """Вызывается через /rcon_test"""
        await interaction.response.send_message("⌛ Отправляю тестовую команду в консоль Purpur...")
        response = await self.send_rcon_command(test_cmd)

        if response is not None:
            clean_response = str(response).strip()
            if not clean_response:
                clean_response = "[Сервер выполнил команду, но ничего не вернул в ответ]"
            await interaction.followup.send(f"✅ Успех! Ответ сервера:\n```\n{clean_response}\n```")
        else:
            await interaction.followup.send(
                "❌ Ошибка! Не удалось связаться с сервером. Проверьте настройки портов и пароля.")

    # ==========================================
    # СЛЭШ-КОМАНДА ДЛЯ СМЕНЫ НИКА ЧЕРЕЗ ТЕХ.ПОДДЕРЖКУ
    # ==========================================
    @app_commands.command(name="changenick",
                          description="Переносит проходку вайтлиста и донат-роли на новый ник игрока")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def change_nick_command(self, interaction: discord.Interaction, member: discord.Member, new_nickname: str):
        """Вызывается через /changenick"""
        old_nickname = self.get_minecraft_name(member)
        await interaction.response.send_message(f"🔄 Начинаю процесс переноса с `{old_nickname}` на `{new_nickname}`...")

        if member.id not in self.ADMIN_EXCEPTIONS:
            try:
                await member.edit(nick=new_nickname)
            except Exception:
                await interaction.followup.send(
                    f"⚠️ Не удалось изменить ник в Discord (нет прав), но в игре перенос продолжится.")

        await self.send_rcon_command(f"swl remove {old_nickname}")
        await self.send_rcon_command(f"swl add {new_nickname}")

        transferred_count = 0
        for role in member.roles:
            if role.id in self.ROLE_MAPPING:
                cfg = self.ROLE_MAPPING[role.id]
                if cfg["type"] in ["group", "temp_group"]:
                    await self.send_rcon_command(f"lp user {old_nickname} parent remove {cfg['name']}")
                    await self.send_rcon_command(f"lp user {new_nickname} parent add {cfg['name']}")
                elif cfg["type"] == "permission":
                    await self.send_rcon_command(f"lp user {old_nickname} permission unset {cfg['name']}")
                    await self.send_rcon_command(f"lp user {new_nickname} permission set {cfg['name']} true")
                transferred_count += 1

        await interaction.followup.send(
            f"✅ Перенос завершен! Из вайтлиста убран `{old_nickname}`, добавлен `{new_nickname}`. Перенесено LP-прав: {transferred_count}.")


async def setup(bot):
    await bot.add_cog(MCRolesSync(bot))