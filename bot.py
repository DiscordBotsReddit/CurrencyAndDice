import json
import logging
import os
from typing import Literal, Optional

import discord
from discord.ext import commands
from discord.ext.commands import ExtensionAlreadyLoaded
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modals.bank import Bank
from modals.currency import Currency
from modals.settings import Settings

with open("config.json") as f:
    CONFIG = json.load(f)

engine = create_async_engine(f"sqlite+aiosqlite:///{CONFIG['DATABASE']}")
SessionLocal = async_sessionmaker(engine)


async def db_init():
    if not os.path.exists(CONFIG["DATABASE"]):
        print("Database not found.  Initalizing...")
        with open(CONFIG["DATABASE"], "w") as f:
            f.write("")
        async with engine.begin() as conn:
            await conn.run_sync(Currency.metadata.create_all)
            await conn.run_sync(Settings.metadata.create_all)
            await conn.run_sync(Bank.metadata.create_all)
        await engine.dispose(close=True)


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=CONFIG["PREFIX"], intents=intents)


@bot.event
async def on_ready():
    await db_init()
    for subdir, _, files in os.walk("cogs"):
        files = [
            file for file in files if file.endswith(".py") and "template" not in file
        ]
        for file in files:
            if len(subdir.split("cogs\\")) >= 2:
                try:
                    sub = subdir.split("cogs\\")[1]
                    await bot.load_extension(f"cogs.{sub}.{file[:-3]}")
                except ExtensionAlreadyLoaded:
                    sub = subdir.split("cogs\\")[1]
                    await bot.reload_extension(f"cogs.{sub}.{file[:-3]}")
            else:
                try:
                    await bot.load_extension(f"{subdir}.{file[:-3]}")
                except ExtensionAlreadyLoaded:
                    await bot.reload_extension(f"{subdir}.{file[:-3]}")
    print(f"Logged in as {bot.user}")


@bot.command()
@commands.is_owner()
async def reloadall(ctx: commands.Context):
    await ctx.message.delete()
    for subdir, _, files in os.walk("cogs"):
        files = [
            file for file in files if file.endswith(".py") and "template" not in file
        ]
        for file in files:
            if len(subdir.split("cogs\\")) >= 2:
                try:
                    sub = subdir.split("cogs\\")[1]
                    await bot.load_extension(f"cogs.{sub}.{file[:-3]}")
                    await ctx.send(f"Loaded `cogs.{sub}.{file[:-3]}`")
                except ExtensionAlreadyLoaded:
                    sub = subdir.split("cogs\\")[1]
                    await bot.reload_extension(f"cogs.{sub}.{file[:-3]}")
                    await ctx.send(f"Reloaded `cogs.{sub}.{file[:-3]}`")
            else:
                try:
                    await bot.load_extension(f"{subdir}.{file[:-3]}")
                    await ctx.send(f"Loaded `{subdir}.{file[:-3]}`")
                except ExtensionAlreadyLoaded:
                    await bot.reload_extension(f"{subdir}.{file[:-3]}")
                    await ctx.send(f"Reloaded `{subdir}.{file[:-3]}`")


@bot.command()
@commands.is_owner()
async def load(ctx: commands.Context, extension: str):
    await ctx.message.delete()
    try:
        await bot.load_extension(f"cogs.{extension}")
        await ctx.send(f"Loaded `{extension.upper()}`")
    except Exception as e:
        await ctx.send(f"Error loading `{extension.upper()}`\n{e}")


# https://about.abstractumbra.dev/discord.py/2023/01/29/sync-command-example.html
@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(
    ctx: commands.Context,
    guilds: commands.Greedy[discord.Object],
    spec: Optional[Literal["~", "*", "^", "x"]] = None,
) -> None:
    await ctx.reply("Sync request received.")
    if not guilds:
        if spec == "~":  # sync all to current guild
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":  # sync global to current guild
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":  # remove commands sync'd to current guild
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        elif spec == "x":  # remove all global sync'd commands
            ctx.bot.tree.clear_commands(guild=None)
            await ctx.bot.tree.sync()
            await ctx.send("Cleared all global commands.")
            return
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return

    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")


bot.run(CONFIG["TOKEN"], log_level=logging.WARN)
