import unicodedata

import discord
import docker
from discord import app_commands
from discord.ext import commands


class Utils(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot

    def fix_unicode(self, str):
        fixed = unicodedata.normalize("NFKD", str).encode("ascii", "ignore").decode()
        return fixed

    def check_perms(interaction: discord.Interaction):  # type: ignore
        return interaction.user.id == 908252159148175380

    # This currently doesn't work. #
    # @app_commands.command(
    #     name="restart",
    #     description="Restarts the Docker container.  You probably can't run this.",
    # )
    # @app_commands.check(check_perms)
    # async def restart_bot(self, interaction: discord.Interaction):
    #     await interaction.response.defer(ephemeral=True)
    #     docker_client = docker.DockerClient(base_url="unix://var/run/docker.sock")
    #     container = docker_client.containers.get("bot.CurrencyAndDiceBot")
    #     await interaction.followup.send(
    #         content=f"Restarting.  Will be back shortly!", ephemeral=True
    #     )
    #     with open("reboot_chan.txt", "w") as f:
    #         f.write(str(interaction.channel.id))
    #     container.restart()

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        return await interaction.followup.send(
            f"{error}",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Utils(bot))
    print(f"{__name__[5:].upper()} loaded")


async def teardown(bot: commands.Bot):
    await bot.remove_cog(Utils(bot))  # type: ignore
    print(f"{__name__[5:].upper()} unloaded")
