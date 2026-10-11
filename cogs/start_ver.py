import discord
from discord import ui, app_commands
from discord.ext import commands

# Укажите здесь ID ваших ролей верификации (замените на реальные ID)
ROLE_ID_1 = 123456789012345678  # Первая основная роль
ROLE_ID_2 = 987654321098765432  # Вторая основная роль


class VerificationLayoutView(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)  # Панель будет работать вечно

        # Красивое оформление Components V2 для верификации
        self.add_item(
            ui.Container(
                ui.Section(
                    ui.TextDisplay(
                        "## Добро пожаловать на сервер!\nНажмите на кнопку ниже, чтобы начать"),
                    accessory=ui.Button( # noqa
                        style=discord.ButtonStyle.success,
                        label="СТАРТ",
                        custom_id="btn_start_verification",  # Уникальный ID
                    ),  # type: ignore
                ),
            ),
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data.get("custom_id") == "btn_start_verification":

            # Мгновенно отвечаем Дискорду, чтобы кнопка не зависала
            await interaction.response.defer(ephemeral=True)

            guild = interaction.guild
            member = interaction.user

            if not guild or not isinstance(member, discord.Member):
                return True

            # Ищем роли на сервере
            role1 = guild.get_role(ROLE_ID_1)
            role2 = guild.get_role(ROLE_ID_2)

            if not role1 or not role2:
                await interaction.followup.send(
                    "❌ Ошибка: Роли верификации не найдены на сервере. Обратитесь к администрации.", ephemeral=True)
                return True

            # Проверяем, пройден ли уже процесс, чтобы не спамить запросами
            if role1 in member.roles and role2 in member.roles:
                await interaction.followup.send("ℹ️ Вы уже успешно прошли верификацию!", ephemeral=True)
                return True

            try:
                # Выдаем обе роли одним быстрым запросом
                await member.add_roles(role1, role2)
                await interaction.followup.send("🎉 Вы успешно прошли верификацию! Доступ к серверу открыт.",
                                                ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Ошибка: У бота нет прав на выдачу этих ролей. Проверьте иерархию ролей.", ephemeral=True)

            return True

        return True


class VerificationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Слэш-команда доступна только на сервере и только для Администраторов
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="setup_start_verifier", description="Установить кнопку верификации в текущий канал")
    async def slash_setup_verification(self, interaction: discord.Interaction):
        view = VerificationLayoutView()

        # Подтверждение для администратора
        await interaction.response.send_message("Панель верификации успешно установлена в этом канале!", ephemeral=True)
        # Отправка самой панели для пользователей
        await interaction.channel.send(view=view)

    # Перерегистрация кнопки при перезапуске бота, чтобы она не "умирала"
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(VerificationLayoutView())
        print(f"[Verification] Вечная панель верификации успешно зарегистрирована!")


async def setup(bot: commands.Bot):
    await bot.add_cog(VerificationCog(bot))
