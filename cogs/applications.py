import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite

# ==================== НАСТРОЙКИ КОГА ====================
CONFIG = {
    "ROLE_DOSTUP_ID": 1479100141230358598,  # ID роли "доступ"
    "ROLE_MEMBER_ID": 1459994385289711828,  # ID роли "Member"
    "ROLE_DENIED_ID": 1474438745716555951,  # ID роли "Отказано"

    "CHANNEL_START_ID": 1459994385738629435,  # Канал с кнопкой "Подать заявку"
    "CHANNEL_ACTIVE_ID": 1526615816471318528,  # Приватный канал активных заявок
    "CHANNEL_ARCHIVE_ID": 1526615869700968609,  # Канал-архив закрытых заявок
}


# ========================================================

class StartButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Подать заявку", style=discord.ButtonStyle.green, custom_id="start_app_btn")
    async def start_app(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect("apps_database.db") as db:
            async with db.execute("SELECT 1 FROM apps WHERE user_id = ?", (interaction.user.id,)) as cursor:
                if await cursor.fetchone():
                    return await interaction.response.send_message(
                        "Вы уже подали заявку или у вас есть роль 'Отказано'.", ephemeral=True)

        await interaction.response.send_modal(ApplicationModal())


class ApplicationModal(discord.ui.Modal, title="Анкета на сервер Minecraft"):
    nickname = discord.ui.TextInput(label="Ваш никнейм в Minecraft?", placeholder="Пример: Steve", min_length=3, max_length=16)
    age = discord.ui.TextInput(label="Ваш реальный возраст?", placeholder="Пример: 18", min_length=2, max_length=3)
    source = discord.ui.TextInput(label="Откуда узнали про нас?", placeholder="TikTok, YouTube, ...", style=discord.TextStyle.short)
    friends = discord.ui.TextInput(label="Есть ли тут ваши друзья? Назовите их", placeholder="Пропустите, если нет", required=False)
    about = discord.ui.TextInput(label="Расскажите подробно про себя и свои планы", style=discord.TextStyle.paragraph, min_length=150, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        active_channel = guild.get_channel(CONFIG["CHANNEL_ACTIVE_ID"])
        if not active_channel:
            return await interaction.followup.send("Ошибка: Канал заявок не найден.", ephemeral=True)

        embed = discord.Embed(
            title="📥 Новая заявка на сервер",
            description=f"**Кандидат:** {interaction.user.mention}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="1. Ник в Minecraft:", value=f"```{self.nickname.value}```", inline=False)
        embed.add_field(name="2. Возраст:", value=self.age.value, inline=False)
        embed.add_field(name="3. Откуда узнали:", value=self.source.value, inline=False)
        embed.add_field(name="4. Друзья:", value=self.friends.value or "Нет", inline=False)
        embed.add_field(name="5. О себе и планах:", value=self.about.value, inline=False)
        embed.set_footer(text=f"ID Пользователя: {interaction.user.id}")

        view = ModeratorActionView()
        msg = await active_channel.send(embed=embed, view=view)

        async with aiosqlite.connect("apps_database.db") as db:
            await db.execute("INSERT INTO apps (message_id, user_id, mc_name) VALUES (?, ?, ?)",
                             (msg.id, interaction.user.id, self.nickname.value))
            await db.commit()
        await interaction.followup.send("Ваша заявка успешно отправлена!", ephemeral=True)


class RefusalReasonModal(discord.ui.Modal, title="Причина отклонения"):
    reason = discord.ui.TextInput(label="Укажите причину (увидит игрок):", style=discord.TextStyle.paragraph,
                                  max_length=500)

    def __init__(self, applicant: discord.Member, old_embed: discord.Embed, msg: discord.Message):
        super().__init__()
        self.applicant = applicant
        self.old_embed = old_embed
        self.msg = msg

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            soft_deny_embed = discord.Embed(
                title="🧧 Анкета",
                description=(
                    f"Есть новости для вас!\n"
                    f"Ваша анкета была рассмотрена и **отклонена** по следующей причине:\n\n"
                    f"> **{self.reason.value}**\n\n"
                    f"Не расстраивайтесь – у вас есть возможность исправить ошибки и заполнить её еще раз."
                ),
                color=discord.Color.from_rgb(47, 49, 54)
            )
            soft_deny_embed.set_footer(
                text=f"Tidal • All rights reserved © 2026",
                icon_url=interaction.client.user.display_avatar.url
            )
            await self.applicant.send(embed=soft_deny_embed)
        except discord.Forbidden:
            pass

        archive_channel = interaction.guild.get_channel(CONFIG["CHANNEL_ARCHIVE_ID"])
        if archive_channel:
            # Извлекаем первый эмбед из списка и создаем на его основе копию с новым цветом
            old_embed = self.old_embed[0] if isinstance(self.old_embed, list) else self.old_embed

            # Достаем ID пользователя из футера ("ID Пользователя: 123456789")
            try:
                applicant_id = old_embed.footer.text.split(": ")[1]
                applicant_mention = f"<@{applicant_id}>"
            except (AttributeError, IndexError, ValueError):
                applicant_mention = "Неизвестен"

            archive_embed = discord.Embed(
                title="❌ Отклонено (с переподачей)",
                description=f"**Кандидат:** {applicant_mention}\n**Модератор:** {interaction.user.mention}",
                color=discord.Color.orange()
            )
            # Копируем все поля из старой анкеты в архивную заявку
            for field in old_embed.fields:
                archive_embed.add_field(name=field.name, value=field.value, inline=field.inline)

            archive_embed.add_field(name="\u200b", value="\u200b", inline=False)

            # Добавляем причину отказа отдельным полем
            archive_embed.add_field(name="Причина отказа:", value=self.reason.value, inline=False)
            if old_embed.thumbnail:
                archive_embed.set_thumbnail(url=old_embed.thumbnail.url)

            await archive_channel.send(embed=archive_embed)

        async with aiosqlite.connect("apps_database.db") as db:
            await db.execute("DELETE FROM apps WHERE message_id = ?", (self.msg.id,))
            await db.commit()

        await self.msg.delete()
        await interaction.followup.send("Заявка отклонена.", ephemeral=True)


class ModeratorActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.green, custom_id="app_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        applicant_id = None
        mc_nickname = None

        # 1. Пытаемся найти заявку в базе данных
        async with aiosqlite.connect("apps_database.db") as db:
            async with db.execute("SELECT user_id, mc_name FROM apps WHERE message_id = ?",
                                  (interaction.message.id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    applicant_id, mc_nickname = row

        # 2. ПЛАН Б: Если в базе пусто после перезагрузки хостинга, читаем сам эмбед анкеты
        if (not applicant_id or not mc_nickname) and interaction.message and interaction.message.embeds:
            old_embed = interaction.message.embeds[0]

            # Вытаскиваем ID из футера
            try:
                footer_text = old_embed.footer.text if old_embed.footer else ""
                if "ID Пользователя:" in footer_text:
                    applicant_id = int(footer_text.split(": ")[1])
            except (IndexError, ValueError):
                pass

            # Вытаскиваем никнейм из полей
            try:
                for field in old_embed.fields:
                    if "Ник в Minecraft" in field.name:
                        mc_nickname = field.value.replace("```", "").strip()
                        break
            except AttributeError:
                pass

        # 3. Если данные не удалось найти вообще нигде (заявка повреждена)
        if not applicant_id or not mc_nickname:
            return await interaction.followup.send(
                "❌ Критическая ошибка: Не удалось определить ID игрока или его никнейм.", ephemeral=True)

        # 4. Проверяем, есть ли пользователь на сервере
        member = guild.get_member(applicant_id)

        # Если игрок ВЫШЕЛ с сервера — экстренная очистка и архивация
        if not member:
            archive_channel = guild.get_channel(CONFIG["CHANNEL_ARCHIVE_ID"])
            if archive_channel and interaction.message and interaction.message.embeds:
                old_embed = interaction.message.embeds[0]
                archive_embed = discord.Embed(
                    title="⚠️ Закрыто (Игрок вышел)",
                    description=f"**Кандидат:** <@{applicant_id}>\n**Модератор:** {interaction.user.mention}\n\n*Действие «Принять» отменено, так как пользователя нет на сервере.*",
                    color=discord.Color.light_grey()
                )
                for field in old_embed.fields:
                    archive_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                if old_embed.thumbnail:
                    archive_embed.set_thumbnail(url=old_embed.thumbnail.url)
                await archive_channel.send(embed=archive_embed)

            async with aiosqlite.connect("apps_database.db") as db:
                await db.execute("DELETE FROM apps WHERE message_id = ?", (interaction.message.id,))
                await db.commit()

            await interaction.message.delete()
            return await interaction.followup.send("Заявка заархивирована. Игрок вышел с сервера, база очищена.",
                                                   ephemeral=True)

        # 5. Если игрок на сервере — стандартный процесс выдачи ролей
        role_dostup = guild.get_role(CONFIG["ROLE_DOSTUP_ID"])
        role_member = guild.get_role(CONFIG["ROLE_MEMBER_ID"])

        if role_dostup and role_dostup in member.roles:
            await member.remove_roles(role_dostup)
        if role_member:
            await member.add_roles(role_member)

        try:
            await member.edit(nick=mc_nickname)
        except discord.Forbidden:
            pass

        try:
            accept_embed = discord.Embed(
                title="🧧 Анкета",
                description=(
                    f"Добрый день. Проверяющий вашу анкету является администратором сервера.\n"
                    f"Ваша анкета была рассмотрена и **одобрена**. Вы были добавлены на сервер.\n\n"
                    f"**Информация:** [Ваш текст приветствия, IP или ссылки]\n\n"
                    f"Приятной игры на сервере!"
                ),
                color=discord.Color.from_rgb(47, 49, 54)
            )
            accept_embed.set_footer(
                text=f"{guild.name} • All rights reserved © 2026",
                icon_url=interaction.client.user.display_avatar.url
            )
            await member.send(embed=accept_embed)
        except discord.Forbidden:
            pass

        # 6. Отправляем заполненную анкету в архив результатов
        archive_channel = guild.get_channel(CONFIG["CHANNEL_ARCHIVE_ID"])
        if archive_channel and interaction.message and interaction.message.embeds:
            old_embed = interaction.message.embeds[0]
            archive_embed = discord.Embed(
                title="✅ Принято",
                description=f"**Кандидат:** <@{applicant_id}>\n**Модератор:** {interaction.user.mention}",
                color=discord.Color.green()
            )
            for field in old_embed.fields:
                archive_embed.add_field(name=field.name, value=field.value, inline=field.inline)
            if old_embed.thumbnail:
                archive_embed.set_thumbnail(url=old_embed.thumbnail.url)
            await archive_channel.send(embed=archive_embed)

        # 7. Чистим базу данных
        async with aiosqlite.connect("apps_database.db") as db:
            await db.execute("DELETE FROM apps WHERE message_id = ?", (interaction.message.id,))
            await db.commit()

        # 8. Удаляем сообщение СРАЗУ (до запуска внешних когов)
        await interaction.message.delete()
        await interaction.followup.send("Игрок успешно принят!", ephemeral=True)

        # 9. Безопасный вызов вашей новой интеграции с MCRolesSync
        try:
            mc_sync_cog = getattr(interaction.client, "get_cog", lambda name: None)("MCRolesSync")
            if mc_sync_cog:
                interaction.client.loop.create_task(mc_sync_cog.process_accepted_player(mc_nickname)) # noqa
        except Exception as e:
            print(f"[MCRolesSync Ошибка] Не удалось синхронизировать роли: {e}")

    @discord.ui.button(label="Отклонить (Переподача)", style=discord.ButtonStyle.blurple, custom_id="app_soft_deny")
    async def soft_deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        async with aiosqlite.connect("apps_database.db") as db:
            async with db.execute("SELECT user_id FROM apps WHERE message_id = ?", (interaction.message.id,)) as cursor:
                row = await cursor.fetchone()
                if not row: return await interaction.response.send_message("Заявка не найдена в базе данных.", ephemeral=True)
                applicant_id = row[0]

        member = guild.get_member(applicant_id)
        if not member:
            archive_channel = guild.get_channel(CONFIG["CHANNEL_ARCHIVE_ID"])
            if archive_channel and interaction.message and interaction.message.embeds:
                old_embed = interaction.message.embeds[0]
                archive_embed = discord.Embed(
                    title="⚠️ Закрыто (Игрок вышел)",
                    description=f"**Кандидат:** <@{applicant_id}>\n**Модератор:** {interaction.user.mention}\n\n*Действие «Переподача» отменено, так как пользователя нет на сервере. Анкета заархивирована.*",
                    color=discord.Color.light_grey()
                )
                for field in old_embed.fields:
                    archive_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                if old_embed.thumbnail:
                    archive_embed.set_thumbnail(url=old_embed.thumbnail.url)
                await archive_channel.send(embed=archive_embed)

            async with aiosqlite.connect("apps_database.db") as db:
                await db.execute("DELETE FROM apps WHERE message_id = ?", (interaction.message.id,))
                await db.commit()

            await interaction.message.delete()
            return await interaction.response.send_message(
                "Заявка заархивирована. Игрок вышел с сервера, база очищена.", ephemeral=True)

        if not interaction.message:
            return await interaction.response.send_message("Сообщение не найдено.", ephemeral=True)

        await interaction.response.send_modal(
            RefusalReasonModal(member, interaction.message.embeds[0], interaction.message)
        )

    @discord.ui.button(label="Отклонить (Насовсем)", style=discord.ButtonStyle.red, custom_id="app_hard_deny")
    async def hard_deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        async with aiosqlite.connect("apps_database.db") as db:
            async with db.execute("SELECT user_id FROM apps WHERE message_id = ?", (interaction.message.id,)) as cursor:
                row = await cursor.fetchone()
                if not row: return await interaction.followup.send("Заявка не найдена в базе данных.", ephemeral=True)
                applicant_id = row[0]

        member = guild.get_member(applicant_id)
        if not member:
            archive_channel = guild.get_channel(CONFIG["CHANNEL_ARCHIVE_ID"])
            if archive_channel and interaction.message and interaction.message.embeds:
                old_embed = interaction.message.embeds[0]
                archive_embed = discord.Embed(
                    title="⛔ Перманентный отказ (Заочно)",
                    description=f"**Кандидат:** <@{applicant_id}>\n**Модератор:** {interaction.user.mention}\n\n*Игрока нет на сервере, но ему выдан вечный отказ. При попытке вернуться он не сможет подать анкету.*",
                    color=discord.Color.red()
                )
                for field in old_embed.fields:
                    archive_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                if old_embed.thumbnail:
                    archive_embed.set_thumbnail(url=old_embed.thumbnail.url)
                await archive_channel.send(embed=archive_embed)

            # Вместо удаления мы обновляем запись в базе данных!
            async with aiosqlite.connect("apps_database.db") as db:
                # Ставим вместо ID сообщения метку -1, чтобы бот помнил бан вечно
                await db.execute("UPDATE apps SET message_id = -1 WHERE user_id = ?", (applicant_id,))
                await db.commit()

            await interaction.message.delete()
            return await interaction.followup.send("Игроку выдан вечный отказ заочно. База заблокировала его ID.",
                                                   ephemeral=True)

        role_dostup = guild.get_role(CONFIG["ROLE_DOSTUP_ID"])
        role_denied = guild.get_role(CONFIG["ROLE_DENIED_ID"])

        # Безопасно снимаем роль "доступ" (убирает желтое предупреждение)
        if role_dostup and role_dostup in member.roles:
            await member.remove_roles(role_dostup)

        # Безопасно выдаем роль "Отказано" (убирает желтое предупреждение)
        if role_denied:
            await member.add_roles(role_denied)

        try:
            hard_deny_embed = discord.Embed(
                title="🧧 Анкета",
                description=(
                    f"Есть новости для вас!\n"
                    f"Ваша анкета была рассмотрена и **отклонена без возможности повторного заполнения**.\n\n"
                    f"Не расстраивайтесь – вы можете купить платное добавление на сервер без заполнения анкеты.\n"
                ),
                color=discord.Color.from_rgb(47, 49, 54)
            )
            hard_deny_embed.set_footer(
                text=f"{guild.name} • All rights reserved © 2026",
                icon_url=interaction.client.user.display_avatar.url
            )
            await member.send(embed=hard_deny_embed)
        except discord.Forbidden:
            pass

        archive_channel = guild.get_channel(CONFIG["CHANNEL_ARCHIVE_ID"])
        if archive_channel and interaction.message and interaction.message.embeds:
            # Берем оригинальный эмбед анкеты
            old_embed = interaction.message.embeds[0]

            # Создаем правильную копию для архива с красным цветом (исправляет ошибку с .color)
            archive_embed = discord.Embed(
                title="⛔ Перманентный отказ",
                description=f"**Кандидат:** <@{applicant_id}>\n**Модератор:** {interaction.user.mention}",
                color=discord.Color.red()
            )
            # Переносим все ответы кандидата в новое сообщение для архива
            for field in old_embed.fields:
                archive_embed.add_field(name=field.name, value=field.value, inline=field.inline)

            if old_embed.thumbnail:
                archive_embed.set_thumbnail(url=old_embed.thumbnail.url)

            await archive_channel.send(embed=archive_embed)

        await interaction.message.delete()
        await interaction.followup.send("Игроку выдан вечный отказ.", ephemeral=True)


class ApplicationsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        async with aiosqlite.connect("apps_database.db") as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS apps (message_id INTEGER PRIMARY KEY, user_id INTEGER, mc_name TEXT)")
            await db.commit()

        self.bot.add_view(StartButtonView())
        self.bot.add_view(ModeratorActionView())
        print("Ког заявок успешно загружен, все кнопки зарегистрированы!")

    # Теперь это красивая слэш-команда /setup_apps
    @app_commands.command(name="setup_apps", description="Создать стартовое сообщение с кнопкой подачи заявки")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_apps(self, interaction: discord.Interaction):
        # Так как это слэш-команда, вместо ctx мы используем interaction
        channel = interaction.guild.get_channel(CONFIG["CHANNEL_START_ID"])
        if not channel:
            return await interaction.response.send_message("Стартовый канал не найден.", ephemeral=True)

        embed = discord.Embed(
            title="📋 Подача заявки на сервер",
            description="Добро пожаловать! Чтобы попасть на наш сервер, нажмите на кнопку ниже и заполните анкету.",
            color=discord.Color.from_rgb(100, 210, 210)
        )
        embed.set_footer(
            text="Tidal • all rights reserved © 2026",
            icon_url=self.bot.user.display_avatar.url
        )
        await channel.send(embed=embed, view=StartButtonView())
        await interaction.response.send_message("Стартовое сообщение успешно создано в канале!", ephemeral=True)

    # Скрытая слэш-команда для полной очистки данных игрока в базе
    @app_commands.command(name="reset_user",
                          description="Очистить данные игрока в базе заявок, чтобы он мог подать её снова")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_user(self, interaction: discord.Interaction, user: discord.User):
        async with aiosqlite.connect("apps_database.db") as db:
            # Удаляем все записи, связанные с этим ID пользователя
            await db.execute("DELETE FROM apps WHERE user_id = ?", (user.id,))
            await db.commit()

        await interaction.response.send_message(
            f"✅ Данные пользователя {user.mention} успешно удалены из базы. Он может подавать заявку снова!",
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(ApplicationsCog(bot))
