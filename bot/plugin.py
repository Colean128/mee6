class PluginMount(type):

    def __init__(cls, name, bases, attrs):
        """Called when a Plugin derived class is imported"""

        if not hasattr(cls, 'plugins'):
            cls.plugins = []
        else:
            cls.plugins.append(cls)

class Plugin(object, metaclass=PluginMount):

    def __init__(self, mee6):
        self.mee6 = mee6
        self.db = mee6.db

    def get_storage(self, server):
        return self.mee6.db.get_storage(self, server)

    def key(self, k):
        prefix = '{0.__class__.__name__}.{1}:'.format(self, server.id)
