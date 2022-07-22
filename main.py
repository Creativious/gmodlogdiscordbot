import os
from creativiousutilities import discord as discUtils
from creativiousutilities.logging import Logger
from creativiousutilities.config import YAMLConfig
from discord.commands.context import ApplicationContext
from discord.ext import commands
import discord

# @TODO: Setup new config system

"""
Documentation: https://docs.pycord.dev/en/master/
"""

if not os.path.isdir("logs/"):
    os.makedirs("logs/")

if not os.path.exists("sensitive/"): # If the path for the sensitive files doesn't exist then create it
    os.makedirs("sensitive/")


if not os.path.exists("sensitive/token.txt"): # Ensuring the file for tokens exists, setup so github can't see it.
    with open("sensitive/token.txt", "w+") as f:
        f.write("TOKENGOESHERE")

if not os.path.exists("cogs/"):
    os.makedirs("cogs/")

token = ""
with open("sensitive/token.txt", "r") as f: # Loading bot token
    token = f.read();




class CoreBot(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.logger = Logger(name="Bot", debug=True).getLogger()
        self.logger.info("Startup!")
        self.config = YAMLConfig("config/default_config.yaml", "config/config.yaml").load()

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




if token != "TOKENGOESHERE":
    client.run(token)
else:
    client.logger.error("Please provide a discord bot token in the sensitive/token.txt file")
