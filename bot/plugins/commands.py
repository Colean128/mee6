from plugin import Plugin
import asyncio

class Commands(Plugin):

    @asyncio.coroutine
    def on_message(self, message):
        storage = self.get_storage(message.server)
        commands = storage.smembers('commands')
        if message.content in commands:
            response = storage.get('command:{}'.format(message.content))
            yield from self.mee6.send_message(
                message.channel,
                response
            )
