from plugin import Plugin
import logging
import asyncio
import os
from xml.etree import ElementTree
import re
import aiohttp
import html

log = logging.getLogger('discord')
MAL_USERNAME = os.getenv('MAL_USERNAME')
MAL_PASSWORD = os.getenv('MAL_PASSWORD')

class AnimuAndMango(Plugin):

    fancy_name = 'Animu and Mango'

    def get_commands(self, server):
        commands = [
            {
                'name': '!animu <animu_name>',
                'description': 'Gives you information about an animu.'
            },
            {
                'name': '!mango <mango_name>',
                'description': 'Gives you information about a mango.'
            }
        ]
        return commands

    async def get_xml(self, nature, name):
        auth = aiohttp.BasicAuth(login = MAL_USERNAME, password = MAL_PASSWORD)
        url = 'http://myanimelist.net/api/{}/search.xml'.format(nature)
        params = {
            'q': name
        }
        with aiohttp.ClientSession(auth=auth) as session:
            async with session.get(url, params=params) as response:
                data = await response.text()
                return data


    async def on_message(self, message):

        rule = r'!(animu|mango) (.*)'
        check = re.match(rule, message.content)

        if check is None:
            return

        log.info('{}#{}@{} >> {}'.format(
            message.author.name,
            message.author.discriminator,
            message.server.name,
            message.content
        ))

        nature, name = check.groups()

        switcher = {'animu': 'anime', 'mango': 'manga'}
        nature = switcher[nature]

        data = await self.get_xml(nature, name)
        if data == '':
            await self.mee6.send_message(
                message.channel,
                'I didn\'t found anything :cry: ...'
            )
            return

        root = ElementTree.fromstring(data)
        if len(root) == 0:
            await self.mee6.send_message(
                message.channel,
                'Sorry, I found nothing :cry:.'
            )
        elif len(root) == 1:
            entry = root[0]
        else:
            msg = "**Please choose one by giving its number.**\n"
            msg += "\n".join([ '{} - {}'.format(n+1, entry[1].text) for n, entry in enumerate(root) if n < 10 ])

            await self.mee6.send_message(message.channel, msg)

            check = lambda m: m.content in map(str, range(1, len(root)+1))
            resp = await self.mee6.wait_for_message(
                author = message.author,
                check = check,
                timeout = 20
            )
            if resp is None:
                return

            entry = root[int(resp.content)-1]

        switcher = [
            'english',
            'score',
            'type',
            'episodes',
            'volumes',
            'chapters',
            'status',
            'start_date',
            'end_date',
            'synopsis'
            ]

        msg = '\n**{}**\n\n'.format(entry.find('title').text)
        for k in switcher:
            spec = entry.find(k)
            if spec is not None and spec.text is not None:
                msg += '**{}** {}\n'.format(k.capitalize()+':', html.unescape(spec.text.replace('<br />', '')))
        msg += 'http://myanimelist.net/{}/{}'.format(nature, entry.find('id').text)

        await self.mee6.send_message(
            message.channel,
            msg
        )
