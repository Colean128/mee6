import discord
import asyncio
import logging
from plugin_manager import PluginManager
from database import Db
from utils import find_server
from time import time

from plugins.commands import Commands
from plugins.help import Help
from plugins.levels import Levels
from plugins.welcome import Welcome
from plugins.animu import AnimuAndMango

log = logging.getLogger('discord')

class Mee6(discord.Client):
    def __init__(self, *args, **kwargs):
        discord.Client.__init__(self, *args, **kwargs)
        self.redis_url = kwargs.get('redis_url')
        self.db = Db(self.redis_url)
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_all()
        self.last_messages = []

    async def on_ready(self):
        with open('welcome_ascii.txt') as f:
            print(f.read())
        self.add_all_servers()
        discord.utils.create_task(self.heartbeat(5), loop=self.loop)
        discord.utils.create_task(self.update_stats(60), loop=self.loop)
        await self.change_status(game=discord.Game(name='http://mee6.xyz'))

    def add_all_servers(self):
        log.debug('Syncing servers and db')
        self.db.redis.delete('servers')
        for server in self.servers:
            log.debug('Adding server {}\'s id to db'.format(server.id))
            self.db.redis.sadd('servers', server.id)

    @asyncio.coroutine
    def send_message(self, *args, **kwargs):
        dest = args[0]
        if hasattr(args[0], 'server'):
            dest = args[0].server
        if isinstance(args[0], discord.Member):
            dest = args[0]
        log.info('Mee6@{} >> {}'.format(dest.name,args[1].replace('\n', '~')))
        yield from super().send_message(*args, **kwargs)

    @asyncio.coroutine
    def on_server_join(self, server):
        log.info('Joined {} server : {} !'.format(server.owner.name, server.name))
        log.debug('Adding server {}\'s id to db'.format(server.id))
        self.db.redis.sadd('servers', server.id)
        self.db.redis.set('server:{}:name'.format(server.id), server.name)
        if server.icon:
            self.db.redis.set('server:{}:icon'.format(server.id), server.icon)

    @asyncio.coroutine
    def on_server_remove(self, server):
        log.info('Leaving {} server : {} !'.format(server.owner.name, server.name))
        log.debug('Removing server {}\'s id from the db'.format(server.id))
        self.db.redis.srem('servers', server.id)

    @asyncio.coroutine
    def heartbeat(self, interval):
        while self.is_logged_in:
            self.db.redis.set('heartbeat', 1, ex=interval)
            yield from asyncio.sleep(0.9 * interval)

    @asyncio.coroutine
    def update_stats(self, interval):
        while self.is_logged_in:
            # Total members and online members
            members = list(self.get_all_members())
            online_members = filter(lambda m: m.status is discord.Status.online, members)
            online_members = list(online_members)
            self.db.redis.set('mee6:stats:online_members', len(online_members))
            self.db.redis.set('mee6:stats:members', len(members))

            # Last messages
            for index, timestamp in enumerate(self.last_messages):
                if timestamp + interval < time():
                    self.last_messages.pop(index)
            self.db.redis.set('mee6:stats:last_messages', len(self.last_messages))

            yield from asyncio.sleep(interval)

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

    async def on_message(self, message):
        mee6_server_id = "159962941502783488"
        update_channel_id = "160784396679380992"
        if not hasattr(message, 'server'):
            return
        if (message.server.id, message.channel.id) == (mee6_server_id, update_channel_id):
            owners = set(server.owner for server in self.servers)
            for owner in owners:
                await self.send_message(
                    owner,
                    message.content
                )

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

        # Total number of messages stats update
        if event=='message':
            self.db.redis.incr('mee6:stats:messages')
            self.last_messages.append(time())
            if hasattr(self, method):
                discord.utils.create_task(self._run_event(method, *args,\
             **kwargs), loop=self.loop)

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
