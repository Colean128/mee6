from plugin import Plugin
import asyncio
import logging
from types import MethodType

log = logging.getLogger('discord')

def get_help_info(self, server):
    if self.fancy_name is None:
        self.fancy_name = type(self).__name__
    payload = {
        'name': type(self).__name__,
        'fancy_name': self.fancy_name,
        'commands': self.get_commands(server)
    }
    return payload


class Help(Plugin):

    def __init__(self, *args, **kwargs):
        Plugin.__init__(self, *args, **kwargs)
        # Patch the Plugin class
        Plugin.get_help_info = get_help_info

    def generate_help(self, server):
        enabled_plugins = self.mee6.plugin_manager.get_all(server)
        enabled_plugins = sorted(enabled_plugins, key=lambda p: type(p).__name__)

        help_payload = []
        for plugin in enabled_plugins:
            if not isinstance(plugin, Help) and hasattr(plugin, 'get_commands'):
                help_info = plugin.get_help_info(server)
                help_payload.append(help_info)

        return self.render_message(help_payload)

    def render_message(self, help_payload):
        message = ""
        for plugin_info in help_payload:
            if plugin_info['commands'] != []:
                message += "**{}**\n".format(plugin_info['fancy_name'])
            for cmd in plugin_info['commands']:
                message += "   **{}** {}\n".format(cmd['name'], cmd.get('description', ''))
        return message


    @asyncio.coroutine
    def on_message(self, message):
        if message.content =='!help':
            log.info('{}#{}@{} >> !help'.format(
                message.author.name,
                message.author.discriminator,
                message.server.name
            ))
            server = message.server
            help_message = self.generate_help(server)
            if help_message == '':
                help_message = "There's no command to show :cry:"
            yield from self.mee6.send_message(message.channel, help_message)
