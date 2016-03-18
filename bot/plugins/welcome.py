from plugin import Plugin
import asyncio
import logging
from types import MethodType
import discord

log = logging.getLogger('discord')

class Welcome(Plugin):

    fancy_name = "Welcome"

    @asyncio.coroutine
    def on_member_join(self, member):
        server = member.server
        storage = self.get_storage(server)
        welcome_message = storage.get('welcome_message').format(
            server = server.name,
            user = member.mention
        )
        channel_name = storage.get('channel_name')

        destination = server
        channel = discord.utils.find(lambda c: c.name == channel_name, server.channels)
        if channel is not None:
            destination = channel

        yield from self.mee6.send_message(destination, welcome_message)
