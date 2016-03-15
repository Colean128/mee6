from plugin import Plugin
import asyncio

class Hello(Plugin):
    @asyncio.coroutine
    def on_message(self, message):
        if message.content == '!hello':
            yield from self.mee6.send_message(message.channel, 'Hello ! {} from the server {}'.format(
                message.author.mention,
                message.server.name
            ))
