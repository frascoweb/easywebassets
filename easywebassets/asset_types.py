import types
from webassets import six, Bundle


__all__ = ('UnknownAssetTypeError', 'detect_asset_type',
           'asset_type', 'render_asset_tags')


_asset_types = {}


class UnknownAssetTypeError(Exception):
    pass


class AssetType(object):
    name = None
    file_exts = None
    template = None

    def __init__(self, name=None, file_exts=None, template=None):
        if name:
            self.name = name
        if file_exts:
            self.file_exts = file_exts
        if template:
            self.template = template

    def match(self, filename):
        ext = filename.rsplit(".", 1)[1]
        if self.file_exts and ext in self.file_exts:
            return True
        return False

    def render(self, url):
        if self.template:
            return self.template.format([url])
        return ""


def asset_type(name=None, exts=None):
    def decorator(f):
        n = name or f.__name__
        if isinstance(f, types.ClassType):
            _asset_types[n] = f
        else:
            atype = AssetType(n, exts or [n])
            atype.render = f
            _asset_types[n] = atype
        return f
    return decorator


def list_asset_types():
    return six.itervalues(_asset_types)


def get_asset_type(name):
    if name not in _asset_types:
        raise UnknownAssetTypeError("Unknown asset type '%s'" % name)
    return _asset_types[name]


def detect_asset_type(filename):
    if isinstance(filename, Bundle):
        return detect_bundle_asset_type(filename)
    for name, atype in six.iteritems(_asset_types):
        if atype.match(filename):
            return name
    raise UnknownAssetTypeError("Cannot detect type of asset '%s'" % filename)


def detect_bundle_asset_type(bundle):
    for filename in bundle.contents:
        try:
            return detect_asset_type(filename)
        except UnknownAssetTypeError:
            continue
    raise UnknownAssetTypeError("Cannot detect the type of assets in a bundle")


def render_asset_html_tags(asset_type, urls):
    if asset_type not in _asset_types:
        raise UnknownAssetTypeError("Unknown type '%s' when rendering assets" % asset_type)
    html = []
    for url in urls:
        html.append(_asset_types[asset_type].render(url))
    return "\n".join(html)


@asset_type("css", exts=["css", "less", "scss", "sass", "styl"])
def render_css_tag(url):
    return '<link rel="stylesheet" type="text/css" href="%s">' % url


@asset_type("js", exts=["js", "coffee", "jst"])
def render_js_tag(url):
    return '<script type="text/javascript" src="%s"></script>' % url
