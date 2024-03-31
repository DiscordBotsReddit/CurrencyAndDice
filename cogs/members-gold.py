import json
import unicodedata
from typing import List, Optional

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


class MembersGold(commands.Cog):
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

    @app_commands.command(name="give_gold", description="Give gold to another member.")
    @app_commands.autocomplete(currency_name=currency_name_autocomplete)
    @app_commands.describe(member="The member you want to give gold to.")
    @app_commands.describe(currency_name="The name of the currency to give.")
    @app_commands.describe(amount="The amount of currency to give.")
    async def give_gold(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        currency_name: str,
        amount: int,
    ):
        await interaction.response.defer()
        give_gold_embed = discord.Embed()
        if interaction.guild is not None and interaction.guild.icon is not None:
            give_gold_embed.set_thumbnail(url=interaction.guild.icon.url)
        if amount <= 0:
            give_gold_embed.color = discord.Color.brand_red()
            give_gold_embed.title = "❌ Give Gold **FAILED**"
            give_gold_embed.description = (
                "Please set `amount` to a value higher than 0."
            )
            return await interaction.followup.send(
                embed=give_gold_embed,
                ephemeral=True
            )
        if member == interaction.user:
            give_gold_embed.color = discord.Color.brand_red()
            give_gold_embed.title = "❌ Give Gold **FAILED**"
            give_gold_embed.description = "You cannot send youself currency."
            return await interaction.followup.send(
                embed=give_gold_embed,
                ephemeral=True
            )
        async with engine.begin() as conn:
            currency_id = await conn.execute(
                select(Currency.id).filter_by(
                    name=currency_name, guild_id=interaction.guild_id
                )
            )
            currency_id = currency_id.first()
            from_amount = await conn.execute(
                select(Bank.amount).filter_by(
                    user_id=interaction.user.id,
                    guild_id=interaction.guild_id,
                    currency_id=currency_id[0],  # type: ignore
                )
            )
            from_amount = from_amount.one_or_none()
            if from_amount is None:
                give_gold_embed.color = discord.Color.brand_red()
                give_gold_embed.title = "❌ Give Gold **FAILED**"
                give_gold_embed.description = (
                    f"You cannot send `{currency_name}`, because you have none."
                )
                await engine.dispose(close=True)
                return await interaction.followup.send(
                    embed=give_gold_embed,
                    ephemeral=True
                )
            elif from_amount[0] < amount:
                give_gold_embed.color = discord.Color.brand_red()
                give_gold_embed.title = "❌ Give Gold **FAILED**"
                give_gold_embed.description = f"You cannot `{amount:,}` of `{currency_name}`, beacuse you only have `{from_amount[0]:,}`."
                await engine.dispose(close=True)
                return await interaction.followup.send(
                    embed=give_gold_embed,
                    ephemeral=True
                )
            else:
                to_amount = await conn.execute(
                    select(Bank.amount).filter_by(
                        user_id=member.id,
                        guild_id=interaction.guild_id,
                        currency_id=currency_id[0],  # type: ignore
                    )
                )
                to_amount = to_amount.one_or_none()
                if to_amount is None:
                    new_from_amt = from_amount[0] - amount
                    await conn.execute(
                        update(Bank)
                        .filter_by(
                            user_id=interaction.user.id,
                            guild_id=interaction.guild_id,
                            currency_id=currency_id[0],  # type: ignore
                        )
                        .values(amount=new_from_amt)
                    )
                    await conn.execute(
                        insert(Bank).values(
                            user_id=member.id,
                            guild_id=interaction.guild_id,
                            currency_id=currency_id[0],  # type: ignore
                            amount=amount,
                        )
                    )
                    await conn.commit()
                    await engine.dispose(close=True)
                else:
                    new_amt = to_amount[0] + amount
                    new_from_amt = from_amount[0] - amount
                    await conn.execute(
                        update(Bank)
                        .filter_by(
                            user_id=interaction.user.id,
                            guild_id=interaction.guild_id,
                            currency_id=currency_id[0],  # type: ignore
                        )
                        .values(amount=new_from_amt)
                    )
                    await conn.execute(
                        update(Bank)
                        .filter_by(
                            user_id=member.id,
                            guild_id=interaction.guild_id,
                            currency_id=currency_id[0],  # type: ignore
                        )
                        .values(amount=new_amt)
                    )
                    await conn.commit()
                    await engine.dispose(close=True)
                give_gold_embed.color = discord.Color.green()
                give_gold_embed.title = "✅ Give Gold **SUCCESSFUL**"
                give_gold_embed.description = f"{interaction.user.mention} gave `{amount}` of `{currency_name}` to {member.mention}!"
                return await interaction.followup.send(
                    content=f"{interaction.user.mention} -> {member.mention}",
                    embed=give_gold_embed
                )

    @app_commands.command(
        name="balance",
        description="Shows how much of each currency the member has. (Highest 25 only)",
    )
    @app_commands.describe(
        member="The member to check the balance of.  Leave blank to check yours."
    )
    async def balance(
        self, interaction: discord.Interaction, member: Optional[discord.Member]
    ):
        await interaction.response.defer()
        balance_embed = discord.Embed(color=discord.Color.random())
        if interaction.guild is not None and interaction.guild.icon is not None:
            balance_embed.set_thumbnail(url=interaction.guild.icon.url)
        if member is None:
            member = interaction.user  # type: ignore
        async with engine.begin() as conn:
            currencies_amounts = await conn.execute(
                select(Bank.amount, Bank.currency_id)
                .filter_by(
                    guild_id=interaction.guild_id, user_id=member.id  # type: ignore
                )
                .order_by(Bank.amount.desc())
                .limit(25)
            )
            currencies_amounts = currencies_amounts.all()
            if len(currencies_amounts) == 0:
                balance_embed.color = discord.Color.brand_red()
                balance_embed.title = "❌ Balance **FAILED**"
                balance_embed.description = f"{member.mention} has no currencies!"  # type: ignore
                await engine.dispose(close=True)
                return await interaction.followup.send(
                    embed=balance_embed, ephemeral=True
                )
            else:
                balance_embed.title = f"Balances for {member.display_name}"  # type: ignore
                for cur in currencies_amounts:
                    currency_name = await conn.execute(
                        select(Currency.name).filter_by(id=cur[1])
                    )
                    currency_name = currency_name.first()
                    balance_embed.add_field(
                        name=currency_name[0], value=f"{cur[0]:,}", inline=False  # type: ignore
                    )
                await engine.dispose(close=True)
                return await interaction.followup.send(embed=balance_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MembersGold(bot))
    print(f"{__name__[5:].upper()} loaded")


async def teardown(bot: commands.Bot):
    await bot.remove_cog(MembersGold(bot))  # type: ignore
    print(f"{__name__[5:].upper()} unloaded")
