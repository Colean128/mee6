def find_server(*args, **kwargs):
    for arg in args:
        if hasattr(arg, 'server'):
            return arg.server
    for key, value in kwargs.items():
        if hasattr(value, 'server'):
            return arg.server
