import discord
class SimpleTextChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, limit=1, **kwargs):
        super().__init__(placeholder="Select Channels" if limit > 1 else "Select a Channel", max_values=limit, channel_types=[discord.ChannelType.text], **kwargs)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.parent.view.stop()