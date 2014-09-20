from webassets import Environment, Bundle, six
from webassets.env import RegisterError, BaseEnvironment
from .package import Package


class Assets(object):
    def __init__(self, env=None, **kwargs):
        if env:
            self.env = env
        else:
            self.env = Environment(**kwargs)
        self.packages = {}

    def register(self, name, *args, **kwargs):
        if isinstance(name, dict) and not args and not kwargs:
            for name, pkg in name.items():
                self.register(name, pkg)
            return

        if len(args) == 1 and not kwargs and isinstance(args[0], (Package, Bundle)):
            item = args[0]
        else:
            if len(args) == 1 and isinstance(args[0], list):
                args = args[0]
            item = Package(*args, **kwargs)

        if name in self.env or name in self.packages:
            raise RegisterError('Another bundle or package is already registered '+
                                'as "%s"' % name)
        elif isinstance(item, Bundle):
            self.env.register(name, item)
        else:
            self.packages[name] = item
            item.env = self

        return item

    def __getitem__(self, name):
        return self.packages[name]

    def __contains__(self, name):
        return name in self.packages