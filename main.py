import os
from creativiousutilities import discord as discUtils
from creativiousutilities.logging import Logger
from creativiousutilities.config import YAMLConfig
from discord.commands.context import ApplicationContext
from discord.ui import Button, View
from discord.ext import commands
from interface import LoggingInterface
import discord

# @TODO: Setup new config system
import ui

"""
Documentation: https://docs.pycord.dev/en/master/
"""

if not os.path.isdir("logs/"):
    os.makedirs("logs/")

if not os.path.exists("cogs/"):
    os.makedirs("cogs/")

if not os.path.exists("cache/"):
    os.makedirs("cache/")

if not os.path.exists("storage/"):
    os.makedirs("storage/")


class CoreBot(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.config = YAMLConfig("config/default_config.yaml", "config/config.yaml").load()
        self.logger = Logger(name="Bot", debug=bool(self.config["bot"]["logging"]["debug"]), logfile=self.config["bot"]["logging"]["filename"]).getLogger()
        self.logger.info("Startup!")


    def shutdown(self):
        self.logger.info("Bot has shutdown!")

    def __del__(self):
        self.logger.warning("Bot has been garbage collected")


client = CoreBot('$')


@client.event
async def on_ready():
    client.logger.info(f"Logged into {str(client.user.name)} ({str(client.user.id)})")
    discUtils.loadAllCogs(client, "cogs/")
    activity = discord.Game(name="Message me with /help to get started")
    client.remove_command("help")
    await client.change_presence(activity=activity, status=discord.Status.online)

# @client.command(name="test")
# async def test(ctx : commands.Context):
#     """Test Command"""
#     print("Test")
#     await ctx.reply("Response")

@client.slash_command()
async def help(ctx : ApplicationContext):
    """Provides all the possible commands that can be given by the bot"""
    helpCommandObject = discUtils.HelpCommand(client)
    helpEmbed = helpCommandObject.getHelp(0)
    await ctx.respond(embed=helpEmbed)

@client.slash_command()
async def create_log_interface(ctx : ApplicationContext):
    client.logger.debug("Creating Log Interface")
    await ctx.defer()
    await ctx.delete()
    await ctx.send(view=LoggingInterface(config=client.config).create())





if client.config["bot"]["token"] != "TOKENHERE":
    client.run(client.config["bot"]["token"])
else:
    client.logger.error("Please provide a discord bot token in the sensitive/token.txt file")
