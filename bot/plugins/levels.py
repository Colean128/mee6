from plugin import Plugin
import logging
import asyncio
from random import randint
log = logging.getLogger('discord')

class Levels(Plugin):

    fancy_name = 'Levels'

    def get_commands(self, server):
        commands = [
            {
                'name': '!levels',
                'description': 'Gives you the server leaderboard.'
            },
            {
                'name': '!rank',
                'description': 'Gives you your xp, level and rank.'
            }
        ]
        return commands

    @staticmethod
    def _get_level_xp(n):
        return 100*(1.2**n)

    @staticmethod
    def _get_level_from_xp(xp):
        remaining_xp = int(xp)
        level = 0
        while remaining_xp >= Levels._get_level_xp(level):
            remaining_xp -= Levels._get_level_xp(level)
            level += 1
        return level

    @asyncio.coroutine
    def on_message(self, message):
        if message.author.id == self.mee6.user.id:
            return

        if message.content == '!levels':
            url = 'http://mee6.xyz/levels/{}'.format(message.server.id)
            response = 'Go check **{}**\'s leaderboard here : {} ! :wink:'.format(
                message.server.name,
                url
            )
            yield from self.mee6.send_message(message.channel, response)
            return

        if message.content == '!rank':
            storage = self.get_storage(message.server)
            player = message.author
            players = storage.smembers('players')
            if player.id not in players:
                yield from self.mee6.send_message(message.channel,
                    '{}, It seems like you are not ranked. Start talking in the chat to get ranked :wink:.'.format(
                        player.mention
                    )
                )
                return

            player_xp = storage.get('player:{}:xp'.format(player.id))
            player_lvl = storage.get('player:{}:lvl'.format(player.id))
            player_rank = storage.sort('players', by='players:*:xp').index(player.id)+1

            response = '{} : **LEVEL {}** / **TOTAL XP {}** / **Rank {}/{}**'.format(
                player.mention,
                player_lvl,
                player_xp,
                player_rank,
                len(players)
            )

            yield from self.mee6.send_message(message.channel, response)
            return

        storage = self.get_storage(message.server)

        # Updating player's profile
        player = message.author
        server = message.server
        self.mee6.db.redis.set('server:{}:name'.format(server.id), server.name)
        if server.icon:
            self.mee6.db.redis.set('server:{}:icon'.format(server.id), server.icon)
        if server.icon:
            storage.sadd('server:icon', server.icon)
        storage.sadd('players', player.id)
        storage.set('player:{}:name'.format(player.id), player.name)
        storage.set('player:{}:discriminator'.format(player.id), player.discriminator)
        storage.set('player:{}:avatar'.format(player.id), player.avatar)

        # Is the player good to go ?
        check = storage.get('player:{}:check'.format(player.id))
        if check:
            return

        # Get the player lvl
        lvl = storage.get('player:{}:lvl'.format(player.id))
        if lvl is None:
            storage.set('player:{}:lvl'.format(player.id), 0)
            lvl = 0
        else:
            lvl = int(lvl)

        # Give random xp between 5 and 10
        storage.incr('player:{}:xp'.format(player.id), amount=randint(5,10))
        # Block the player for 60 sec (that's 1 min btw...)
        storage.set('player:{}:check'.format(player.id), '1', ex=60)
        # Get the new player xp
        player_xp = storage.get('player:{}:xp'.format(player.id))
        # Update the level
        storage.set('player:{}:lvl'.format(player.id), Levels._get_level_from_xp(player_xp))
        # Comparing the level before and after
        new_level = int(storage.get('player:{}:lvl'.format(player.id)))
        if new_level != lvl:
            # Check if announcement is good
            announcement_enabled = storage.get('announcement_enabled')
            if announcement_enabled:
                announcement = storage.get('announcement')
                yield from self.mee6.send_message(message.channel, announcement.format(
                    player = player.mention,
                    level = new_level
                ))
