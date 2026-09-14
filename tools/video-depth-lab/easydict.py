class EasyDict(dict):
    """Minimal attribute-access dictionary used by the bundled VDA runtime."""

    __getattr__ = dict.__getitem__

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        del self[key]
