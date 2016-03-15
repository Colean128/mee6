import redis
import asyncio
import logging
from storage import Storage

log = logging.getLogger('discord')

class Db(object):
    def __init__(self, redis_url):
        self.redis_url = redis_url
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def get_storage(self, plugin, server):
        namespace = "{}.{}:".format(
            plugin.__class__.__name__,
            server.id
        )
        storage = Storage.from_url(
            self.redis_url,
            decode_responses=True,
            namespace=namespace
        )

        return storage
