import discord
from discord.ext import commands
from discord import app_commands
import io
import chat_exporter

# Константы настроек
MAIN_CHANNEL_ID = 1473042971963166740
TICKET_CATEGORY_ID = 1525619777589219462
TRANSCRIPT_CHANNEL_ID = 1525621277191045261

ROLE_ADMIN = 1459994385289711830
ROLE_MODER = 1473235427250012251
ROLE_ARTIST = 1474348495233351722

# Конфигурация тем тикетов
TICKET_TOPICS = {
    "purchase": {
        "label": "Покупка на сайте",
        "emoji": "💶",
        "roles_to_allow": [ROLE_ADMIN],
        "roles_to_ping": [ROLE_ADMIN]
    },
    "support": {
        "label": "Поддержка",
        "emoji": "❓",
        "roles_to_allow": [ROLE_ADMIN, ROLE_MODER],
        "roles_to_ping": [ROLE_ADMIN, ROLE_MODER]
    },
    "bugs": {
        "label": "Баг-трекер",
        "emoji": "⚠️",
        "roles_to_allow": [ROLE_ADMIN],
        "roles_to_ping": [ROLE_ADMIN]
    },
    "design": {
        "label": "Отдел дизайна",
        "emoji": "🎨",
        "roles_to_allow": [ROLE_ADMIN, ROLE_MODER, ROLE_ARTIST],
        "roles_to_ping": [ROLE_ADMIN]
    },
    "content": {
        "label": "Стать контентмейкером",
        "emoji": "🎥",
        "roles_to_allow": [ROLE_ADMIN],
        "roles_to_ping": [ROLE_ADMIN]
    }
}


class TicketModal(discord.ui.Modal):
    def __init__(self, topic_id: str, topic_data: dict):
        super().__init__(title=f"Тикет: {topic_data['label']}")
        self.topic_id = topic_id
        self.topic_data = topic_data

        self.nickname = discord.ui.TextInput(
            label="Ваш никнейм",
            placeholder="Введите ваш ник на сервере...",
            min_length=3,
            max_length=16,
            required=True
        )
        self.issue = discord.ui.TextInput(
            label="Суть вашего обращения",
            style=discord.TextStyle.long,
            placeholder="Опишите вашу проблему как можно подробнее...",
            min_length=10,
            max_length=1000,
            required=True
        )

        self.add_item(self.nickname)
        self.add_item(self.issue)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send("Ошибка: Категория для тикетов не найдена.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True)
        }

        for role_id in self.topic_data["roles_to_allow"]:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True)

        channel_name = f"{self.topic_data['emoji']}︱{self.nickname.value}"

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites, # noqa
            topic=f"Тикет игрока {interaction.user.mention} (Ник: {self.nickname.value}) | Тема: {self.topic_data['label']}"
        )

        ping_mentions = [interaction.user.mention]
        for role_id in self.topic_data["roles_to_ping"]:
            role = guild.get_role(role_id)
            if role:
                ping_mentions.append(role.mention)

        ping_string = " ".join(ping_mentions)

        embed = discord.Embed(
            title=f"{self.topic_data['emoji']} Новое обращение: {self.topic_data['label']}",
            color=discord.Color.from_rgb(100, 210, 210)
        )
        embed.add_field(name="Игрок (Discord)", value=interaction.user.mention, inline=True)
        embed.add_field(name="Никнейм в Minecraft", value=self.nickname.value, inline=True)
        embed.add_field(name="Суть обращения", value=self.issue.value, inline=False)
        embed.set_footer(text="Для закрытия нажмите кнопку ниже. Транскрипт будет сохранен автоматически.")

        view = TicketControlView()
        main_msg = await ticket_channel.send(content=ping_string, embed=embed, view=view)
        await main_msg.pin()

        await interaction.followup.send(f"Ваш тикет успешно создан! Перейдите в канал: {ticket_channel.mention}", ephemeral=True)


class TicketSelectMenu(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=data["label"], value=key, emoji=data["emoji"]) # noqa
            for key, data in TICKET_TOPICS.items()
        ]
        # Добавляем custom_id для выпадающего меню, чтобы оно не слетало
        super().__init__(
            placeholder="Выберите тему вашего обращения...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_select_menu_main"
        )

    async def callback(self, interaction: discord.Interaction):
        if not self.values:
            return

        topic_id = self.values[0]

        if topic_id not in TICKET_TOPICS:
            await interaction.response.send_message("Ошибка: Тема не найдена.", ephemeral=True)
            return

        topic_data = TICKET_TOPICS[topic_id]
        await interaction.response.send_modal(TicketModal(topic_id, topic_data))


class TicketStartView(discord.ui.View):
    def __init__(self):
        # timeout=None делает представление постоянным
        super().__init__(timeout=None)
        self.add_item(TicketSelectMenu())


class TicketCloseReasonModal(discord.ui.Modal):
    def __init__(self, ticket_creator: discord.Member, channel: discord.TextChannel):
        super().__init__(title="Закрытие тикета")
        self.ticket_creator = ticket_creator
        self.channel = channel

        self.reason = discord.ui.TextInput(
            label="Причина закрытия тикета",
            style=discord.TextStyle.long,
            placeholder="Например: Меры приняты / Вопрос решен...",
            min_length=3,
            max_length=500,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        # Откладываем ответ, так как генерация HTML и отправка ЛС требуют времени
        await interaction.response.defer()

        guild = interaction.guild
        if not guild:
            return

        log_channel = guild.get_channel(TRANSCRIPT_CHANNEL_ID)

        # 1. Сначала отправляем сообщение в ЛС игроку
        try:
            embed_dm = discord.Embed(
                title="🔒 Ваш тикет закрыт",
                description=f"Ваш тикет на сервере **{guild.name}** был успешно закрыт.",
                color=discord.Color.from_rgb(100, 210, 210)
            )
            embed_dm.add_field(name="Причина закрытия", value=f"`{self.reason.value}`", inline=False)
            embed_dm.set_footer(text="Спасибо за обращение в поддержку проекта Tidal!")

            await self.ticket_creator.send(embed=embed_dm)
        except discord.Forbidden:
            # Если у игрока закрыты ЛС, бот не упадет, а продолжит работу
            await self.channel.send(
                "⚠️ *Не удалось отправить уведомление в ЛС игроку (у него закрыты личные сообщения).*")

        # 2. Оповещаем модератора в чате тикета
        await self.channel.send("💾 *Генерация HTML-транскрипта и архивация...*")

        import chat_exporter
        import io

        # 3. Полный цикл архивации, который мы настроили ранее
        try:
            transcript = await chat_exporter.export(self.channel, limit=500, bot=interaction.client)

            if transcript is not None:
                file_data = io.BytesIO(transcript.encode('utf-8'))
                transcript_file = discord.File(fp=file_data, filename=f"transcript-{self.channel.name}.html")

                log_embed = discord.Embed(
                    title="🔒 Тикет закрыт",
                    description=f"Канал **{self.channel.name}** был успешно удален.",
                    color=discord.Color.red()
                )
                log_embed.add_field(name="Кто закрыл", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="Причина", value=f"`{self.reason.value}`", inline=False)
                if self.channel.topic:
                    log_embed.add_field(name="Информация", value=self.channel.topic, inline=False)

                if log_channel and isinstance(log_channel, discord.TextChannel):
                    msg_with_file = await log_channel.send(file=transcript_file)
                    file_url = msg_with_file.attachments[0].url
                    web_url = f"https://github.io?{file_url}"

                    view = discord.ui.View()
                    view.add_item(
                        discord.ui.Button(label="Открыть в браузере", style=discord.ButtonStyle.link, url=web_url,
                                          emoji="🌐"))

                    await log_channel.send(embed=log_embed, view=view)

        except Exception as e:
            print(f"Ошибка при создании транскрипта: {e}")
            if log_channel and isinstance(log_channel, discord.TextChannel):
                await log_channel.send(f"⚠️ Ошибка создания HTML-лога для {self.channel.name}: `{e}`")

        # 4. Удаляем канал тикета
        await self.channel.delete()


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        # Проверка прав: закрыть может только персонал
        is_staff = any(role.id in [ROLE_ADMIN, ROLE_MODER] for role in interaction.user.roles)
        is_creator = channel.overwrites_for(interaction.user).read_messages is True

        if not (is_staff or is_creator):
            await interaction.response.send_message("У вас нет прав для закрытия этого тикета.", ephemeral=True)
            return

        # Нам нужно найти создателя тикета. Мы вытащим его из прав доступа (overwrites) канала
        ticket_creator = None
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Member) and not target.bot:
                # Если у обычного пользователя есть права отправлять сообщения — он создатель
                if overwrite.read_messages is True:
                    ticket_creator = target
                    break

        # Если создатель вышел с сервера или права сбились, подстрахуемся и укажем самого модератора
        if not ticket_creator:
            ticket_creator = interaction.user

        # Открываем модератору форму для ввода причины закрытия
        await interaction.response.send_modal(TicketCloseReasonModal(ticket_creator, channel))


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(TicketStartView())
        self.bot.add_view(TicketControlView())
        print("Ког тикетов успешно запущен!")

    @app_commands.command(name="setup_tickets", description="Отправить меню тикетов (Только для Администрации)")
    @app_commands.checks.has_any_role(ROLE_ADMIN)
    async def setup_tickets(self, interaction: discord.Interaction):
        target_channel = interaction.guild.get_channel(MAIN_CHANNEL_ID)

        if not target_channel or not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message("Ошибка: Целевой канал не найден.", ephemeral=True)
            return

        ticket_description = """
Возникли проблемы или есть вопросы? Создайте обращение в нашу поддержку!

**Как создать тикет:**
1. Нажмите на выпадающее меню ниже.
2. Выберите интересующую вас тему.
3. Заполните появившуюся форму и нажмите «Отправить».

*Наши специалисты ответят вам в созданном приватном канале в ближайшее время!*
        """.strip()

        embed = discord.Embed(
            title="📩 Техническая поддержка проекта Tidal",
            description=ticket_description,
            color=discord.Color.from_rgb(100, 210, 210)
        )
        embed.set_footer(text="Пожалуйста, выбирайте правильную тему для ускорения ответа.")

        await target_channel.send(embed=embed, view=TicketStartView())
        await interaction.response.send_message("Стартовое сообщение отправлено!", ephemeral=True)

    @app_commands.command(name="ticket_add", description="Добавить игрока в тикет (Только для Администрации)")
    @app_commands.describe(member="Игрок, которого нужно добавить")
    @app_commands.checks.has_any_role(ROLE_ADMIN)
    async def ticket_add(self, interaction: discord.Interaction, member: discord.Member):
        channel = interaction.channel

        if not channel.category or channel.category.id != TICKET_CATEGORY_ID:
            await interaction.response.send_message("Эту команду можно использовать только внутри тикетов!", ephemeral=True)
            return

        await channel.set_permissions(member, read_messages=True, send_messages=True, attach_files=True,
                                      embed_links=True)
        await interaction.response.send_message(f"Пользователь {member.mention} добавлен в этот тикет.")

    @setup_tickets.error
    @ticket_add.error
    async def ticket_commands_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingAnyRole):
            await interaction.response.send_message("У вас нет прав Администратора!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
