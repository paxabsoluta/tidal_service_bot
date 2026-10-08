import discord
from discord.ext import commands
from discord import ui
from discord import app_commands  # Добавляем импорт для слэш-команд

# =========================================================================
# КОНФИГУРАЦИЯ: Укажите здесь реальные ID ролей уведомлений с вашего сервера
# =========================================================================
ROLE_IDS = {
    "btn_action": 123456789012345678,  # ID роли для 📯 (Уведомления от команды)
    "btn_action_4": 123456789012345678,  # ID роли для 🎉 (Ивенты)
    "btn_action_3": 123456789012345678,  # ID роли для 🗞️ (Roleplay-Газета)
    "btn_action_2": 123456789012345678,  # ID роли для 🎥 (Медиа)
}


class RolesLayoutView(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

        container = ui.Container(
            ui.MediaGallery(
                discord.MediaGalleryItem(
                    "attachment://ChatGPT_Image_3____._2026__.__09_28_28.png",
                ),
            ),
            ui.TextDisplay("ⵈ━═════════════════════════╗◊╔═════════════════════════━ⵈ"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(
                "## Основные роли:\n"
                "➢ <@&1459994385289711830> — непосредственные руководители проекта.\n\n"
                "➢ <@&1477955071521325199> — эксперты.\n\n"
                "➢ <@&1473235427250012251> — модераторы.\n\n"
                "➢ <@&1475601409838682243> — поддержка.\n\n"
                "➢ <@&1477007491660517406> — медиа.\n\n"
                "➢ <@&1475598422798106724> — спонсоры.",
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(
                "## Получение ролей\n"
                "Нажмите на нужные реакции ниже, чтобы получать соответствующие уведомления:\n"
                ":postal_horn: — Уведомления от команды\n"
                ":tada: — Ивенты\n"
                ":newspaper2: — Roleplay-Газета\n"
                ":movie_camera: — Медиа (анонсы видео и стримов)",
            ),
        )

        btn_1 = ui.Button(style=discord.ButtonStyle.secondary, emoji="📯", custom_id="btn_action")
        btn_2 = ui.Button(style=discord.ButtonStyle.secondary, emoji="🎉", custom_id="btn_action_4")
        btn_3 = ui.Button(style=discord.ButtonStyle.secondary, emoji="🗞️", custom_id="btn_action_3")
        btn_4 = ui.Button(style=discord.ButtonStyle.secondary, emoji="🎥", custom_id="btn_action_2")

        btn_clear = ui.Button(
            style=discord.ButtonStyle.danger,
            emoji="❌",
            label="Сбросить подписки",
            custom_id="btn_clear_subscriptions"
        )

        btn_1.callback = self.handle_role_button
        btn_2.callback = self.handle_role_button
        btn_3.callback = self.handle_role_button
        btn_4.callback = self.handle_role_button
        btn_clear.callback = self.handle_clear_subscriptions

        action_row = ui.ActionRow()
        action_row.add_item(btn_1)
        action_row.add_item(btn_2)
        action_row.add_item(btn_3)
        action_row.add_item(btn_4)
        action_row.add_item(btn_clear)

        self.add_item(container)
        self.add_item(action_row)

    async def handle_role_button(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Эта кнопка работает только на сервере!", ephemeral=True)

        role_id = ROLE_IDS.get(interaction.data.get("custom_id"))
        role = interaction.guild.get_role(role_id)

        if not role:
            return await interaction.response.send_message("❌ Ошибка: Роль не найдена на сервере.", ephemeral=True)

        member = interaction.user

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"С вас снята роль подписки {role.mention}", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"Вам выдана роль подписки {role.mention}", ephemeral=True)

    async def handle_clear_subscriptions(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Эта кнопка работает только на сервере!", ephemeral=True)

        member = interaction.user
        roles_to_remove = []

        for role_id in ROLE_IDS.values():
            role = interaction.guild.get_role(role_id)
            if role and role in member.roles:
                roles_to_remove.append(role)

        if not roles_to_remove:
            return await interaction.response.send_message("У вас нет active подписок из этого меню!", ephemeral=True)

        await member.remove_roles(*roles_to_remove)
        removed_mentions = ", ".join([r.mention for r in roles_to_remove])
        await interaction.response.send_message(f"❌ Ваши подписки аннулированы. Сняты роли: {removed_mentions}",
                                                ephemeral=True)


class RoleMenuCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(RolesLayoutView())

    # Меняем префиксную команду на современную слэш-команду
    @app_commands.command(name="sendroles", description="Отправить интерактивное меню выбора ролей в текущий канал")
    # Ограничиваем доступ на уровне Discord: команду видят только администраторы
    @app_commands.default_permissions(administrator=True)
    async def send_roles_menu(self, interaction: discord.Interaction):
        """Слэш-команда для отправки панели"""
        view = RolesLayoutView()

        image_path = "./ChatGPT_Image_3____._2026__.__09_28_28.png"
        filename = "ChatGPT_Image_3____._2026__.__09_28_28.png"

        try:
            file = discord.File(image_path, filename=filename)

            # 1. Сначала отправляем саму панель прямо в канал
            await interaction.channel.send(
                view=view,
                allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False),
                files=[file]
            )

            # 2. Отвечаем на саму слэш-команду эфемерным (скрытым) сообщением,
            # чтобы у администратора не висела ошибка «Приложение не ответило»
            await interaction.response.send_message("✅ Панель выбора ролей успешно отправлена!", ephemeral=True)

        except FileNotFoundError:
            await interaction.response.send_message(f"❌ Файл изображения `{filename}` не найден в корне проекта!",
                                                    ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleMenuCog(bot))
