import os
from creativiousutilities import discord as discUtils
from creativiousutilities.logging import Logger
from discord.commands.context import ApplicationContext
from discord.ext import commands
import discord


if not os.path.isdir("logs/"):
    os.makedirs("logs/")

if not os.path.exists("sensitive/"): # If the path for the sensitive files doesn't exist then create it
    os.makedirs("sensitive/")


if not os.path.exists("sensitive/token.txt"): # Ensuring the file for tokens exists, setup so github can't see it.
    with open("sensitive/token.txt", "w+") as f:
        f.write("TOKENGOESHERE")




class CoreBot(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.logger = Logger(name="Bot", debug=True).getLogger()
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

@client.slash_command()
async def help(ctx : ApplicationContext):
    """Is your general help command!"""
    # @TODO: Create the help command
    await ctx.respond("Testing")
    print([c.name for c in list(client.commands)])
    pass

@client.command(name="test")
async def test(ctx : commands.Context):
    await ctx.reply("Response")