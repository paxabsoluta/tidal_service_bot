import discord
from discord import ui, app_commands
from discord.ext import commands

# Укажите здесь ID роли, которую бот будет выдавать (замените на ваш реальный ID)
ROLE_ID = 1459994385281454326


class RoleLayoutView(ui.LayoutView):
    def __init__(self):
        # timeout=None критически важен для вечных панелей
        super().__init__(timeout=None)

        # Строим структуру Components V2 (Container -> Section -> Button)
        self.add_item(
            ui.Container(
                ui.Section(
                    ui.TextDisplay("## Нажмите на кнопку, чтобы начать"),
                    # Используем стандартный ui.Button
                    # Комментарий # type: ignore отключает ложную подсветку типов в PyCharm/VS Code
                    accessory=ui.Button( # noqa
                        style=discord.ButtonStyle.success,
                        label="СТАРТ",
                        custom_id="btn_give_role",  # По этому ID бот узнает кнопку после перезапуска
                    ),  # type: ignore
                ),
            ),
        )

    # Защищенный обработчик взаимодействия низкого уровня для LayoutView
    # Меняем название метода на встроенный interaction_check
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Проверяем, что нажата именно наша кнопка
        if interaction.data.get("custom_id") == "btn_give_role":

            # Мгновенно уведомляем Discord, что запрос принят
            await interaction.response.defer(ephemeral=True)

            guild = interaction.guild
            member = interaction.user

            if not guild or not isinstance(member, discord.Member):
                return True

            role = guild.get_role(ROLE_ID)
            if not role:
                await interaction.followup.send("❌ Ошибка: Указанная роль не найдена на сервере.", ephemeral=True)
                return True

            # Переключатель роли (выдать, если нет / забрать, если есть)
            if role in member.roles:
                await member.remove_roles(role)
                await interaction.followup.send(f"✅ С вас снята роль {role.mention}!", ephemeral=True)
            else:
                await member.add_roles(role)
                await interaction.followup.send(f"✅ Вам выдана роль {role.mention}!", ephemeral=True)

            return True

            # Вместо super().on_interaction() просто возвращаем True
        return True


class RoleButtonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Ограничения для слэш-команды
    @app_commands.guild_only()  # Команда запрещена в ЛС (только для серверов)
    @app_commands.default_permissions(administrator=True)  # Видна только администраторам сервера
    @app_commands.command(name="setup_start_verifier", description="Установить интерактивную кнопку выдачи роли")
    async def slash_setup_button(self, interaction: discord.Interaction):
        # Создаем экземпляр нашей структуры
        view = RoleLayoutView()

        # Отправляем невидимое подтверждение администратору
        await interaction.response.send_message("Панель успешно создана и установлена!", ephemeral=True)

        # Отправляем саму вечную панель в канал, где была вызвана команда
        await interaction.channel.send(view=view)

    # Регистрация вечной панели в памяти бота при каждом его включении
    @commands.Cog.listener()
    async def on_ready(self):
        # Добавляем view в глобальный трекер бота, чтобы custom_id обрабатывался всегда
        self.bot.add_view(RoleLayoutView())
        print(f"[RoleButtonCog] Вечная панель RoleLayoutView успешно зарегистрирована в менеджере!")


# Обязательная точка входа для вашего авто-сканера когов
async def setup(bot: commands.Bot):
    await bot.add_cog(RoleButtonCog(bot))
