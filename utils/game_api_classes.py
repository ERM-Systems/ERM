from discord.ext import commands; import typing

class ResponseFailure(Exception):
    detail: str | None
    status_code: int
    json_data: dict

    def __init__(self, *args, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"{self.status_code}: {self.json_data}"

class ServerLinkNotFound(commands.CheckFailure):
    def __init__(self, platform: typing.Optional[str]):
        self.platform = platform
        super().__init__()

    platform: str = "erlc"
    code: int = 0