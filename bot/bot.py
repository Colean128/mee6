from mee6 import Mee6
import os
import logging

logging.basicConfig(level=logging.INFO)

token = os.getenv('MEE6_TOKEN')
redis_url = os.getenv('REDIS_URL')
mee6_debug = os.getenv('MEE6_DEBUG')

if mee6_debug:
    logging.basicConfig(level=logging.DEBUG)

bot = Mee6(redis_url=redis_url)
bot.run(token)
