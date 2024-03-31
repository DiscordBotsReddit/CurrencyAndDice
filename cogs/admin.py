import json
import unicodedata
from typing import List, Literal, Optional

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


class Admin(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot

    def fix_unicode(self, str):
        fixed = unicodedata.normalize("NFKD", str).encode("ascii", "ignore").decode()
        return fixed

    async def find_cmd(self, bot: commands.Bot, cmd: str, group: Optional[str] = None):
        if group is None:
            command = discord.utils.find(
                lambda c: c.name.lower() == cmd.lower(),
                await bot.tree.fetch_commands(),
            )
            return command
        else:
            cmd_group = discord.utils.find(
                lambda cg: cg.name.lower() == group.lower(),
                await bot.tree.fetch_commands(),
            )
            for child in cmd_group.options:  # type: ignore
                if child.name.lower() == cmd.lower():
                    return child
        return "No command found."

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

    @app_commands.command(name="create", description="Creates a new currency.")
    @app_commands.describe(currency_name="The name for your new currency.")
    async def create_currency(
        self, interaction: discord.Interaction, currency_name: str
    ):
        await interaction.response.defer(ephemeral=True)
        currency_embed = discord.Embed()
        if interaction.guild is not None and interaction.guild.icon is not None:
            currency_embed.set_thumbnail(url=interaction.guild.icon.url)
        currency_name = self.fix_unicode(currency_name)
        async with engine.begin() as conn:
            exists = await conn.execute(
                select(Currency.name)
                .filter_by(guild_id=interaction.guild_id)
                .filter(Currency.name.ilike(currency_name))
            )
            exists = exists.one_or_none()
        await engine.dispose(close=True)
        if exists is not None:
            currency_embed.color = discord.Color.brand_red()
            currency_embed.title = "❌ Currency Create **FAILED**"
            currency_embed.description = (
                f"You already have a currency called `{exists[0]}`."
            )
            return await interaction.followup.send(
                embed=currency_embed,
                ephemeral=True
            )
        else:
            currency_embed.color = discord.Color.brand_green()
            currency_embed.title = "✅ Currency Create **SUCCESSFUL**"
            currency_embed.description = (
                f"A new currency `{currency_name}` has been created!"
            )
            async with engine.begin() as conn:
                await conn.execute(
                    insert(Currency).values(
                        name=currency_name, guild_id=interaction.guild_id
                    )
                )
                await conn.commit()
            await engine.dispose(close=True)
            return await interaction.followup.send(
                embed=currency_embed, ephemeral=True
            )

    @app_commands.command(name="destroy", description="Deletes an existing currency.")
    @app_commands.describe(currency_name="The name for your existing currency.")
    @app_commands.describe(
        double_check="Select 'Yes' if you are really sure you want to do this."
    )
    @app_commands.autocomplete(currency_name=currency_name_autocomplete)
    async def delete_currency(
        self,
        interaction: discord.Interaction,
        currency_name: str,
        double_check: Literal["No", "Yes"],
    ):
        await interaction.response.defer()
        destroy_embed = discord.Embed()
        if interaction.guild is not None and interaction.guild.icon is not None:
            destroy_embed.set_thumbnail(url=interaction.guild.icon.url)
        if double_check == "No":
            destroy_embed.color = discord.Color.brand_red()
            destroy_embed.title = "❌ Destroy Currency **FAILED**"
            destroy_embed.description = f"Failed to delete `{currency_name}` due to not selecting **Yes** for the double check parameter."
            return await interaction.followup.send(
                embed=destroy_embed, ephemeral=True
            )
        else:
            async with engine.begin() as conn:
                currency_id = await conn.execute(
                    select(Currency.id).filter_by(
                        name=currency_name,
                        guild_id=interaction.guild_id,
                    )
                )
                currency_id = currency_id.first()
                await conn.execute(
                    delete(Currency).filter_by(
                        name=currency_name,
                        guild_id=interaction.guild_id,
                    )
                )
                await conn.execute(delete(Bank).filter_by(currency_id=currency_id[0]))  # type: ignore
                await conn.commit()
            await engine.dispose(close=True)
            destroy_embed.color = discord.Color.brand_green()
            destroy_embed.title = "✅ Destroy Currency **SUCCESSFUL**"
            destroy_embed.description = (
                f"The currency `{currency_name}` has been deleted."
            )
            return await interaction.followup.send(
                embed=destroy_embed
            )

    @app_commands.command(
        name="print_gold", description="Gives currency to selected member."
    )
    @app_commands.autocomplete(currency_name=currency_name_autocomplete)
    @app_commands.describe(member="The member you want to give currency to.")
    @app_commands.describe(currency_name="The name of the currency you want to give.")
    @app_commands.describe(amount="The amount of currency to give.")
    async def print_currency(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        currency_name: str,
        amount: int,
    ):
        await interaction.response.defer()
        print_currency_embed = discord.Embed(
            color=discord.Color.brand_green(),
            title="✅ Print Currency **SUCCESSFUL**",
            description=f"`{amount:,}` `{currency_name}` has been created in {member.mention}'s bag!",
        )
        if interaction.guild is not None and interaction.guild.icon is not None:
            print_currency_embed.set_thumbnail(url=interaction.guild.icon.url)
        if amount <= 0:
            return await interaction.followup.send(
                content="Please set `amount` to a value higher than 0.",
                ephemeral=True
            )
        async with engine.begin() as conn:
            currency_id = await conn.execute(
                select(Currency.id).filter_by(
                    name=currency_name, guild_id=interaction.guild_id
                )
            )
            currency_id = currency_id.first()
            user_bank = await conn.execute(
                select(Bank.amount).filter_by(
                    currency_id=currency_id[0],  # type: ignore
                    user_id=member.id,
                    guild_id=interaction.guild_id,
                )
            )
            user_bank = user_bank.one_or_none()
            if user_bank is None:
                await conn.execute(
                    insert(Bank).values(
                        user_id=member.id,
                        guild_id=interaction.guild_id,
                        currency_id=currency_id[0],  # type: ignore
                        amount=amount,
                    )
                )
                await conn.commit()
            else:
                new_amt = user_bank[0] + amount
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
        await interaction.followup.send(
            content=f"{member.mention}", embed=print_currency_embed
        )
        await engine.dispose(close=True)

    @app_commands.command(
        name="remove_gold", description="Removes currency from a member."
    )
    @app_commands.autocomplete(currency_name=currency_name_autocomplete)
    @app_commands.describe(member="The member you want to remove currency from.")
    @app_commands.describe(currency_name="The name of the currency you want to remove.")
    @app_commands.describe(amount="The amount of currency to remove.")
    async def remove_currency(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        currency_name: str,
        amount: int,
    ):
        await interaction.response.defer()
        remove_currency_embed = discord.Embed()
        if interaction.guild is not None and interaction.guild.icon is not None:
            remove_currency_embed.set_thumbnail(url=interaction.guild.icon.url)
        if amount <= 0:
            remove_currency_embed.color = discord.Color.brand_red()
            remove_currency_embed.title = "❌ Remove Currency **FAILED**"
            remove_currency_embed.description = (
                "Please set `amount` to a value higher than 0."
            )
            return await interaction.followup.send(
                embed=remove_currency_embed,
                ephemeral=True
            )
        async with engine.begin() as conn:
            currency_id = await conn.execute(
                select(Currency.id).filter_by(
                    name=currency_name, guild_id=interaction.guild_id
                )
            )
            currency_id = currency_id.first()
            current_amount = await conn.execute(
                select(Bank.amount).filter_by(
                    user_id=member.id,
                    guild_id=interaction.guild_id,
                    currency_id=currency_id[0],  # type: ignore
                )
            )
            current_amount = current_amount.one_or_none()
            if current_amount is None:
                remove_currency_embed.color = discord.Color.brand_red()
                remove_currency_embed.title = "❌ Remove Currency **FAILED**"
                remove_currency_embed.description = f"Could not remove `{currency_name}` currency, because {member.mention} has none."
                await engine.dispose(close=True)
                return await interaction.followup.send(
                    embed=remove_currency_embed, ephemeral=True
                )
            else:
                set_to_zero = False
                new_amt = current_amount[0] - amount
                if new_amt < 0:
                    new_amt = 0
                    set_to_zero = True
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
                remove_currency_embed.color = discord.Color.brand_green()
                remove_currency_embed.title = "✅ Remove Currency **SUCCESSFUL**"
                remove_currency_embed.description = f"{amount:,} `{currency_name}` has been removed from the {member.mention}."
                if set_to_zero:
                    remove_currency_embed.description = f"{member.mention} did not have enough `{currency_name}` to remove `{amount:,}`.\n\nThey were set to **0** instead."
                await engine.dispose(close=True)
                return await interaction.followup.send(
                    content=f"{member.mention}", embed=remove_currency_embed
                )

    @app_commands.command(
        name="set_dice", description="Set the win condition for the dice game."
    )
    @app_commands.describe(win_amt="The number members must get below to win dice.")
    async def set_dice_win(self, interaction: discord.Interaction, win_amt: int):
        await interaction.response.defer()
        set_dice_embed = discord.Embed()
        if interaction.guild is not None and interaction.guild.icon is not None:
            set_dice_embed.set_thumbnail(url=interaction.guild.icon.url)
        if win_amt <= 0:
            set_dice_embed.color = discord.Color.brand_red()
            set_dice_embed.title = "❌ Set Dice **FAILED**"
            set_dice_embed.description = (
                "Please set a win condition number greater than 0."
            )
            return await interaction.followup.send(
                embed=set_dice_embed, ephemeral=True
            )
        else:
            async with engine.begin() as conn:
                current_win = await conn.execute(
                    select(Settings.dice_win).filter_by(guild_id=interaction.guild_id)
                )
                current_win = current_win.first()
                if current_win is None:
                    # no settings found - insert
                    await conn.execute(
                        insert(Settings).values(
                            guild_id=interaction.guild_id, dice_win=win_amt
                        )
                    )
                    await conn.commit()
                else:
                    # settings found - update
                    await conn.execute(
                        update(Settings)
                        .filter_by(guild_id=interaction.guild_id)
                        .values(dice_win=win_amt)
                    )
                    await conn.commit()
                dice_cmd = await self.find_cmd(self.bot, cmd="dice")
                set_dice_embed.color = discord.Color.brand_green()
                set_dice_embed.title = "✅ Set Dice **SUCCESSFUL**"
                set_dice_embed.description = f"From now, members win only when they get `1-{win_amt}` from {dice_cmd.mention}."  # type: ignore
                await interaction.followup.send(embed=set_dice_embed)

    @app_commands.command(
        name="set_limits",
        description="Set the limits on the amount members can bet on dice.",
    )
    async def set_dice_limits(
        self,
        interaction: discord.Interaction,
        min_bet: Optional[int],
        max_bet: Optional[int],
    ):
        await interaction.response.defer()
        dice_limit_embed = discord.Embed(
            title="✅ Dice Limits Updated **SUCCESSFUL**",
            color=discord.Color.brand_green(),
        )
        if min_bet is not None and max_bet is not None and min_bet > max_bet:
            dice_limit_embed.title = "❌ Dice Limits Update **FAILED**"
            dice_limit_embed.color = discord.Color.brand_red()
            dice_limit_embed.description = (
                "You must set `min_bet` greater than `max_bet`."
            )
            return await interaction.followup.send(
                embed=dice_limit_embed, ephemeral=True
            )
        if min_bet is None and max_bet is None:
            dice_limit_embed.title = "❌ Dice Limits Update **FAILED**"
            dice_limit_embed.color = discord.Color.brand_red()
            dice_limit_embed.description = (
                "You must set either the `min_bet` or the `max_bet`."
            )
            return await interaction.followup.send(
                embed=dice_limit_embed, ephemeral=True
            )
        if min_bet is not None:
            async with engine.begin() as conn:
                current_min = await conn.execute(
                    select(Settings.min_bet).filter_by(guild_id=interaction.guild_id)
                )
                current_min = current_min.one_or_none()
                if current_min is None:
                    await conn.execute(
                        insert(Settings).values(
                            guild_id=interaction.guild_id, min_bet=min_bet
                        )
                    )
                    await conn.commit()
                else:
                    await conn.execute(
                        update(Settings)
                        .filter_by(guild_id=interaction.guild_id)
                        .values(min_bet=min_bet)
                    )
                    await conn.commit()
                await engine.dispose(close=True)
                dice_limit_embed.add_field(
                    name="",
                    value=f"Dice minimum bet set to `{min_bet:,}`.",
                    inline=False,
                )
        if max_bet is not None:
            async with engine.begin() as conn:
                current_min = await conn.execute(
                    select(Settings.max_bet).filter_by(guild_id=interaction.guild_id)
                )
                current_min = current_min.one_or_none()
                if current_min is None:
                    await conn.execute(
                        insert(Settings).values(
                            guild_id=interaction.guild_id, max_bet=max_bet
                        )
                    )
                    await conn.commit()
                else:
                    await conn.execute(
                        update(Settings)
                        .filter_by(guild_id=interaction.guild_id)
                        .values(max_bet=max_bet)
                    )
                    await conn.commit()
                await engine.dispose(close=True)
                dice_limit_embed.add_field(
                    name="",
                    value=f"Dice maximum bet set to `{max_bet:,}`.",
                    inline=False,
                )
        return await interaction.followup.send(embed=dice_limit_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
    print(f"{__name__[5:].upper()} loaded")


async def teardown(bot: commands.Bot):
    await bot.remove_cog(Admin(bot))  # type: ignore
    print(f"{__name__[5:].upper()} unloaded")
