import discord
import steamid_converter.Converter

from creativiousutilities.discord.ui import HomeButton, PageRightButton, PageLeftButton
from discord.ui import Button, View, Select, Modal, Item
from discord import Embed, ButtonStyle
from discord import Interaction, SelectOption
from discord.ext import pages
import math
from creativiousutilities.sql import MySQL
from creativiousutilities.discord.messages import MessageHandler
import time
import datetime
import steamid_converter.Converter as SteamIDConverter
from asyncio import wait_for, gather, wait
import json
from caching import Cache, CacheType, CacheSystem

import mysql.connector

class CustomView(View):
    def __init__(self, client, *items: Item):
        super().__init__(*items, timeout=None)

    async def on_timeout(self):
        print("Timed out")


class LoggingInterface:
    def __init__(self, config, sql_sync, caching_system, client):
        # @TODO: Add Interface persistence
        self.config = config
        self.interface_id = 0
        self.caching_system = caching_system
        self.sql_sync: InterfaceSQLSync = sql_sync
        self.view = CustomView(client=client)

        self.buttons = {}
        self.default_embed = discord.Embed(colour=discord.Colour.blurple(), title="Vapor Networks DarkRP Log Interface",
                                           description="""
                    Please use the buttons down below to navigate the interface
                    """)
        self.select_menus = {}
        self.pages = {}
        self.current_page = 0
        self.total_pages = 0
        self.modals = {}
        self.interface_message_handler = MessageHandler("storage/interface_messages.json")

    def __del__(self):
        self.sql.close()


    def create(self):
        self.view.clear_items()
        self.createButton("homeButton", row=1, button=Button(style=discord.ButtonStyle.primary, emoji="🏠", label="Home", custom_id='home-button'), callback=self.callback_home_button)
        self.createButton("logsButton", Button(style=ButtonStyle.primary, label="Logs", custom_id='logs-button'), row=1, callback=self.callback_logs_button)
        return self.view

    def create_from_message(self, message : discord.Message):
        self.view = self.view.from_message(message)
        try:
            messages = self.interface_message_handler.getMessages()["interfaces"][str(message.id)] = str(message.channel.id)
        except KeyError:
            messages = self.interface_message_handler.getMessages()
            messages["interfaces"] = {}
            messages["interfaces"][str(message.id)] = str(message.channel.id)
        finally:
            self.interface_message_handler.saveMessages(messages)
        return self.create()

    def deleteButton(self, buttonName: str):
        self.view.remove_item(self.buttons[buttonName])
        self.buttons.pop(buttonName)

    def clearToDefault(self):
        default_buttons = [
            "homeButton",
            "logsButton"
        ]
        buttons = [button for button in self.buttons]
        self.pages = {}
        self.current_page = 0
        selectMenus = [selectMenu for selectMenu in self.select_menus]
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


    def deleteSelectMenu(self, selectMenuID: str):
        self.view.remove_item(self.select_menus[selectMenuID])
        self.select_menus.pop(selectMenuID)

    async def callback_home_button(self, interaction : discord.Interaction):
        self.clearToDefault()
        await interaction.response.edit_message(view=self.view, embed=self.default_embed)

    async def callback_logs_button(self, interaction : discord.Interaction):
        self.clearToDefault()
        self.createButton("openbLogsButton", Button(style=ButtonStyle.secondary, label="bLogs"), row=2, callback=self.callback_bLogs_button)
        await interaction.response.edit_message(view=self.view, embed=self.default_embed)

    async def callback_log_module_picked(self, module: str, interaction : Interaction):
        self.view = self.create()


    def getLoggingModuleCategoriesSelectOptions(self, default_category: str = None):
        categories = self.sql_sync.getLoggingModuleCategories()
        options = []
        for x in range(1, len(categories) + 1):
            option = SelectOption(
                label=str(categories[str(x)]['name'])
            )
            if default_category == categories[str(x)]['name']:
                option.default = True
            options.append(option)
        return options
    def getLoggingModulesSelectOptions(self, category: str, default_category: str = None):
        modules = self.sql_sync.getLoggingModules()
        options = []
        for x in range(1, len(modules) + 1):
            if modules[str(x)]['category_name'] == category:
                option = SelectOption(
                    label=str(modules[str(x)]['name']),
                    description=category
                )
                if default_category == modules[str(x)]['name']:
                    option.default = True
                options.append(option)
        return options

    async def callback_confirm_selection_button(self, interaction: Interaction):
        self.sql_sync.firstTimeSetups() # Ensuring everything is up to date
        module_name = self.select_menus['module-select-menu'].values[0]
        self.clearToDefault()
        self.createButton("loading_button", Button(label="Loading...", disabled=True, style=ButtonStyle.gray), row=2)
        await interaction.response.edit_message(view=self.view)
        modules = self.sql_sync.getLoggingModules()
        module_id = None
        category_id = None
        for module in modules:
            if modules[str(module)]['name'] == module_name:
                module_id = modules[str(module)]['id']
                category_id = modules[str(module)]['category_id']
                category_name = modules[str(module)]['category_name']
                break
        if module_id is None:
            raise "Module somehow does not exist"
        if category_id is None:
            raise "Module category somehow doesn't exist"
        self.clearToDefault()
        index_cache = self.caching_system.getCache('log_index_cache')
        index_data = index_cache.get_data()
        all_the_logs: dict = index_data['categories'][str(category_id)]['modules'][str(module_id)]['logs']
        sorted_logs = [all_the_logs[str(log_key)] for log_key in all_the_logs]
        def sort_key(e):
            return e['timestamp']
        sorted_logs.sort(key=sort_key)
        log_count = len(sorted_logs)
        embed = self.default_embed.copy()
        embed.title = f"bLogs Log Search | Category: {category_name} | Module: {module_name}"
        embed.colour = discord.Colour.green()

        def generatePages():
            players = self.sql_sync.getPlayers()
            logs = self.sql_sync.getLogs()
            classes = self.sql_sync.getLoggingClasses()
            pages = {}
            i = 0
            page = 1
            page_embed = embed.copy()
            page_embed.description = ""
            presetup = True
            for log_hint_dict in sorted_logs:
                i += 1
                log_id = log_hint_dict['log_id']
                log = logs[str(log_id)]
                time_stamp = datetime.datetime.fromtimestamp(log['timestamp'])
                line = f"[{str(log_id)}] {time_stamp}   "
                if i > 10:
                    pages[str(page)] = {"embed": page_embed}
                    page_embed = embed.copy()
                    page_embed.description = ""
                    page += 1
                    i = 1
                if module_id == 56:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    main_player_nick = players[str(main_player_id)]['rpname']
                    chat_said = '"' + str(log['module_specific_info']['chat_said']) + '"'
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) said {chat_said}"
                    line += string
                elif module_id == 14:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    original_name = '"' + log['module_specific_info']['original_name'] + '"'
                    new_name = '"' + log['module_specific_info']['new_name'] + '"'
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) changed their name from {original_name} to {new_name}"
                    line += string
                elif module_id == 18:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    command_ran = '"**' + log['module_specific_info']['command_ran'] + '**"'
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) ran command {command_ran}"
                    line += string
                elif module_id == 17:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    cheque_amount = '"**' + "{:,}".format(log['module_specific_info']['cheque_amount']) + '**"'
                    log_phrase = log['log_phrase']
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)})"
                    if log_phrase == "darkrp_cheque_dropped":
                        secondary_player_id = log['secondary_player']
                        secondary_player_name = players[str(secondary_player_id)]['name']
                        string += f" dropped a cheque of {cheque_amount} for [{secondary_player_name}](http://steamcommunity.com/profiles/{str(secondary_player_id)})"
                    elif log_phrase == "darkrp_cheque_picked_up":
                        secondary_player_id = log['secondary_player']
                        secondary_player_name = players[str(secondary_player_id)]['name']
                        string += f" cashed a cheque of {cheque_amount} for [{secondary_player_name}](http://steamcommunity.com/profiles/{str(secondary_player_id)})"
                    line += string
                elif module_id == 42:
                    try:
                        main_player_id = log['main_player']
                        main_player_name = players[str(main_player_id)]['name']
                    except:
                        main_player_name = "Unknown"
                        main_player_id = None
                    if log['module_specific_info']['type'] == "connected_from_country":
                        connection_from = classes[str(log['module_specific_info']['country'])]['class_name']
                        if connection_from == "United States":
                            connection_from = 'the "**' + connection_from + '**"'
                        else:
                            connection_from = '"**' + connection_from + '**"'
                        if main_player_id is None:
                            string = f"{main_player_name} is connecting from {connection_from}"
                        else:
                            string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) is connecting from {connection_from}"
                    else:
                        if main_player_id is None:
                            string = f"{main_player_name} finished connecting"
                        else:
                            string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) finished connecting"
                    line += string
                elif module_id == 36:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    prop_spawned = '"**' + log['module_specific_info']['prop_spawned'] + '**"'
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) spawned prop {prop_spawned}"
                    line += string
                elif module_id == 34:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    tool = '"**' + log['module_specific_info']['tool'] + '**"'
                    used_on = '"**' + log['module_specific_info']['used_on'] + '**"'
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) used toolgun tool {tool} on {used_on}"
                    line += string
                elif module_id == 52:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    dmg_amount = '"**' + str(log['module_specific_info']['damage_taken']) + '**"'
                    dmg_type = '"**' + str(log['module_specific_info']['damage_type']) + '**"'
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) took damage {dmg_amount} of type {dmg_type}"
                    line += string
                elif module_id == 3:
                    line += log['deepstorage_log']
                elif module_id == 43:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) disconnected from the server"
                    line += string
                elif module_id == 44:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) respawned"
                    line += string
                elif module_id == 54:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) died"
                    line += string
                elif module_id == 45:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    picked_up_item = '"**' + log['module_specific_info']['picked_up_item'] + '**"'
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) picked up {picked_up_item}"
                    line += string
                elif module_id == 58:
                    main_player_id = log['main_player']
                    main_player_name = players[str(main_player_id)]['name']
                    secondary_player_id = log['secondary_player']
                    secondary_player_name = players[str(secondary_player_id)]['name']
                    string = f"[{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)}) changed the admin notes for [{secondary_player_name}](http://steamcommunity.com/profiles/{str(secondary_player_id)})"
                    line += string
                else:
                    try:
                        if log['main_player'] is not None:
                            has_main_player = True
                        else:
                            has_main_player = False
                    except KeyError:
                        has_main_player = False
                    try:
                        if log['secondary_player'] is not None:
                            has_secondary_player = True
                        else:
                            has_secondary_player = False
                    except KeyError:
                        has_secondary_player = False
                    try:
                        if log['log_phrase'] is not None:
                            has_log_phrase = True
                        else:
                            has_log_phrase = False
                    except KeyError:
                        has_log_phrase = False
                    string = f""
                    if has_main_player:
                        main_player_id = log['main_player']
                        main_player_name = players[str(main_player_id)]['name']
                        string += f"main player: [{main_player_name}](http://steamcommunity.com/profiles/{str(main_player_id)})"
                    if has_log_phrase:
                        log_phrase = '"**' + log['log_phrase'] + '**"'
                        string += f"   log phrase: {log_phrase}"
                    if has_secondary_player:
                        secondary_player_id = log['secondary_player']
                        secondary_player_name = players[str(secondary_player_id)]['name']
                        string += f"   secondary player: [{secondary_player_name}](http://steamcommunity.com/profiles/{str(secondary_player_id)})"
                    line += string
                    presetup = False
                if not presetup:
                    page_embed.set_footer(text=f"**This module does not have an pre-configured output!**\nDebug: module_id = {module_id}")
                page_embed.description += line + "\n\n"

            pages[str(page)] = {"embed": page_embed}
            return pages

        async def callback_next_page(sub_interaction: Interaction):
            self.current_page += 1
            self.buttons['blogs_current_page'].label = f"Page: {self.current_page}/{self.total_pages}"
            if self.current_page > 1:
                self.buttons['blogs_back_button'].disabled = False
                self.buttons['blogs_beginning_button'].disabled = False
            else:
                self.buttons['blogs_back_button'].disabled = True
                self.buttons['blogs_beginning_button'].disabled = True
            if self.current_page == self.total_pages:
                self.buttons["blogs_next_button"].disabled = True
                self.buttons["blogs_last_button"].disabled = True
            else:
                self.buttons["blogs_next_button"].disabled = False
                self.buttons["blogs_last_button"].disabled = False
            await sub_interaction.response.edit_message(view=self.view, embed=self.pages[str(self.current_page)]['embed'])

        async def callback_back_page(sub_interaction: Interaction):
            self.current_page -= 1
            self.buttons['blogs_current_page'].label = f"Page: {self.current_page}/{self.total_pages}"
            if self.current_page > 1:
                self.buttons['blogs_back_button'].disabled = False
                self.buttons['blogs_beginning_button'].disabled = False
            else:
                self.buttons['blogs_back_button'].disabled = True
                self.buttons['blogs_beginning_button'].disabled = True
            if self.current_page == self.total_pages:
                self.buttons["blogs_next_button"].disabled = True
                self.buttons["blogs_last_button"].disabled = True
            else:
                self.buttons["blogs_next_button"].disabled = False
                self.buttons["blogs_last_button"].disabled = False
            await sub_interaction.response.edit_message(view=self.view,
                                                        embed=self.pages[str(self.current_page)]['embed'])

        async def callback_beginning_page(sub_interaction: Interaction):
            self.current_page = 1
            self.buttons['blogs_current_page'].label = f"Page: {self.current_page}/{self.total_pages}"
            if self.current_page > 1:
                self.buttons['blogs_back_button'].disabled = False
                self.buttons['blogs_beginning_button'].disabled = False
            else:
                self.buttons['blogs_back_button'].disabled = True
                self.buttons['blogs_beginning_button'].disabled = True
            if self.current_page == self.total_pages:
                self.buttons["blogs_next_button"].disabled = True
                self.buttons["blogs_last_button"].disabled = True
            else:
                self.buttons["blogs_next_button"].disabled = False
                self.buttons["blogs_last_button"].disabled = False
            await sub_interaction.response.edit_message(view=self.view,
                                                        embed=self.pages[str(self.current_page)]['embed'])

        async def callback_last_page(sub_interaction: Interaction):
            self.current_page = self.total_pages
            self.buttons['blogs_current_page'].label = f"Page: {self.current_page}/{self.total_pages}"
            if self.current_page > 1:
                self.buttons['blogs_back_button'].disabled = False
                self.buttons['blogs_beginning_button'].disabled = False
            else:
                self.buttons['blogs_back_button'].disabled = True
                self.buttons['blogs_beginning_button'].disabled = True
            if self.current_page == self.total_pages:
                self.buttons["blogs_next_button"].disabled = True
                self.buttons["blogs_last_button"].disabled = True
            else:
                self.buttons["blogs_next_button"].disabled = False
                self.buttons["blogs_last_button"].disabled = False
            await sub_interaction.response.edit_message(view=self.view,
                                                        embed=self.pages[str(self.current_page)]['embed'])
        async def callback_view_specific_log(sub_interaction: Interaction):
            async def modal_callback(modal_interaction: Interaction):
                modal: Modal = self.modals['view-log-modal']
                log_id = modal.children[0].value
                logs = self.sql_sync.getLogs()
                try:
                    log_id = int(log_id)
                except:
                    await modal_interaction.response.send_message(content="Please use numbers only when typing in the log id", delete_after=2)
                try:
                    log = logs[str(log_id)]
                except KeyError:
                    await modal_interaction.response.send_message(
                        content="No log exists by that id", delete_after=2)

            modal = Modal(title="Enter Log ID to view", custom_id="view-log-modal")
            modal.callback = modal_callback
            modal.add_item(discord.ui.InputText(label="Log ID", style=discord.InputTextStyle.short))
            self.modals['view-log-modal'] = modal
            await sub_interaction.response.send_modal(modal)

        if log_count > 0:
            if log_count > 10:
                self.total_pages = round(log_count/10) if log_count % 10 == 0 else round(math.floor(log_count/10) + 1)
                self.current_page = 1
                self.createButton("blogs_beginning_button", button=Button(label="|<<", style=ButtonStyle.gray, disabled=True), row=2, callback=callback_beginning_page)
                self.createButton("blogs_back_button", button=Button(label="<", style=ButtonStyle.green, disabled=True), row=2, callback=callback_back_page)
                self.createButton("blogs_current_page", button=Button(label=f"Page: {self.current_page}/{self.total_pages}", disabled=True, style=ButtonStyle.blurple), row=2)
                self.createButton("blogs_next_button", button=Button(label=">", style=ButtonStyle.green), row=2, callback=callback_next_page)
                self.createButton("blogs_last_button", button=Button(label=">>|", style=ButtonStyle.gray), row=2, callback=callback_last_page)
                # self.createButton("blogs_view_log_button", button=Button(label="View Specific Log", style=ButtonStyle.blurple), row=3, callback=callback_view_specific_log)
                self.pages = generatePages()
                embed = self.pages[str(self.current_page)]['embed']
            else:
                self.pages = generatePages()
                embed = self.pages['1']['embed']
        else:
            embed.colour = discord.Colour.red()
            embed.description = "No logs available for this module"
        message = await interaction.message.edit(view=self.view, embed=embed)

    async def callback_bLogs_button(self, interaction: discord.Interaction):
        self.clearToDefault()
        category_select_menu = Select(custom_id='category-select-menu', placeholder='Logging Category', options=self.getLoggingModuleCategoriesSelectOptions(), row=2)
        category_select_menu.callback = self.callback_category_select_menu
        module_select_menu = Select(custom_id='module-select-menu', placeholder='Logging Module', disabled=True, options=self.getLoggingModuleCategoriesSelectOptions(), row=3)
        module_select_menu.callback = self.callback_modules_select_menu
        self.select_menus['category-select-menu'] = category_select_menu
        self.select_menus['module-select-menu'] = module_select_menu
        self.view.add_item(category_select_menu)
        self.view.add_item(module_select_menu)
        self.createButton('confirm-button', Button(label="Confirm Search", style=ButtonStyle.green, disabled=True), row=4, callback=self.callback_confirm_selection_button)
        await interaction.response.edit_message(view=self.view)

    async def callback_modules_select_menu(self, interaction: Interaction):
        self.buttons['confirm-button'].disabled = True
        self.select_menus['category-select-menu'].placeholder = "Loading..."
        self.select_menus['module-select-menu'].placeholder = "Loading..."
        self.select_menus['category-select-menu'].options = [SelectOption(label='Loading...', default=True)]
        self.select_menus['module-select-menu'].options = [SelectOption(label='Loading...', default=True)]
        self.select_menus['category-select-menu'].disabled = True
        self.select_menus['module-select-menu'].disabled = True
        await interaction.response.edit_message(view=self.view)

        for child in self.view.children:
            if child == self.select_menus['module-select-menu']:
                self.select_menus['module-select-menu'] = child
                self.select_menus['category-select-menu'].placeholder = "Logging Category"
                self.select_menus['module-select-menu'].placeholder = "Logging Module"
                self.select_menus['module-select-menu'].disabled = False
                self.select_menus['category-select-menu'].disabled = False
                self.select_menus['category-select-menu'].options = self.getLoggingModuleCategoriesSelectOptions(
                    self.select_menus['category-select-menu'].values[0])
                self.select_menus['module-select-menu'].options = self.getLoggingModulesSelectOptions(self.select_menus['category-select-menu'].values[0], self.select_menus['module-select-menu'].values[0])
        self.buttons['confirm-button'].disabled = False
        await interaction.message.edit(view=self.view)


    async def callback_category_select_menu(self, interaction: Interaction):
        self.buttons['confirm-button'].disabled = True
        self.select_menus['category-select-menu'].placeholder = "Loading..."
        self.select_menus['module-select-menu'].placeholder = "Loading..."
        self.select_menus['category-select-menu'].options = [SelectOption(label='Loading...', default=True)]
        self.select_menus['module-select-menu'].options = [SelectOption(label='Loading...', default=True)]
        self.select_menus['category-select-menu'].disabled = True
        self.select_menus['module-select-menu'].disabled = True
        await interaction.response.edit_message(view=self.view)

        for child in self.view.children:
            if child == self.select_menus['category-select-menu']:
                self.select_menus['category-select-menu'] = child
                self.select_menus['category-select-menu'].placeholder = "Logging Category"
                self.select_menus['module-select-menu'].placeholder = "Logging Module"
                self.select_menus['category-select-menu'].disabled = False
                self.select_menus['category-select-menu'].options = self.getLoggingModuleCategoriesSelectOptions(self.select_menus['category-select-menu'].values[0])
                self.select_menus['module-select-menu'].disabled = False
                self.select_menus['module-select-menu'].options = self.getLoggingModulesSelectOptions(self.select_menus['category-select-menu'].values[0])
        await interaction.message.edit(view=self.view)

class InterfaceSQLSync:
    def __init__(self, sql: mysql.connector.MySQLConnection, config: dict, caching_system: CacheSystem):
        self.config = config
        self.sql = sql
        self.caching_system = caching_system
        start_time = time.time()
        self.firstTimeSetups()
        end_time = time.time()
        print("Interface SQL Sync Startup time: " + str(round(end_time - start_time)))

    def firstTimeSetups(self):
        self.__firstTimeGetLoggingModuleCategories()
        self.__firstTimeGetLoggingModules()
        self.__firstTimePlayers()
        self.__firstTimeGetLoggingClasses()
        self.__firstTimeGetIndexCache()
        self.__firstTimeGetLogs()

    def __firstTimeGetLoggingModuleCategories(self):
        cache_name = self.config["mysql"]["tables"]["gas_logging_module_categories"]
        cache_type = CacheType.OneTime
        cache = self.caching_system.createCache(cache_name, cache_type)
        try:
            highest_id = cache.getSpecialEntry('highest_id')
        except KeyError:
            highest_id = 0
            cache.addSpecialEntry('highest_id', highest_id)
        cursor = self.sql.cursor()
        query = f"""SELECT id, name FROM {self.config["mysql"]["tables"]["gas_logging_module_categories"]} WHERE id > {str(highest_id)}"""
        cursor.execute(query)
        cursor_fetchall = cursor.fetchall()
        cursor.close()
        if len(cursor_fetchall) > 0:
            id = highest_id
            for entry in cursor_fetchall:
                data = {"id": entry[0], "name": entry[1]}
                if int(entry[0]) > id:
                    id = int(entry[0])
                cache.new_entry(str(entry[0]), data)
            cache.reset_created_time()
            cache.addSpecialEntry('highest_id', id)
            self.caching_system.updateCache(cache_name, cache)

    def __firstTimeGetLoggingModules(self):
        cache_name = self.config["mysql"]["tables"]["gas_logging_modules"]
        cache_type = CacheType.OneTime
        cache = self.caching_system.createCache(cache_name, cache_type)
        try:
            highest_id = cache.getSpecialEntry('highest_id')
        except KeyError:
            highest_id = 0
            cache.addSpecialEntry('highest_id', highest_id)

        cursor = self.sql.cursor()
        categories = self.getLoggingModuleCategories()
        query = f"""SELECT id, category_id, name FROM {self.config["mysql"]["tables"]["gas_logging_modules"]} WHERE id > {str(highest_id)}"""
        cursor.execute(query)
        cursor_fetchall = cursor.fetchall()
        cursor.close()
        if len(cursor_fetchall) > 0:
            id = highest_id
            for entry in cursor_fetchall:
                data = {"id": entry[0], "name": entry[2], "category_id": entry[1],
                        "category_name": categories[str(entry[1])]['name']}
                if int(entry[0]) > id:
                    id = int(entry[0])
                cache.new_entry(str(entry[0]), data)
            cache.reset_created_time()
            cache.addSpecialEntry('highest_id', id)
            self.caching_system.updateCache(cache_name, cache)

    def __firstTimePlayers(self):
        cache_name = "Players"
        cache_type = CacheType.OneTime
        cache = self.caching_system.createCache(cache_name, cache_type)
        data: dict = cache.get_data()
        new_data = data.copy()
        cache_keys = [int(key) for key in data]
        # Cache keys are steamid64
        cursor = self.sql.cursor()
        darkrp_player = self.config['mysql']['tables']['darkrp_player']
        darkrp_levels = self.config['mysql']['tables']['darkrp_levels']
        player_information = self.config['mysql']['tables']['player_information']
        sam_players = self.config['mysql']['tables']['sam_players']
        gas_offline_player_data = self.config['mysql']['tables']['gas_offline_player_data']
        darkrp_serverplayer = self.config['mysql']['tables']['darkrp_serverplayer']
        playerinformation_query = f"""SELECT uid, steamid FROM {player_information}{" WHERE " if len(cache_keys) > 0 else ""}{" AND ".join([f"uid != {int(uid)}" for uid in cache_keys])}"""
        cursor.execute(playerinformation_query)
        playerinformation_data = cursor.fetchall()
        darkrp_serverplayer_query = f"""SELECT uid FROM {darkrp_serverplayer}"""
        cursor.execute(darkrp_serverplayer_query)
        darkrp_serverplayer_data = cursor.fetchall()
        online_players = [str(player[0]) for player in darkrp_serverplayer_data] # steamid64
        for entry in playerinformation_data:
            new_data[str(entry[0])] = {"steamid64": entry[0], "steamid": str(entry[1])}
        sam_players_query = f"""SELECT id, steamid, name, rank, first_join, last_join, play_time FROM {sam_players}"""
        cursor.execute(sam_players_query)
        sam_players_data = cursor.fetchall()
        players_to_be_updated = [] # steamid64
        players_to_not_update = []
        for entry in sam_players_data:

            steamid64 = SteamIDConverter.to_steamID64(str(entry[1]))
            if str(steamid64) in data:
                if int(data[str(steamid64)]["last_join"]) < int(entry[5]) or str(steamid64) in online_players:
                    players_to_be_updated.append(str(steamid64))
                    new_data[str(steamid64)]['last_join'] = int(entry[5])
                    new_data[str(steamid64)]['play_time'] = int(entry[6]) # In seconds
                    new_data[str(steamid64)]['name'] = str(entry[2])
                    new_data[str(steamid64)]['rank'] = entry[3]

                else:
                    players_to_not_update.append(str(steamid64))
            else:
                players_to_be_updated.append(str(steamid64))
                new_data[str(steamid64)]['first_join'] = int(entry[4])
                new_data[str(steamid64)]['last_join'] = int(entry[5])
                new_data[str(steamid64)]['play_time'] = int(entry[6])  # In seconds
                new_data[str(steamid64)]['name'] = str(entry[2])
                new_data[str(steamid64)]['rank'] = entry[3]
                new_data[str(steamid64)]['sam_id'] = entry[0]

        if len(players_to_be_updated) > 0:
            cache.reset_created_time()
            darkrp_player_query = f"""SELECT uid, rpname, wallet FROM {darkrp_player}{" WHERE " if len(players_to_not_update) > 0 else ""}{" AND ".join([f"uid != {int(steamid64)}" for steamid64 in players_to_not_update])}"""
            cursor.execute(darkrp_player_query)
            darkrp_player_data = cursor.fetchall()
            for entry in darkrp_player_data:
                if str(entry[0]) in players_to_be_updated:
                    if str(entry[0]) not in data.keys():
                        for sub_entry in darkrp_player_data:
                            if sub_entry[1] == entry[1] and sub_entry[2] == entry[2]:
                                new_data[str(entry[0])]['backwards_compat_id'] = sub_entry[0]
                                break
                            else:
                                continue
                    new_data[str(entry[0])]['rpname'] = entry[1]
                    new_data[str(entry[0])]['wallet'] = entry[2]
                    continue
                else:
                    continue


            gas_offline_player_data_query = f"""SELECT account_id, nick, usergroup, ip_address, country_code FROM {gas_offline_player_data}{" WHERE " if len(players_to_not_update) > 0 else ""}{" AND ".join([f"account_id != {data[str(steamid64)]['gas_id']}" for steamid64 in players_to_not_update])}"""
            cursor.execute(gas_offline_player_data_query)
            gas_offline_player_data_data = cursor.fetchall()
            for entry in gas_offline_player_data_data:
                for steamid64 in players_to_be_updated:
                    if str(steamid64) in data.keys():
                        if entry[0] == new_data[str(steamid64)]:
                            new_data[str(steamid64)]['country_code'] = entry[4]
                            new_data[str(steamid64)]['ip_address'] = entry[3]
                            break
                    if entry[1] == new_data[str(steamid64)]['rpname'] and entry[2] == new_data[str(steamid64)]['rank']:
                        new_data[str(steamid64)]['gas_id'] = entry[0]
                        new_data[str(steamid64)]['country_code'] = entry[4]
                        new_data[str(steamid64)]['ip_address'] = entry[3]
                        break

            darkrp_levels_query = f"""SELECT uid, level, xp FROM {darkrp_levels}{" WHERE " if len(players_to_not_update) > 0 else ""}{" AND ".join([f"uid != {data[str(steamid64)]['backwards_compat_id']}" for steamid64 in players_to_not_update])}"""
            cursor.execute(darkrp_levels_query)
            darkrp_levels_query_data = cursor.fetchall()
            for entry in darkrp_levels_query_data:
                for steamid64 in players_to_be_updated:
                    if entry[0] == new_data[str(steamid64)]["backwards_compat_id"]:
                        new_data[str(steamid64)]['level'] = entry[1]
                        new_data[str(steamid64)]['xp'] = entry[2]
                        break
                    else:
                        continue

            cache.cache_dict['entries'] = new_data
            self.caching_system.updateCache(cache_name, cache)

    def __firstTimeGetLoggingClasses(self):
        cursor = self.sql.cursor()
        cache_name = self.config['mysql']['tables']['gas_logging_classes']
        cache_type = CacheType.OneTime
        cache = self.caching_system.createCache(cache_name, cache_type)
        try:
            highest_id = cache.getSpecialEntry('highest_id')
        except KeyError:
            highest_id = 0
            cache.addSpecialEntry('highest_id', highest_id)

        query = f"""SELECT id, class_type, class_name FROM {cache_name} WHERE id > {str(highest_id)}"""
        cursor.execute(query)
        cursor_fetchall = cursor.fetchall()
        cursor.close()

        if len(cursor_fetchall) > 0:
            id = highest_id
            with open("gmod/class_types.json", "r") as f:
                class_types = json.loads(f.read())
            for entry in cursor_fetchall:
                data = {"id": str(entry[0]), "class_type": str(class_types[str(entry[1])]), "class_name": str(entry[2])}
                if int(entry[0]) > id:
                    id = int(entry[0])
                cache.new_entry(str(entry[0]), data)
            cache.reset_created_time()
            cache.addSpecialEntry('highest_id', id)
            self.caching_system.updateCache(cache_name, cache)



    def getLoggingModuleCategories(self):
        cache_name = self.config["mysql"]["tables"]["gas_logging_module_categories"]
        return self.caching_system.getCache(cache_name).get_data()
    def getLoggingModules(self):
        cache_name = self.config["mysql"]["tables"]["gas_logging_modules"]
        return self.caching_system.getCache(cache_name).get_data()

    def getLoggingClasses(self):
        cache_name = self.config['mysql']['tables']['gas_logging_classes']
        return self.caching_system.getCache(cache_name).get_data()


    def getPlayers(self):
        self.__firstTimePlayers()
        cache_name = "Players"
        return self.caching_system.getCache(cache_name).get_data()

    def __firstTimeGetIndexCache(self):
        index_cache_name = "log_index_cache"
        index_cache_type = CacheType.OneTime
        index_cache: Cache = self.caching_system.createCache(index_cache_name, index_cache_type)
        index_cache_data = index_cache.get_data()
        categories = self.getLoggingModuleCategories()
        players = self.getPlayers()
        modules = self.getLoggingModules()
        try:
            index_cache_data['categories']
        except KeyError:
            index_cache_data['categories'] = {}
        try:
            index_cache_data['players']
        except KeyError:
            index_cache_data['players'] = {}
        try:
            index_cache_data['players']['alternative_player_id_index']
        except KeyError:
            index_cache_data['players']['alternative_player_id_index'] = {}

        for category in categories:
            if str(category) not in index_cache_data['categories']:
                index_cache_data['categories'][str(category)] = {'modules': {}}
            for module in modules:
                if modules[str(module)]['category_id'] == int(category):
                    if str(module) not in index_cache_data['categories'][str(category)]['modules']:
                        index_cache_data['categories'][str(category)]['modules'][str(module)] = {'logs': {}}
                    else:
                        continue
                else:
                    continue
        for player in players:
            if str(player) not in index_cache_data['players']:
                alternative_index = {
                    "backwards_compat_id": players[str(player)]['backwards_compat_id'],
                    "gas_id": players[str(player)]['gas_id'],
                    "sam_id": players[str(player)]['sam_id'],
                    "steamid64": players[str(player)]['steamid64'],
                    'steamid': players[str(player)]['steamid']
                }
                for key in alternative_index:
                    try:
                        index_cache_data['players']['alternative_player_id_index'][str(key)]
                    except KeyError:
                        index_cache_data['players']['alternative_player_id_index'][str(key)] = {}
                    index_cache_data['players']['alternative_player_id_index'][str(key)][str(players[str(player)][str(key)])] = alternative_index

                index_cache_data['players'][str(player)] = {'logs': {}}
        index_cache.set_data(index_cache_data)
        self.caching_system.updateCache(index_cache_name, index_cache)

    def getIndexCache(self):
        self.__firstTimeGetIndexCache()
        index_cache_name = "log_index_cache"
        index_cache_type = CacheType.OneTime
        return self.caching_system.getCache(index_cache_name).get_data()



    def __firstTimeGetLogs(self):
        cache_name = self.config["mysql"]["tables"]["gas_logging_deepstorage_logdata"]
        cache_type = CacheType.Additive
        cache = self.caching_system.createCache(cache_name, cache_type)
        index_cache_data = self.getIndexCache()
        try:
            index_cache_data['categories']
        except KeyError:
            index_cache_data['categories'] = {}
            index_cache_data['players'] = {'alternative_player_id_index': {
                'steamid': {},
                'steamid64': {},
                'gas_id': {},
                'sam_id': {},
                'backwards_compat_id': {}
            }}
        categories = self.getLoggingModuleCategories()
        modules = self.getLoggingModules()
        players = self.getPlayers()
        classes = self.getLoggingClasses()


        new_logs = []
        try:
            log_count = cache.getSpecialEntry("log_count")
        except KeyError:
            log_count = 0
            cache.addSpecialEntry("log_count", log_count)
        try:
            highest_log_id = cache.getSpecialEntry("highest_log_id")
        except KeyError:
            highest_log_id = 0
            cache.addSpecialEntry("highest_log_id", highest_log_id)
        query_gas_logging_deepstorage_logdata = f"""SELECT log_id, data_index, string, highlight, currency, console, bot, account_id, usergroup, team, role, health, armor, weapon, vehicle, dmg_amount, dmg_type, class_type, class_id FROM {str(self.config['mysql']['tables']['gas_logging_deepstorage_logdata'])} WHERE log_id > {str(highest_log_id)}"""
        cursor = self.sql.cursor()
        cursor.execute(query_gas_logging_deepstorage_logdata)
        gas_logging_deepstorage_logdata = cursor.fetchall()
        query_gas_logging_deepstorage = f"""SELECT id, module_id, log, log_phrase, timestamp, session FROM {str(self.config['mysql']['tables']['gas_logging_deepstorage'])} WHERE id > {str(highest_log_id)}"""
        cursor.execute(query_gas_logging_deepstorage)
        gas_logging_deepstorage = cursor.fetchall()
        query_gas_logging_pvp_events = f""""""

        cursor.close()

        for entry in gas_logging_deepstorage:
            # Below are all the data in each log
            deepstorage_log_id = entry[0]
            if deepstorage_log_id > highest_log_id:
                highest_log_id = deepstorage_log_id
            deepstorage_module_id = entry[1]
            log_module: dict = modules[str(deepstorage_module_id)]
            log_module_category: dict = categories[str(log_module['category_id'])]


            deepstorage_log = entry[2]
            deepstorage_log_phrase = entry[3]
            deepstorage_timestamp = entry[4]
            deepstorage_session = entry[5]
            log_hint = {'log_id': deepstorage_log_id, 'timestamp': deepstorage_timestamp}
            index_cache_data['categories'][str(log_module_category['id'])]['modules'][str(log_module['id'])]['logs'][str(deepstorage_log_id)] = log_hint
            log_data = {"log_id": deepstorage_log_id, "timestamp": deepstorage_timestamp,
                        "module_id": deepstorage_module_id, "deepstorage_log": deepstorage_log,
                        "log_phrase": deepstorage_log_phrase, 'module': log_module['name'],
                        'category': log_module_category['name'], 'module_specific_info': {}}


            for sub_entry in gas_logging_deepstorage_logdata:
                if deepstorage_module_id == 3:
                    break
                log_id = sub_entry[0]
                if log_id == deepstorage_log_id:
                    data_index = sub_entry[1]
                    string = sub_entry[2]
                    highlight = sub_entry[3]
                    currency = sub_entry[4]
                    console = sub_entry[5]
                    bot = sub_entry[6]
                    account_id = sub_entry[7]
                    if account_id is not None:
                        if data_index == 1:
                            try:
                                log_data['main_player'] = index_cache_data['players']['alternative_player_id_index']['gas_id'][str(account_id)]['steamid64']
                                index_cache_data['players'][str(log_data['main_player'])]['logs'][
                                    str(deepstorage_log_id)] = log_hint
                            except KeyError:
                                log_data['main_player'] = None
                        else:
                            try:
                                log_data['secondary_player'] = index_cache_data['players']['alternative_player_id_index']['gas_id'][str(account_id)]['steamid64']
                                index_cache_data['players'][str(log_data['main_player'])]['logs'][
                                    str(deepstorage_log_id)] = log_hint
                            except KeyError:
                                log_data['secondary_player'] = None
                    usergroup = sub_entry[8]
                    team = sub_entry[9]
                    role = sub_entry[10]
                    health = sub_entry[11]
                    armor = sub_entry[12]
                    weapon = sub_entry[13]
                    vehicle = sub_entry[14]
                    dmg_amount = sub_entry[15]
                    dmg_type = sub_entry[16]
                    class_type = sub_entry[17]
                    class_id = sub_entry[18]
                    if int(deepstorage_module_id) == 14:
                        if data_index == 2:
                            log_data['module_specific_info']['original_name'] = str(highlight)
                        elif data_index == 3:
                            log_data['module_specific_info']['new_name'] = str(highlight)
                    elif int(deepstorage_module_id) == 56:
                        if data_index == 2:
                            log_data['module_specific_info']['chat_said'] = str(string)
                    elif int(deepstorage_module_id) == 18:
                        if data_index == 2:
                            log_data['module_specific_info']['command_ran'] = str(string)
                    elif int(deepstorage_module_id) == 17:
                        if data_index == 2:
                            log_data['module_specific_info']['cheque_amount'] = int(currency)
                    elif int(deepstorage_module_id) == 42:
                        log_data['module_specific_info']['type'] = deepstorage_log_phrase
                        if deepstorage_log_phrase == "connected_from_country":
                            log_data['module_specific_info']['country'] = class_id
                    elif int(deepstorage_module_id) == 36:
                        if deepstorage_log_phrase == "spawned_prop":
                            if data_index == 2:
                                log_data['module_specific_info']['prop_spawned'] = classes[str(class_id)]['class_name']
                    elif int(deepstorage_module_id) == 34:
                        if data_index == 2:
                            log_data['module_specific_info']['tool'] = highlight
                        elif data_index == 3:
                            log_data['module_specific_info']['used_on'] = classes[str(class_id)]['class_name']
                    elif int(deepstorage_module_id) == 52:
                        if data_index == 2:
                            log_data['module_specific_info']['damage_taken'] = dmg_amount
                            log_data['module_specific_info']['damage_type'] = dmg_type
                    elif int(deepstorage_module_id) == 45:
                        if data_index == 2:
                            log_data['module_specific_info']['picked_up_item'] = classes[str(class_id)]['class_name']
                else:
                    continue
            cache.new_entry(str(deepstorage_log_id), log_data)
            new_logs.append(log_data)
        cache.addSpecialEntry('highest_log_id', highest_log_id)
        log_count += len(new_logs)
        cache.addSpecialEntry('log_count', log_count)
        self.caching_system.updateCache(cache_name, cache)
        index_cache : Cache = self.caching_system.getCache("log_index_cache")
        index_cache.set_data(index_cache_data)
        self.caching_system.updateCache('log_index_cache', index_cache)

            # Above is all the data in each log

    def getLogs(self):
        self.firstTimeSetups()
        cache_name = self.config["mysql"]["tables"]["gas_logging_deepstorage_logdata"]
        cache: Cache = self.caching_system.getCache(cache_name)
        return cache.get_data()






    def __autoHandleAdditiveCache(self):
        pass