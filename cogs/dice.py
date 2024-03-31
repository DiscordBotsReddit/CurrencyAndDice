import json
import random
import unicodedata
from typing import List

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import create_async_engine

from modals.bank import Bank
from modals.currency import Currency
from modals.settings import Settings

with open("config.json") as f:
    CONFIG = json.load(f)

engine = create_async_engine(f"sqlite+aiosqlite:///{CONFIG['DATABASE']}")


class DiceGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def fix_unicode(self, str):
        fixed = unicodedata.normalize("NFKD", str).encode("ascii", "ignore").decode()
        return fixed

    async def dice_bet_min_autocomplete(
        self, interaction: discord.Interaction, current: int
    ) -> List[app_commands.Choice[int]]:
        if current == "":
            async with engine.begin() as conn:
                min_bet = await conn.execute(
                    select(Settings.min_bet, Settings.max_bet).filter_by(
                        guild_id=interaction.guild_id
                    )
                )
                min_bet = min_bet.all()
            if len(min_bet) == 0:
                return [
                    app_commands.Choice(name="No minimum bet set.", value=0)
                    for _ in range(0, 1)
                ]
            else:
                return [
                    app_commands.Choice(
                        name=str(f"Minimum bet = {min_bet[0][0]:,}"),
                        value=min_bet[0][0],
                    ),
                    app_commands.Choice(
                        name=str(f"Maximum bet = {min_bet[0][1]:,}"),
                        value=min_bet[0][1],
                    ),
                ]
        else:
            async with engine.begin() as conn:
                min_bet = await conn.execute(
                    select(Settings.min_bet, Settings.max_bet).filter_by(
                        guild_id=interaction.guild_id
                    )
                )
                min_bet = min_bet.all()
            if len(min_bet) == 0:
                return [
                    app_commands.Choice(name="No minimum", value=0) for _ in range(0, 1)
                ]
            else:
                if int(current) < min_bet[0][0]:
                    return [
                        app_commands.Choice(
                            name=str(f"Minimum bet = {min_bet[0][0]:,}"),
                            value=min_bet[0][0],
                        ),
                    ]
                if int(current) > min_bet[0][1]:
                    return [
                        app_commands.Choice(
                            name=str(f"Maximum bet = {min_bet[0][1]:,}"),
                            value=min_bet[0][1],
                        ),
                    ]
                else:
                    return [app_commands.Choice(name=str(current), value=int(current))]

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
        name="dice", description="Bet a currency for a chance to win double back!"
    )
    @app_commands.autocomplete(currency_name=currency_name_autocomplete)
    @app_commands.describe(currency_name="The currency you want to use to bet.")
    @app_commands.describe(bet_amount="The amount of currency you want to bet.")
    @app_commands.autocomplete(bet_amount=dice_bet_min_autocomplete)  # type: ignore
    async def dice_game(
        self, interaction: discord.Interaction, currency_name: str, bet_amount: int
    ):
        await interaction.response.defer()
        dice_game_embed = discord.Embed()
        if interaction.guild is not None and interaction.guild.icon is not None:
            dice_game_embed.set_thumbnail(url=interaction.guild.icon.url)
        if bet_amount <= 0:
            dice_game_embed.color = discord.Color.brand_red()
            dice_game_embed.title = "❌ Dice Game ❌ **FAILED**"
            dice_game_embed.description = (
                "Please set `bet_amount` to a value higher than 0."
            )
            await engine.dispose(close=True)
            return await interaction.followup.send(
                embed=dice_game_embed, ephemeral=True
            )
        async with engine.begin() as conn:
            bet_limits = await conn.execute(
                select(Settings.min_bet, Settings.max_bet).filter_by(
                    guild_id=interaction.guild_id
                )
            )
            bet_limits = bet_limits.one_or_none()
            if bet_limits is None:
                dice_game_embed.color = discord.Color.brand_red()
                dice_game_embed.title = "❌ Dice Game ❌ **FAILED**"
                dice_game_embed.description = (
                    "Your server admins have not set the winning roll required yet."
                )
                await engine.dispose(close=True)
                return await interaction.followup.send(embed=dice_game_embed)
            elif bet_amount < bet_limits[0] or bet_amount > bet_limits[1]:
                dice_game_embed.color = discord.Color.brand_red()
                dice_game_embed.title = "❌ Dice Game ❌ **FAILED**"
                dice_game_embed.description = f"Your server admins have set a minimum bet of `{bet_limits[0]:,}` and a maximum bet of `{bet_limits[1]:,}`."
                await engine.dispose(close=True)
                return await interaction.followup.send(
                    embed=dice_game_embed, ephemeral=True
                )
            currency_id = await conn.execute(
                select(Currency.id).filter_by(
                    name=currency_name, guild_id=interaction.guild_id
                )
            )
            currency_id = currency_id.first()
            currency_amt = await conn.execute(
                select(Bank.amount).filter_by(
                    user_id=interaction.user.id,
                    guild_id=interaction.guild_id,
                    currency_id=currency_id[0],  # type: ignore
                )
            )
            currency_amt = currency_amt.one_or_none()
            if currency_amt is None:
                dice_game_embed.color = discord.Color.brand_red()
                dice_game_embed.title = "❌ Dice Game ❌ **FAILED**"
                dice_game_embed.description = (
                    f"You do not have any of `{currency_name}` currency to bet."
                )
                await engine.dispose(close=True)
                return await interaction.followup.send(
                    embed=dice_game_embed, ephemeral=True
                )
            elif currency_amt[0] < bet_amount:
                dice_game_embed.color = discord.Color.brand_red()
                dice_game_embed.title = "❌ Dice Game ❌ **FAILED**"
                dice_game_embed.description = f"You do not have enough of `{currency_name}` currency to bet `{bet_amount}`."
                await engine.dispose(close=True)
                return await interaction.followup.send(
                    embed=dice_game_embed, ephemeral=True
                )
            else:
                winning_number = await conn.execute(
                    select(Settings.dice_win).filter_by(guild_id=interaction.guild_id)
                )
                winning_number = winning_number.one_or_none()
                if winning_number is None:
                    dice_game_embed.color = discord.Color.brand_red()
                    dice_game_embed.title = "❌ Dice Game ❌ **FAILED**"
                    dice_game_embed.description = (
                        "Your server admins have not set the winning roll required yet."
                    )
                    await engine.dispose(close=True)
                    return await interaction.followup.send(embed=dice_game_embed)
                else:
                    dice_role = random.randrange(0, 101)
                    if dice_role <= winning_number[0]:
                        amt_to_add = bet_amount
                        new_amt = currency_amt[0] + amt_to_add
                        dice_game_embed.color = discord.Color.brand_green()
                        dice_game_embed.title = "🎲 Dice Game 🎲 **WON**"
                        dice_game_embed.description = f"You wagered `{bet_amount:,}` of `{currency_name}` and your roll was `{dice_role}`, which is a winning number.\n\nYou gained `{amt_to_add:,}` of `{currency_name}`!\nNow you have `{new_amt:,}` of `{currency_name}`."
                        dice_game_embed.set_footer(
                            text=f"Winning numbers are less than or equal to {winning_number[0]}."
                        )
                        await conn.execute(
                            update(Bank)
                            .filter_by(
                                user_id=interaction.user.id,
                                guild_id=interaction.guild_id,
                                currency_id=currency_id[0],  # type: ignore
                            )
                            .values(amount=new_amt)
                        )
                        await conn.commit()
                        await engine.dispose(close=True)
                        return await interaction.followup.send(embed=dice_game_embed)
                    else:
                        amt_to_remove = bet_amount
                        new_amt = currency_amt[0] - amt_to_remove
                        dice_game_embed.color = discord.Color.brand_red()
                        dice_game_embed.title = "🎲 Dice Game 🎲 **LOST**"
                        dice_game_embed.description = f"You wagered `{bet_amount:,}` of `{currency_name}` and your roll was `{dice_role}`, which is a losing number.\nTry again!\n\nYou lost `{bet_amount:,}` of `{currency_name}`.\nNow you have `{new_amt:,}` of `{currency_name}`."
                        dice_game_embed.set_footer(
                            text=f"Winning numbers are less than or equal to {winning_number[0]}."
                        )
                        await conn.execute(
                            update(Bank)
                            .filter_by(
                                user_id=interaction.user.id,
                                guild_id=interaction.guild_id,
                                currency_id=currency_id[0],  # type: ignore
                            )
                            .values(amount=new_amt)
                        )
                        await conn.commit()
                        await engine.dispose(close=True)
                        return await interaction.followup.send(embed=dice_game_embed)

    @app_commands.command(
        name="roll", description="Roll a random number from 1 to 100."
    )
    async def roll_random(self, interaction: discord.Interaction):
        rand_roll = random.randrange(0, 100)
        return await interaction.response.send_message(
            f"{interaction.user.mention}, you got `{rand_roll}`!"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(DiceGame(bot))
    print(f"{__name__[5:].upper()} loaded")


async def teardown(bot: commands.Bot):
    await bot.remove_cog(DiceGame(bot))  # type: ignore
    print(f"{__name__[5:].upper()} unloaded")
