import logging

minPoints = 3
edgeTolerance = 0.0001


def _on_edge(a: dict, b: dict, probe: dict) -> bool:
    cross = (b["x"] - a["x"]) * (probe["z"] - a["z"]) - (b["z"] - a["z"]) * (probe["x"] - a["x"])
    if abs(cross) > edgeTolerance:
        return False

    withinX = min(a["x"], b["x"]) - edgeTolerance <= probe["x"] <= max(a["x"], b["x"]) + edgeTolerance
    withinZ = min(a["z"], b["z"]) - edgeTolerance <= probe["z"] <= max(a["z"], b["z"]) + edgeTolerance

    return withinX and withinZ


def inside_region(points: list, probe: dict) -> bool:
    """Ray casting, matching lib/aop.ts exactly.

    A shape with too few points means nobody is enforced against, and a player
    sitting on the boundary counts as inside so rounding never punishes them.
    """
    if not points or len(points) < minPoints:
        return True

    inside = False
    count = len(points)

    for i in range(count):
        a = points[i]
        b = points[i - 1]

        if _on_edge(a, b, probe):
            return True

        straddles = (a["z"] > probe["z"]) != (b["z"] > probe["z"])
        if not straddles:
            continue

        crossing = (b["x"] - a["x"]) * (probe["z"] - a["z"]) / (b["z"] - a["z"]) + a["x"]
        if probe["x"] < crossing:
            inside = not inside

    return inside


def normalise_points(raw) -> list:
    points = []

    for entry in raw or []:
        try:
            points.append({"x": float(entry["x"]), "z": float(entry["z"])})
        except (KeyError, TypeError, ValueError):
            continue

    return points


def active_region(settings: dict, session: dict | None = None) -> dict | None:
    """The area being enforced right now, if any."""
    options = (settings or {}).get("area_of_play") or {}
    if options.get("enabled") is not True:
        return None

    regions = options.get("regions") or []
    if not regions:
        return None

    wanted = (session or {}).get("aop_region") or options.get("default_region")
    chosen = next((region for region in regions if region.get("id") == wanted), None) if wanted else regions[0]
    if not chosen:
        return None

    points = normalise_points(chosen.get("points"))
    if len(points) < minPoints:
        return None

    return {"id": chosen.get("id"), "name": chosen.get("name") or "Area of Play", "points": points}


def outside_players(players: list, region: dict) -> list:
    """Players currently outside the area, ignoring anyone with no position."""
    outside = []

    for player in players:
        location = getattr(player, "location", None) or {}
        x = location.get("x") if isinstance(location, dict) else None
        z = location.get("z") if isinstance(location, dict) else None

        if x is None or z is None:
            continue

        if not inside_region(region["points"], {"x": float(x), "z": float(z)}):
            outside.append(player)

    return outside


def enforcement_plan(options: dict, offences: int) -> str:
    """What to do to a player on this offence: warn, or the configured action."""
    raw = options.get("warnings")
    warnings = max(0, int(3 if raw is None else raw))

    if offences <= warnings:
        return "warn"

    action = str(options.get("action") or "kick").lower()
    return action if action in ("kick", "ban", "wanted") else "kick"
