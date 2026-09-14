LEVEL_KEYS = {
    "staff": "bot.staff",
    "admin": "bot.admin",
    "management": "bot.management",
}


def _role_ids(value):
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]

    ids = []
    for entry in value:
        try:
            ids.append(int(entry))
        except (TypeError, ValueError):
            continue
    return ids


def granted_keys(guild_settings, member_role_ids):
    if not isinstance(guild_settings, dict):
        return set()

    custom = guild_settings.get("custom_permissions")
    if not isinstance(custom, dict):
        return set()

    roles = custom.get("roles")
    if not isinstance(roles, list):
        return set()

    held = {int(role_id) for role_id in member_role_ids}
    granted = set()

    for role in roles:
        if not isinstance(role, dict):
            continue
        if not held.intersection(_role_ids(role.get("discord_role_ids"))):
            continue

        permissions = role.get("permissions")
        if not isinstance(permissions, dict):
            continue

        for key, enabled in permissions.items():
            if enabled is True and isinstance(key, str):
                granted.add(key)

    return granted


def command_key(qualified_name):
    if not qualified_name:
        return ""
    return "bot." + ".".join(qualified_name.split())


def allowed(guild_settings, member_role_ids, level, qualified_name):
    granted = granted_keys(guild_settings, member_role_ids)
    if not granted:
        return False

    if LEVEL_KEYS.get(level) in granted:
        return True

    key = command_key(qualified_name)
    return bool(key) and key in granted
