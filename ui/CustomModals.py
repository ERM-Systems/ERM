import discord, typing
from menus import CustomModal
from utils.utils import generalised_interaction_check_failure

class CustomModalButton(discord.ui.Button):
    def __init__(
        self,
        user_id,
        title: str,
        label: str,
        options: typing.List[typing.Tuple[str | typing.Literal[str], discord.ui.TextInput | discord.ui.Label | discord.ui.TextDisplay]],
        epher_args: typing.Optional[dict] = None,
    ):
        super().__init__(label=label or "Enter Strike Amount", style=discord.ButtonStyle.secondary)
        self.value = None
        self.user_id = user_id
        self.modal: typing.Union[None, CustomModal] = None
        self.title = title or self.label
        self.label = label
        self.options = options
        self.epher_args = epher_args or {}

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.defer(ephemeral=True, thinking=True)
            return await generalised_interaction_check_failure(interaction.followup)

        self.modal = CustomModal(self.label, self.options, self.epher_args)
        await interaction.response.send_modal(self.modal)
        await self.modal.wait()
        
        self.values = []
        for component in self.modal.children:
            if isinstance(component, discord.ui.TextDisplay): continue
            if isinstance(component, discord.ui.Label):
                # Labels have a .component attribute
                target = component.component
            else:
                # Other components are the target themselves
                target = component
            
            # Skip if target doesn't have value/values
            if hasattr(target, 'values'):
                self.values.append(target.values)
            elif hasattr(target, 'value'):
                self.values.append(target.value)
        self.parent.view.values = self.values
        self.parent.view.stop()
        return

class CustomModalExecutorButton(discord.ui.Button):
    def __init__(
        self,
        user_id,
        title: str,
        label: str,
        options: typing.List[typing.Tuple[str | typing.Literal[str], discord.ui.TextInput | discord.ui.Label]],
        func: typing.Callable,
        epher_args: typing.Optional[dict] = None,
        
    ):
        super().__init__(label=label or "Enter Strike Amount", style=discord.ButtonStyle.secondary)
        self.value = None
        self.user_id = user_id
        self.modal: typing.Union[None, CustomModal] = None
        self.title = title or self.label
        self.label = label
        self.options = options
        self.func = func
        self.epher_args = epher_args or {}

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.defer(ephemeral=True, thinking=True)
            return await generalised_interaction_check_failure(interaction.followup)

        self.modal = CustomModal(self.label, self.options, self.epher_args)
        await interaction.response.send_modal(self.modal)
        await self.modal.wait()
        
        self.values = []
        for component in self.modal.children:
            if isinstance(component, discord.ui.TextDisplay): continue
            if isinstance(component, discord.ui.Label):
                # Labels have a .component attribute
                target = component.component
            else:
                # Other components are the target themselves
                target = component
            
            # Skip if target doesn't have value/values
            if hasattr(target, 'values'):
                self.values.append(target.values)
            elif hasattr(target, 'value'):
                self.values.append(target.value)
        await self.func(interaction, self)
        