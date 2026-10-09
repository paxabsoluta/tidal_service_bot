import discord
from discord import ui
from discord.ext import commands

ROLE_ID = 1459994385281454326  # Ваш ID роли


class RoleLayoutView(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)  # По-прежнему вечная панель

        self.add_item(
            ui.Container(
                ui.Section(
                    ui.TextDisplay("## Нажмите на кнопку, чтобы начать"),
                    accessory=ui.Button( # noqa
                        style=discord.ButtonStyle.success,
                        label="СТАРТ",
                        custom_id="btn_give_role",
                    ),  # type: ignore
                ),
            ),
        )

    # Исправленный и защищенный обработчик взаимодействия
    async def on_interaction(self, interaction: discord.Interaction) -> bool:
        # Проверяем наш custom_id
        if interaction.data.get("custom_id") == "btn_give_role":

            # 1. МГНОВЕННО говорим Дискорду, что мы приняли запрос и думаем.
            # ephemeral=True означает, что последующий ответ (followup) будет виден только нажавшему.
            await interaction.response.defer(ephemeral=True)

            guild = interaction.guild
            member = interaction.user

            if not guild or not isinstance(member, discord.Member):
                return True

            role = guild.get_role(ROLE_ID)
            if not role:
                # Так как мы использовали defer(), теперь отвечаем через followup.send
                await interaction.followup.send("Ошибка: Роль не найдена на сервере.", ephemeral=True)
                return True

            # 2. Выполняем «тяжелую» операцию смены ролей
            if role in member.roles:
                await member.remove_roles(role)
                await interaction.followup.send(f"С вас снята роль {role.mention}!", ephemeral=True)
            else:
                await member.add_roles(role)
                await interaction.followup.send(f"Вам выдана роль {role.mention}!", ephemeral=True)

            return True  # Сообщаем системе, что взаимодействие полностью обработано

        # Обязательно передаем другие взаимодействия (если они появятся в будущем) наверх
        return await super().on_interaction(interaction)
