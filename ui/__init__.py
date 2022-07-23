from discord.ui import Button, View
import discord
from discord import Interaction
from discord.ext import commands

class PageRightButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, emoji="➡")

class PageLeftButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, emoji="⬅")

class HomeButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, emoji="🏠", label="Home")
