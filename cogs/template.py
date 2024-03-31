import json
import unicodedata

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import create_async_engine

from modals.currency import Currency

with open("config.json") as f:
    CONFIG = json.load(f)

engine = create_async_engine(f"sqlite+aiosqlite:///{CONFIG['DATABASE']}")


class Template(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot

    def fix_unicode(self, str):
        fixed = unicodedata.normalize("NFKD", str).encode("ascii", "ignore").decode()
        return fixed


async def setup(bot: commands.Bot):
    await bot.add_cog(Template(bot))
    print(f"{__name__[5:].upper()} loaded")


async def teardown(bot: commands.Bot):
    await bot.remove_cog(Template(bot))  # type: ignore
    print(f"{__name__[5:].upper()} unloaded")
