import discord
import asyncio
import logging
from plugin_manager import PluginManager
from database import Db
from utils import find_server

from plugins.hello import Hello

log = logging.getLogger('discord')

class Mee6(discord.Client):
    def __init__(self, *args, **kwargs):
        discord.Client.__init__(self, *args, **kwargs)
        self.redis_url = kwargs.get('redis_url')
        self.db = Db(self.redis_url)
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_all()

    @asyncio.coroutine
    def _run_plugin_event(self, plugin, event, *args, **kwargs):
        # A modified coro that is based on Client._run_event
        try:
            yield from getattr(plugin, event)(*args, **kwargs)
        except asyncio.CancelledError:
            pass
        except Exception:
            try:
                yield from self.on_error(event, *args, **kwargs)
            except asyncio.CancelledError:
                pass

    def dispatch(self, event, *args, **kwargs):
        # A list of events that are available from the plugins
        plugin_events = (
            'message',
            'message_delete',
            'message_edit',
            'channel_delete',
            'channel_create',
            'channel_update',
            'member_join',
            'member_update',
            'server_update',
            'server_role_create',
            'server_role_delete',
            'server_role_update',
            'voice_state_update',
            'member_ban',
            'member_unban',
            'typing'
        )
        log.debug('Dispatching event {}'.format(event))
        method = 'on_' + event
        handler = 'handle_' + event

        if hasattr(self, handler):
            getattr(self, handler)(*args, **kwargs)

        if event in plugin_events:
            server_context = find_server(*args, **kwargs)
            if server_context is None:
                return

            # For each plugin that the server has enabled
            enabled_plugins = self.plugin_manager.get_all(server_context)
            for plugin in enabled_plugins:
                if hasattr(plugin, method):
                    discord.utils.create_task(self._run_plugin_event(\
                    plugin, method, *args, **kwargs), loop=self.loop)
        else:
            if hasattr(self, method):
                discord.utils.create_task(self._run_event(method, *args,\
             **kwargs), loop=self.loop)

    def run(self, token):
        self.token = token
        self.headers['authorization'] = token
        self._is_logged_in.set()
        try:
            self.loop.run_until_complete(self.connect())
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.logout())
            pending = asyncio.Task.all_tasks()
            gathered = asyncio.gather(*pending)
            try:
                gathered.cancel()
                self.loop.run_forever()
                gathered.exception()
            except:
                pass
        finally:
            self.loop.close()
