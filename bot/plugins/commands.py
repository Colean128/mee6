from plugin import Plugin
import asyncio

class Commands(Plugin):

    fancy_name = 'Custom Commands'

    def get_commands(self, server):
        storage = self.get_storage(server)
        commands = sorted(storage.smembers('commands'))
        cmds = []
        for command in commands:
            cmd = {
                'name': command
            }
            cmds.append(cmd)
        return cmds

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
