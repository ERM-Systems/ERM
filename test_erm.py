import datetime
import unittest
from typing import Union
from unittest.mock import MagicMock

from discord import DMChannel
from discord.ext.commands import CheckFailure, Context, NoPrivateMessage, has_any_role

from helpers import MockContext, MockRole
from utils.timestamp import td_format


async def has_any_role_check(ctx: Context, *roles: Union[str, int]) -> bool:
    """
    Returns True if the context's author has any of the specified roles.
    `roles` are the names or IDs of the roles for which to check.
    False is always returns if the context is outside a guild.
    """
    try:
        return await has_any_role(*roles).predicate(ctx)
    except CheckFailure:
        return False


async def has_no_roles_check(ctx: Context, *roles: Union[str, int]) -> bool:
    """
    Returns True if the context's author doesn't have any of the specified roles.
    `roles` are the names or IDs of the roles for which to check.
    False is always returns if the context is outside a guild.
    """
    try:
        return not await has_any_role(*roles).predicate(ctx)
    except NoPrivateMessage:
        return False
    except CheckFailure:
        return True


class ChecksTests(unittest.IsolatedAsyncioTestCase):
    """Tests the check functions defined in `bot.checks`."""

    def setUp(self):
        self.ctx = MockContext()

    async def test_has_any_role_check_without_guild(self):
        """`has_any_role_check` returns `False` for non-guild channels."""
        self.ctx.channel = MagicMock(DMChannel)
        self.assertFalse(await has_any_role_check(self.ctx))

    async def test_has_any_role_check_without_required_roles(self):
        """`has_any_role_check` returns `False` if `Context.author` lacks the required role."""
        self.ctx.author.roles = []
        self.assertFalse(await has_any_role_check(self.ctx))

    async def test_has_any_role_check_with_guild_and_required_role(self):
        """`has_any_role_check` returns `True` if `Context.author` has the required role."""
        self.ctx.author.roles.append(MockRole(id=10))
        self.assertTrue(await has_any_role_check(self.ctx, 10))

    async def test_has_no_roles_check_without_guild(self):
        """`has_no_roles_check` should return `False` when `Context.guild` is None."""
        self.ctx.channel = MagicMock(DMChannel)
        self.ctx.guild = None
        self.assertFalse(await has_no_roles_check(self.ctx))


class TdFormatTests(unittest.TestCase):
    """Tests for `utils.timestamp.td_format`."""

    def test_zero_duration(self):
        """A zero timedelta is rendered as `0 seconds`."""
        self.assertEqual(td_format(datetime.timedelta(seconds=0)), "0 seconds")

    def test_singular_unit_has_no_trailing_s(self):
        """A value of one is rendered without a trailing `s`."""
        self.assertEqual(td_format(datetime.timedelta(seconds=1)), "1 second")
        self.assertEqual(td_format(datetime.timedelta(hours=1)), "1 hour")

    def test_plural_unit_has_trailing_s(self):
        """Values greater than one are pluralised."""
        self.assertEqual(td_format(datetime.timedelta(days=2)), "2 days")

    def test_multiple_units_are_joined_largest_first(self):
        """Multiple non-zero periods are joined with commas, largest first."""
        self.assertEqual(
            td_format(datetime.timedelta(minutes=1, seconds=30)),
            "1 minute, 30 seconds",
        )

    def test_negative_duration_is_prefixed_with_minus(self):
        """A negative timedelta is prefixed with `-`."""
        self.assertEqual(
            td_format(datetime.timedelta(seconds=-3661)),
            "-1 hour, 1 minute, 1 second",
        )
