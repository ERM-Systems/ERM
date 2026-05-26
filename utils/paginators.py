from copy import copy

import discord
from discord.ext import commands
import reactionmenu
import typing

from erm import Bot
from menus import CustomSelectMenu
from utils.constants import blank_color
import asyncio
import nest_asyncio


class CustomPage:
    embeds: list[discord.Embed]
    view: typing.Optional[discord.ui.View]
    identifier: typing.Optional[str]

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class SelectPagination(discord.ui.View):
    def __init__(
        self,
        bot: Bot,
        user_id: int,
        pages: list[CustomPage],
        start_at=0,
        edit_method=None,
    ):
        super().__init__(timeout=None)
        # we don't need this for the pagination, only the emojis :sob:
        self.bot = bot
        names_to_emojis = {"1": "l_arrow", "2": "arrow"}
        for button in self.children:
            if isinstance(button, discord.ui.Button):
                if button.emoji is not None:
                    button.emoji = discord.PartialEmoji.from_str(
                        bot.emoji_controller.get_emoji(names_to_emojis[button.label])
                    )
                    button.label = ""

        self.pages = pages
        self.user_id = user_id
        self.current_index = start_at
        self.view = self
        self.preset_children = copy(self.children)
        self.page_children = []
        self.edit_method = edit_method

        starting_page = self.pages[self.current_index]
        if starting_page.identifier:
            for item in self.children:
                if item.label == "TEMP":
                    item.label = starting_page.identifier

    def get_current_view(self) -> discord.ui.View:
        current_page = self.pages[self.current_index]
        new_page = self.pages[self.current_index]
        new_index = self.current_index

        view = self.view
        self.current_index = new_index

        page_view = getattr(new_page, "view", None)
        for i in view.children:
            if i.label == current_page.identifier:
                i.label = new_page.identifier
        if page_view:
            # checks = [i.row in [None, 0] for i in page_view.children]
            # Remove all non-native components
            for child in view.children:
                if child not in self.preset_children:
                    view.children.remove(child)

            self.page_children = []
            # if any(checks):
            #     for index, child in enumerate(page_view.children):
            #         if child.row is None:
            #             child.row = 1
            #         else:
            #             child.row += 1
            #         page_view.children[index] = child
            #         self.page_children.append(child)
            # else:
            for index, child in enumerate(page_view.children):
                self.page_children.append(child)

            for item in self.page_children:
                # Sanity check validations
                if getattr(item, "default", None) is not None:
                    if item.default > len(item.options):
                        item.default = 0
                        # print(f'INVALID ::: {item}')
                elif getattr(item, "default_values", None) is not None:
                    if len(item.default_values) > item.max_values:
                        item.default_values = []
                        # print(f'INVALID ::: {item}')
                else:
                    # print(item)
                    # print(f'Somewhat valid ::: {item}')
                    pass
                view.add_item(item)
        return view

    async def _paginate(
        self,
        interaction: discord.Interaction,
        increment_index: int,
        mode: typing.Literal["set", "increment"],
    ):
        current_page = self.pages[self.current_index]

        if mode == "set":
            new_index = increment_index
            new_page = self.pages[new_index]
        else:
            new_index = self.current_index + increment_index
            if new_index >= len(self.pages):
                new_index = 0
            new_page = self.pages[new_index]

        view = self.view
        self.current_index = new_index

        page_view = getattr(new_page, "view", None)
        for i in view.children:
            if getattr(i, "label", None):
                if i.label == current_page.identifier:
                    i.label = new_page.identifier

        if page_view:
            # Clear the items added by the previous page
            for item in self.page_children:
                view.remove_item(item)
            self.page_children.clear()

            # Add the items from the new page
            for item in page_view.children:
                if getattr(item, "default", None) is not None:
                    if item.default > len(item.options):
                        item.default = 0
                elif getattr(item, "default_values", None) is not None:
                    if len(item.default_values) > item.max_values:
                        item.default_values = []
                else:
                    # print(item)
                    pass
                view.add_item(item)
                self.page_children.append(item)

        if self.edit_method:
            await self.edit_method(embeds=new_page.embeds, view=view)
        else:
            await interaction.message.edit(embeds=new_page.embeds, view=view)

    @discord.ui.button(label="1", emoji="<:l_arrow:1169754353326903407>", row=4)
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title="Not Permitted",
                    description="You are not permitted to interact with these buttons.",
                    color=blank_color,
                ),
                ephemeral=True,
            )
        await interaction.response.defer()
        await self._paginate(interaction, -1, "increment")

    @discord.ui.button(label="TEMP", row=4)
    async def set_current_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title="Not Permitted",
                    description="You are not permitted to interact with these buttons.",
                    color=blank_color,
                ),
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True, thinking=True)

        msg = await interaction.followup.send(
            embed=discord.Embed(
                title="Change Pages",
                description="What page would you like to change to?",
                color=blank_color,
            ),
            view=(
                view := CustomSelectMenu(
                    self.user_id,
                    [
                        discord.SelectOption(label=page.identifier, value=str(index))
                        for index, page in enumerate(self.pages)
                    ],
                )
            ),
        )

        await view.wait()
        index = int(view.value or "1000")
        await msg.delete()
        if index != 1000:
            await self._paginate(interaction, index, "set")

    @discord.ui.button(label="2", emoji="<:arrow:1169695690784518154>", row=4)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title="Not Permitted",
                    description="You are not permitted to interact with these buttons.",
                    color=blank_color,
                ),
                ephemeral=True,
            )
        await interaction.response.defer()
        await self._paginate(interaction, 1, "increment")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Not Permitted",
                description="You are not permitted to interact with these buttons.",
                color=blank_color,
            ),
            ephemeral=True,
        )
        return False

class CustomPageV2:
    view: typing.Optional[discord.ui.LayoutView]
    identifier: typing.Optional[str]
    containers: list[discord.ui.Container]
    aliases: list[str]

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class SelectPaginationV2(discord.ui.LayoutView):
    def __init__(
        self,
        bot,
        user_id: int,
        pages: list[CustomPageV2],
        start_at=0,
        edit_method=None,
    ):
        super().__init__(timeout=900)
        self.bot = bot
        self.pages = pages
        self.user_id = user_id
        self.current_index = start_at
        self.edit_method = edit_method

        self.index_button = discord.ui.Button(
            label = f"Page {self.current_index+1}/{len(pages)}",
            disabled=True
        )

        self.back_button = discord.ui.Button(
            emoji=discord.PartialEmoji.from_str(
                bot.emoji_controller.get_emoji("l_arrow")
            )
        )
        self.set_current_page = discord.ui.Button(
            label=pages[start_at].identifier or "TEMP"
        )
        self.next_button = discord.ui.Button(
            emoji=discord.PartialEmoji.from_str(
                bot.emoji_controller.get_emoji("arrow")
            )
        )
        self.end_button = discord.ui.Button(
            emoji = "<:check:1163142000271429662>"
        )

        self.back_button.callback = self._back_callback
        self.set_current_page.callback = self._set_page_callback
        self.next_button.callback = self._next_callback
        self.end_button.callback = self._end_callback
        self.nav_row = discord.ui.ActionRow(
            self.index_button,
            self.back_button,
            self.set_current_page,
            self.next_button,
            self.end_button
        )
        self.nav_container = discord.ui.Container()
        self.nav_container.interaction_check = self.interaction_check
        self.nav_container.add_item(self.nav_row)
        self.add_item(self.nav_container)
        
    async def on_timeout(self):
        self.remove_item(self.nav_container)
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        print(f"{self.user_id}, {type(self.user_id)}")
        print(interaction.user.id)
        if interaction.user.id != int(self.user_id):
            await interaction.response.defer()
            await generalised_interaction_check_failure(interaction.followup)
            return False
        else:
            return True
    def _validate_page_items(self, page_view: discord.ui.LayoutView):
        for item in page_view.children:
            if getattr(item, "default", None) is not None:
                if item.default > len(item.options):
                    item.default = 0
            elif getattr(item, "default_values", None) is not None:
                if len(item.default_values) > item.max_values:
                    item.default_values = []

    def _update_identifier_label(self, new_page: CustomPageV2):
        if new_page.identifier:
            self.set_current_page.label = new_page.identifier

    def _build_view(self, page: CustomPageV2, detach: bool=False) -> discord.ui.LayoutView:
        view = discord.ui.LayoutView(timeout=None)

        for container in getattr(page, "containers", []):
            view.add_item(container)

        page_view = getattr(page, "view", None)
        if page_view:
            self._validate_page_items(page_view)
            for item in page_view.children:
                view.add_item(item)
         
        if not detach:
            view.add_item(self.nav_container)

        return view

    def get_current_view(self, alias: str|None=None) -> discord.ui.LayoutView:
        if alias:
            self.current_index = self.pages.index([page for page in self.pages if alias in page.aliases][0]) 
        page = self.pages[self.current_index]
        self._update_identifier_label(page)
        return self._build_view(page)
    
    async def _paginate(
        self,
        interaction: discord.Interaction,
        increment_index: int,
        mode: typing.Literal["set", "increment", "detach"],
    ):
        if mode == "set":
            new_index = increment_index
        elif mode == "detach":
            new_index = self.current_index
        else:
            new_index = (self.current_index + increment_index) % len(self.pages)

        self.current_index = new_index
        self.index_button.label = f"Page {self.current_index+1}/{len(self.pages)}"
        new_page = self.pages[new_index]

        self._update_identifier_label(new_page)
        if not mode == "detach":
            new_view = self._build_view(new_page)
        else:
            new_view = self._build_view(new_page, detach=True)

        if self.edit_method:
            await self.edit_method(view=new_view)
        else:
            await interaction.message.edit(view=new_view)

    async def _back_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._paginate(interaction, -1, "increment")

    async def _set_page_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title="Not Permitted",
                    description="You are not permitted to interact with these buttons.",
                    color=000000,
                ),
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True, thinking=True)
        cont = discord.ui.Container()
        cont.add_item(
            discord.ui.TextDisplay(
                (
                    "### Change the Page\n"
                    "What page would you like to go to?"
                )
            )
        ).add_item(
            discord.ui.Separator()
        )
        containers: list[discord.ui.Container] = []
        containers.append(cont)
        indexed_pages = list(enumerate(self.pages))
        page_chunks = list(chunk_list(indexed_pages, 25))  # 25 options per select

        for container_index in range(4):  # max 4 containers
            if not page_chunks:
                break

            container = discord.ui.Container()

            for _ in range(5):  # max 5 selects per container
                if not page_chunks:
                    break

                chunk = page_chunks.pop(0)

                options = [
                    discord.SelectOption(label=page.identifier, value=str(index))
                    for index, page in chunk
                ]

                container.add_item(
                    discord.ui.ActionRow(
                        CustomDropdown(self.user_id, options)
                    )
                )

            containers.append(container)
            
        view = discord.ui.LayoutView()
        for container in containers:
            view.add_item(container)
        msg = await interaction.followup.send(
            embed=None,
            view=view)
        

        await view.wait()
        index = int(view.value or "1000")
        await msg.delete()
        if index != 1000:
            await self._paginate(interaction, index, "set")

    async def _next_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._paginate(interaction, 1, "increment")

    async def _end_callback(self, interaction: discord.Interaction):
        self.remove_item(self.nav_container)
        await interaction.response.defer()
        await self._paginate(interaction, 0, "detach")
        


