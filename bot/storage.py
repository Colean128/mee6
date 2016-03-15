from redis import Redis
from redis import ConnectionPool
from functools import wraps
import inspect

def prefixer(function, pref_type):
    if pref_type == 'name':
        @wraps(function)
        def wrapper(self, *args, **kwargs):
            return function(self, self.namespace + args[0], *(args[1:]), **kwargs)
        return wrapper
    elif pref_type == 'names':
        @wraps(function)
        def wrapper(self, *args, **kwargs):
            args = list(map(lambda name: self.namespace + name, args))
            return function(self, *args, **kwargs)
        return wrapper
    elif pref_type == 'src/dst':
        @wraps(function)
        def wrapper(self, *args, **kwargs):
            return function(self, self.namespace + args[0], self.namespace + args[1], *(args[2:]), **kwargs)
        return wrapper
    elif pref_type == 'keys':
        @wraps(function)
        def wrapper(self, *args, **kwargs):
            args = list(map(lambda name: self.namespace + name, args))
            return function(self, *args, **kwargs)
        return wrapper


def prefix_methods(cls):
    for attr, value in inspect.getmembers(cls.__bases__[0]):
        method = value
        if inspect.isfunction(method):
            args = inspect.getargspec(method)[0]
            varargs = inspect.getargspec(method)[1]
            if len(args)>1 and args[1] == 'name':
                setattr(cls, attr, prefixer(method, 'name'))
            elif varargs == 'names':
                setattr(cls, attr, prefixer(method, 'names'))
            elif 'src' in args and 'dst' in args:
                setattr(cls, attr, prefixer(method, 'src/dst'))
            elif len(args)>1 and args[1] == 'keys':
                setattr(cls, attr, prefixer(method, 'keys'))
    return cls

@prefix_methods
class Storage(Redis):
    def __init__(self, *args, **kwargs):
        self.namespace = kwargs.pop('namespace')
        Redis.__init__(self, *args, **kwargs)

    @classmethod
    def from_url(cls, url, db=None, **kwargs):
        namespace = kwargs.pop('namespace')
        connection_pool = ConnectionPool.from_url(url, db=db, **kwargs)
        return cls(connection_pool=connection_pool, namespace=namespace)
