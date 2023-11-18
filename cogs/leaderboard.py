import json
import unicodedata
from typing import List

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import create_async_engine

from modals.bank import Bank
from modals.currency import Currency

with open("config.json") as f:
    CONFIG = json.load(f)

engine = create_async_engine(f"sqlite+aiosqlite:///{CONFIG['DATABASE']}")


class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def fix_unicode(self, str):
        fixed = unicodedata.normalize("NFKD", str).encode("ascii", "ignore").decode()
        return fixed

    async def currency_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        async with engine.begin() as conn:
            if current != "":
                results = await conn.execute(
                    select(Currency.name)
                    .where(
                        Currency.name.contains(current),
                        Currency.guild_id == interaction.guild_id,
                    )
                    .limit(25)
                )
                results = results.all()
                if results is not None:
                    return [
                        app_commands.Choice(name=solution[0], value=solution[0])
                        for solution in results
                    ]
            else:
                results = await conn.execute(
                    select(Currency.name)
                    .where(Currency.guild_id == interaction.guild_id)
                    .order_by(Currency.name.asc())
                    .limit(25)
                )
                results = results.all()
                if results is not None:
                    return [
                        app_commands.Choice(name=solution[0], value=solution[0])
                        for solution in results
                    ]
        return [app_commands.Choice(name="None", value="None") for _ in range(0, 1)]

    @app_commands.command(
        name="leaderboard",
        description="Shows the top 25 holders of the specified currency.",
    )
    @app_commands.autocomplete(currency_name=currency_name_autocomplete)
    async def leaderboard(self, interaction: discord.Interaction, currency_name: str):
        leaderboard_embed = discord.Embed(
            color=discord.Color.random(),
        )
        if interaction.guild is not None and interaction.guild.icon is not None:
            leaderboard_embed.set_thumbnail(url=interaction.guild.icon.url)
        leaderboard_embed.title = f"🥉 🥈 🥇 Leaderboard for {currency_name} 🥇 🥈 🥉"
        async with engine.begin() as conn:
            currency_id = await conn.execute(
                select(Currency.id).filter_by(
                    name=currency_name, guild_id=interaction.guild_id
                )
            )
            currency_id = currency_id.first()
            top_25_list = await conn.execute(
                select(Bank.user_id, Bank.amount)
                .filter_by(guild_id=interaction.guild_id, currency_id=currency_id[0])  # type: ignore
                .order_by(Bank.amount.desc())
                .limit(25)
            )
            top_25_list = top_25_list.all()
        await engine.dispose(close=True)
        if len(top_25_list) == 0:
            leaderboard_embed.description = "No one has that currency yet."
            return await interaction.response.send_message(embed=leaderboard_embed)
        else:
            if interaction.guild is not None:
                for entry in top_25_list:
                    currency_amount = entry[1]
                    member = interaction.guild.get_member(entry[0])
                    if member is not None:
                        leaderboard_embed.add_field(
                            name=member.display_name,
                            value=f"{currency_amount:,}",
                            inline=False,
                        )
                    else:
                        leaderboard_embed.add_field(
                            name="Member Left",
                            value=f"{currency_amount:,}",
                            inline=False,
                        )
                leaderboard_embed.set_footer(text=f"Top {len(top_25_list)} members.")
                return await interaction.response.send_message(embed=leaderboard_embed)

        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboard(bot))
    print(f"{__name__[5:].upper()} loaded")


async def teardown(bot: commands.Bot):
    await bot.remove_cog(Leaderboard(bot))  # type: ignore
    print(f"{__name__[5:].upper()} unloaded")
