from utils.utils import time_converter

scheduleLimit = 365 * 24 * 60 * 60
epochDigits = 10
scheduleTypes = ("start", "vote")


def parse_schedule_time(value: str, now: int) -> int:
    text = (value or "").strip()
    if not text:
        raise ValueError("No time was given.")

    if text.isdigit() and len(text) >= epochDigits:
        moment = int(text)
    else:
        moment = int(now) + time_converter(text)

    if moment <= int(now):
        raise ValueError("That time has already passed.")

    if moment - int(now) > scheduleLimit:
        raise ValueError("Sessions cannot be scheduled more than a year ahead.")

    return moment


def normalise_type(value: str | None) -> str:
    text = (value or "").strip().lower()
    return text if text in scheduleTypes else "start"


def due_schedules(documents, now: int) -> list:
    ready = [
        document
        for document in (documents or [])
        if not document.get("posted") and document.get("scheduled_for") is not None
        and int(document["scheduled_for"]) <= int(now)
    ]

    return sorted(ready, key=lambda document: int(document["scheduled_for"]))
