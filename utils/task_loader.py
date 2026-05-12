from pkgutil import iter_modules
import asyncio, logging as l, importlib
from discord.ext import tasks
logging = l.getLogger("tasks")
async def start_tasks(bot):
    logging.info("Starting task loader...")
    for module in iter_modules(["tasks"], "tasks."):
        mod = importlib.import_module(module.name)
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)

            if isinstance(attr, tasks.Loop):
                logging.info(f"Task {module.name} started")
                attr.start(bot)
        await asyncio.sleep(2)