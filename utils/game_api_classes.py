from discord.ext import commands; import typing

class ResponseFailure(Exception):
    detail: str | None
    status_code: int
    json_data: dict

    def __init__(self, *args, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"{getattr(self, 'status_code', '?')}: {getattr(self, 'json_data', None)}"

    __str__ = __repr__

class ServerLinkNotFound(commands.CheckFailure):
    def __init__(self, platform: typing.Optional[str]):
        self.platform = platform
        super().__init__()

    platform: str = "erlc"
    code: int = 0