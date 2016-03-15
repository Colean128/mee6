import logging
import asyncio
from plugin import Plugin

log = logging.getLogger('discord')

class PluginManager:

    def __init__(self, mee6):
        self.mee6 = mee6
        self.db = mee6.db
        self.mee6.plugins = []

    def load(self, plugin):
        log.info('Loading plugin {}.'.format(plugin.__name__))
        plugin_instance = plugin(self.mee6)
        self.mee6.plugins.append(plugin_instance)
        log.info('Plugin {} loaded.'.format(plugin.__name__))

    def load_all(self):
        for plugin in Plugin.plugins:
            self.load(plugin)

    def get_all(self, server):
        plugin_names = self.db.redis.smembers('plugins:{}'.format(server.id))
        plugins = []
        for plugin in self.mee6.plugins:
            if plugin.__class__.__name__ in plugin_names:
                plugins.append(plugin)
        return plugins
