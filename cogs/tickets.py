import discord
from discord.ext import commands
from discord import app_commands
import io

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
        super().__init__(placeholder="Выберите тему вашего обращения...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Проверяем, что выбор вообще сделан, чтобы избежать случайного IndexError
        if not self.values:
            return

        topic_id = self.values[0]

        # Защитная проверка: существует ли такая тема в нашем словаре
        if topic_id not in TICKET_TOPICS:
            await interaction.response.send_message("Ошибка: Выбранная тема не существует.", ephemeral=True)
            return

        topic_data = TICKET_TOPICS[topic_id]
        # Открываем форму игроку
        await interaction.response.send_modal(TicketModal(topic_id, topic_data))


class TicketStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelectMenu())


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        channel = interaction.channel
        guild = interaction.guild
        log_channel = guild.get_channel(TRANSCRIPT_CHANNEL_ID)

        is_staff = any(role.id in [ROLE_ADMIN, ROLE_MODER] for role in interaction.user.roles)
        is_creator = channel.overwrites_for(interaction.user).read_messages is True

        if not (is_staff or is_creator):
            await interaction.followup.send("У вас нет прав для закрытия этого тикета.", ephemeral=True)
            return

        await channel.send("💾 *Генерация транскрипта и закрытие канала...*")

        transcript_text = f"=== ТРАНСКРИПТ ТИКЕТА: {channel.name} ===\n"
        transcript_text += f"Закрыт пользователем: {interaction.user.name} ({interaction.user.id})\n"
        transcript_text += "=========================================\n\n"

        async for message in channel.history(limit=500, oldest_first=True):
            time_str = message.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            content = message.clean_content if message.content else "[Вложения/Эмбед]"
            transcript_text += f"[{time_str}] {message.author.name}: {content}\n"

        file_data = io.BytesIO(transcript_text.encode('utf-8'))
        transcript_file = discord.File(fp=file_data, filename=f"transcript-{channel.name}.txt")

        if log_channel and isinstance(log_channel, discord.TextChannel):
            log_embed = discord.Embed(
                title="🔒 Тикет закрыт",
                description=f"Канал **{channel.name}** был успешно удален.\nЛог переписки прикреплен ниже.",
                color=discord.Color.red()
            )
            log_embed.add_field(name="Кто закрыл", value=interaction.user.mention, inline=True)
            if channel.topic:
                log_embed.add_field(name="Информация", value=channel.topic, inline=False)

            await log_channel.send(embed=log_embed, file=transcript_file)

        await channel.delete()


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
