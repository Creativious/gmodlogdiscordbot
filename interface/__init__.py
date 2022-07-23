import discord

from creativiousutilities.discord.ui import HomeButton, PageRightButton, PageLeftButton
from discord.ui import Button, View, Select, Modal, Item
from discord import Embed, ButtonStyle
from discord import Interaction, SelectOption
from creativiousutilities.sql import MySQL
import time
import json
from caching import Cache, CacheType, CacheSystem

import mysql.connector


class LoggingInterface:
    def __init__(self, config):
        self.config = config
        self.sql : mysql.connector.MySQLConnection = mysql.connector.connect(
            host=self.config["mysql"]["host"],
            user=self.config["mysql"]["user"],
            database=self.config["mysql"]["database"],
            password=self.config["mysql"]["password"]
        )
        if self.sql is None:
            raise "SQL IS NONE"
        self.sql_sync = self.SQLSync(self.sql, self.config)
        self.view = View()
        self.buttons = {}
        self.selectMenus = {}
        self.pages = self.__Pages()
        self.current_page = self.pages.home

    def __del__(self):
        self.sql.close()

    class SQLSync:
        def __init__(self, sql: mysql.connector.MySQLConnection, config: dict):
            self.config = config
            self.sql = sql
            self.caching_system = CacheSystem(int(self.config["cache"]["delay"]), self.config["cache"]["cache folder"])
            self.first_times = {"loggingModuleCategories": False}

        def getLoggingModuleCategories(self):
            cache_name = self.config["mysql"]["tables"]["gas_logging_module_categories"]
            cache_type = CacheType.OneTime
            cache = self.caching_system.createCache(cache_name, cache_type)
            def resetCache():
                cache.wipe_all_entries()
                cursor = self.sql.cursor()
                query = f"""SELECT id, name FROM {self.config["mysql"]["tables"]["gas_logging_module_categories"]}"""
                cursor.execute(query)
                cursor_fetchall = cursor.fetchall()
                cursor.close()
                for entry in cursor_fetchall:
                    cache.new_entry(str(entry[0]), str(entry[1]))
                    cache.new_entry(str(entry[1]), entry[0])
                cache.reset_created_time()
                return cache

            if self.first_times["loggingModuleCategories"] is False:
                resetCache()
                self.first_times["loggingModuleCategories"] = True
            else:
                if cache.check_if_delay_passed():
                    resetCache()
            self.caching_system.updateCache(cache_name, cache)
            return cache.get_data()

        # @TODO: Enable grabbing all modules



    def create(self):
        self.createButton("homeButton", row=1, button=HomeButton(), callback=self.callback_home_button)
        self.createButton("logsButton", Button(style=ButtonStyle.primary, label="Logs"), row=1, callback=self.callback_logs_button)
        return self.view

    def deleteButton(self, buttonName: str):
        self.view.remove_item(self.buttons[buttonName])
        self.buttons.pop(buttonName)

    def clearToDefault(self):
        default_buttons = [
            "homeButton",
            "logsButton"
        ]
        buttons = [button for button in self.buttons]
        selectMenus = [selectMenu for selectMenu in self.selectMenus]
        for button in buttons:
            if button not in default_buttons:
                self.deleteButton(button)
        for selectMenu in selectMenus:
            self.deleteSelectMenu(selectMenu)

    def createButton(self, buttonID: str, button : Button, callback = None, row = 2):
        button.row = row

        if callback is not None:
            button.callback = callback
        button.custom_id = buttonID
        self.buttons[buttonID] = button
        self.view.add_item(button)
        return button

    def createSelectMenu(self, selectMenuID: str, options: list, callback = None, row = 2, min_values=1, max_values=1, placeholder: str = None, description: str = "Description"):

        selectMenu = Select(min_values=min_values, max_values=max_values, row=row, custom_id=selectMenuID, placeholder="Select...", options=[SelectOption(label=option, description=description) for option in options])
        selectMenu.callback = callback
        if placeholder is not None:
            selectMenu.placeholder = placeholder
        self.selectMenus[selectMenuID] = selectMenu
        self.view.add_item(self.selectMenus[selectMenuID])
        return self.selectMenus[selectMenuID]

    def deleteSelectMenu(self, selectMenuID: str):
        self.view.remove_item(self.selectMenus[selectMenuID])
        self.selectMenus.pop(selectMenuID)

    async def callback_home_button(self, interaction : discord.Interaction):
        self.clearToDefault()
        await interaction.response.edit_message(view=self.view)

    async def callback_logs_button(self, interaction : discord.Interaction):
        self.clearToDefault()
        self.createButton("openSortByMenuButton", Button(style=ButtonStyle.secondary, label="Sort Logs"), row=2, callback=self.callback_open_sort_by_menu_button)
        await interaction.response.edit_message(view=self.view)

    async def callback_fail_confirm_sort_selection_button(self, interaction: discord.Interaction):
        await interaction.response.defer()



    async def callback_open_sort_by_menu_button(self, interaction: discord.Interaction):
        # self.clearToDefault()
        # self.createButton("confirmSortSelectionButton", Button(style=ButtonStyle.green, label="Confirm Selection"), row=4, callback=self.callback_fail_confirm_sort_selection_button)
        # self.createButton("cancelButton", Button(style=ButtonStyle.red, label="Cancel"), row=4, callback=self.callback_logs_button)
        logging_module_categories = self.sql_sync.getLoggingModuleCategories()
        options = ["Any"]
        for category in logging_module_categories:
            if len(category) > 1:
                options.append(category)
        # self.createSelectMenu("loggingModuleCategoriesSelectMenu", row=2, options=options, callback=self.callback_logging_module_categories_select_menu, placeholder="Module Category")

        await interaction.response.edit_message(view=self.SortingModuleViewFactory(
            [SelectOption(label=option, description="Logging Module Category") for option in options],)(self))
        # self.createSelectMenu("sortLoggingModulesSelectMenu", row=3)

    async def callback_logging_module_categories_select_menu(self, interaction: discord.Interaction):

        await interaction.response.defer()

    def SortingModuleViewFactory(self, options_1):
        # @TODO: Change this so that it shows the modules instead of the Categories, "module [category]" sort them by id number of category then by id number of module
        class SortingView(View):
            def __init__(self, parent:LoggingInterface, *items: Item):
                super().__init__(*items)
                self.parent: LoggingInterface = parent

            @discord.ui.button(label="Home", style=ButtonStyle.primary, emoji="🏠", row=1)
            async def home_callback(self, button: Button, interaction: Interaction):
                await self.parent.callback_home_button(interaction)

            @discord.ui.button(label="Logs", style=ButtonStyle.primary, row=1)
            async def logs_callback(self, button: Button, interaction: Interaction):
                await self.parent.callback_logs_button(interaction)


            @discord.ui.select(row=2, placeholder="Any Logging Module Category", options=options_1)
            async def select_logging_module_category_callback(self, select: Select, interaction: Interaction):

                await interaction.response.defer()

        return SortingView


    class __Pages:
        def __init__(self):
            self.home = "Home"

