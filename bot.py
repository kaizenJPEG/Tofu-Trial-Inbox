import discord
import os
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
MY_DIR = os.getenv('MY_DIR')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='t!', intents=intents)

@bot.event
async def on_ready():
    print("Ready!")

    for filename in os.listdir(MY_DIR):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')
            print(f"Loaded cog - {filename}")


@bot.command(description="Reload Cogs.")
@commands.is_owner()
async def reload(ctx, extension):
    await bot.reload_extension(f'cogs.{extension}')
    await ctx.send(f"Reloaded {extension}")
    print("reloaded\n\n\n")

bot.run(BOT_TOKEN)