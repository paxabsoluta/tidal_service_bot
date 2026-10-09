import discord
from discord import ui, app_commands
from discord.ext import commands

# ID роли, которую бот будет выдавать (замените на свой ID)
ROLE_ID = 1459994385281454326


class RoleLayoutView(ui.LayoutView):
    def __init__(self):
        # timeout=None делает view бессрочной
        super().__init__(timeout=None)

        self.add_item(
            ui.Container(
                ui.Section(
                    ui.TextDisplay("## Нажмите на кнопку, чтобы получить роль"),
                    accessory=ui.Button( # noqa
                        style=discord.ButtonStyle.success,
                        label="Получить роль",
                        custom_id="btn_give_role",  # Уникальный ID для сохранения состояния
                    ),
                ),
            ),
        )

    # Обработчик нажатия, который работает всегда (Persistent)
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.data.get("custom_id") == "btn_give_role":
            guild = interaction.guild
            member = interaction.user

            if not guild or not isinstance(member, discord.Member):
                return

            role = guild.get_role(ROLE_ID)
            if not role:
                await interaction.response.send_message("Ошибка: Роль не найдена на сервере.", ephemeral=True)
                return

            # Переключатель роли (выдать/забрать)
            if role in member.roles:
                await member.remove_roles(role)
                await interaction.response.send_message(f"С вас снята роль {role.mention}!", ephemeral=True)
            else:
                await member.add_roles(role)
                await interaction.response.send_message(f"Вам выдана роль {role.mention}!", ephemeral=True)


class RoleButtonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # 1. Ограничиваем команду только серверами (запрет работы в ЛС)
    @app_commands.guild_only()
    # 2. Доступ только для пользователей с правами Администратора
    @app_commands.default_permissions(administrator=True)
    # 3. Сама слэш-команда
    @app_commands.command(name="setup_start_verifier", description="Установить стартовое проверочное сообщение")
    async def slash_setup_button(self, interaction: discord.Interaction):
        # Создаем экземпляр нашей вечной панели
        view = RoleLayoutView()

        # Отправляем сообщение на сервере
        await interaction.response.send_message("Панель успешно установлена!", ephemeral=True)  # Подтверждение админу
        await interaction.channel.send(view=view)  # Сама панель для пользователей

    # Регистрация вечного View в памяти бота при каждом запуске
    @commands.Cog.listener()
    async def on_ready(self):
        # Без этой строчки кнопки перестанут работать после перезагрузки бота
        self.bot.add_view(RoleLayoutView())
        print(f"Вечная панель RoleLayoutView успешно добавлена в менеджер бота!")


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleButtonCog(bot))
