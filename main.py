import os
from creativiousutilities import discord as discUtils
from creativiousutilities.logging import Logger
from creativiousutilities.config import YAMLConfig
from discord.commands.context import ApplicationContext
from creativiousutilities.discord.messages import MessageHandler
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

if not os.path.exists("indexes/"):
    os.makedirs("indexes/")


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

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True

client = CoreBot('$', intents=intents)

@client.event
async def on_ready():
    client.logger.info(f"Logged into {str(client.user.name)} ({str(client.user.id)})")
    discUtils.loadAllCogs(client, "cogs/")
    interfaceMessageHandler = MessageHandler("storage/interface_messages.json")

    interface_message_ids =[]
    try:
        interface_message_ids = [messageID for messageID in interfaceMessageHandler.getMessages()["interfaces"]]
    except KeyError:
        client.logger.debug("Interfaces doesn't exist")
    for messageID in interface_message_ids:
        try:
            message = await client.get_channel(int(interfaceMessageHandler.getMessages()['interfaces'][str(messageID)])).fetch_message(int(messageID))
            await message.edit(view=LoggingInterface(config=client.config).create_from_message(message), embed=discord.Embed(colour=discord.Colour.blurple(), title="Vapor Networks DarkRP Log Interface",
                                           description="""
                    Please use the buttons down below to navigate the interface
                    """))
        except(Exception) as e:
            messages = interfaceMessageHandler.getMessages()
            messages['interfaces'].pop(str(messageID))
            interfaceMessageHandler.saveMessages(messages)
            client.logger.debug("Message has been deleted for view")
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
    message = await ctx.respond(embed=helpEmbed)
    await message.delete(delay=120)

@client.slash_command()
async def create_log_interface(ctx : ApplicationContext):
    client.logger.debug("Creating Log Interface")
    await ctx.defer()
    await ctx.delete()
    view : View = View()
    view.add_item(Button(label="Loading interface...", style=discord.ButtonStyle.secondary, disabled=True))
    message = await ctx.send(view=view)
    await message.edit(content=None, view=LoggingInterface(config=client.config).create_from_message(message), embed=discord.Embed(colour=discord.Colour.blurple(), title="Vapor Networks DarkRP Log Interface",
                                           description="""
                    Please use the buttons down below to navigate the interface
                    """))


@client.command()
async def temp_create_interface(ctx):
    view: View = View()
    view.add_item(Button(label="Loading interface...", style=discord.ButtonStyle.secondary, disabled=True))
    message = await ctx.send(view=view)
    await message.edit(content=None, view=LoggingInterface(config=client.config).create_from_message(message), embed=discord.Embed(colour=discord.Colour.blurple(), title="Vapor Networks DarkRP Log Interface",
                                           description="""
                    Please use the buttons down below to navigate the interface
                    """))


if client.config["bot"]["token"] != "TOKENHERE":
    client.run(client.config["bot"]["token"])
else:
    client.logger.error("Please provide a discord bot token in the sensitive/token.txt file")
