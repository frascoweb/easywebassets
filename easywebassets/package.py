from .asset_types import detect_asset_type, render_asset_html_tags, list_asset_types
from webassets import Bundle, six
from webassets.filter import get_filter


__all__ = ('Package', 'PackageError')


auto_filters = {
    "less": ("less", "css"),
    "coffee": ("coffeescript", "js"),
    "sass": ("sass", "css"),
    "scss": ("scss", "css"),
    "styl": ("stylus", "css")}


class TypedBundle(Bundle):
    def __init__(self, asset_type, *args, **kwargs):
        super(TypedBundle, self).__init__(*args, **kwargs)
        self.asset_type = asset_type
        self.contents = list(self.contents)


class PackageError(Exception):
    pass


class Package(object):
    """A list of mixed-typed bundles and urls
    """
    def __init__(self, *items, **kwargs):
        self._env = kwargs.pop("env", None)
        self.output = kwargs.pop("output", None)
        self.typed_bundles = {}
        self.depends = []
        if items:
            self.append(*items)

    def append(self, *items):
        self._process_items(items)

    def preprend(self, *items):
        self._process_items(items, True)

    def _process_items(self, items, prepend=False):
        for item in items:
            if isinstance(item, (list, tuple)):
                self._process_items(item)
                continue
            if isinstance(item, six.string_types) and item.startswith("@"):
                if prepend:
                    self.depends.insert(0, item[1:])
                else:
                    self.depends.append(item[1:])
                continue
            if isinstance(item, Bundle):
                self._auto_filter_bundle(item)
            elif isinstance(item, dict):
                item = self._create_bundle(item)
            elif not (item.startswith("http://") or item.startswith("https://")):
                item = self._auto_apply_filter(item)

            asset_type = detect_asset_type(item)
            typed_bundle = self.typed_bundles.get(asset_type)
            if not typed_bundle:
                typed_bundle = TypedBundle(asset_type, output=self._make_typed_bundle_output(asset_type))
                self.typed_bundles[asset_type] = typed_bundle
                if self._env:
                    self._webassets_env.add(typed_bundle)
            if prepend:
                typed_bundle.contents.insert(0, item)
            else:
                typed_bundle.contents.append(item)

    def _make_typed_bundle_output(self, asset_type):
        if not self.output:
            return None
        return "%s.%s" % (self.output, asset_type)

    def _yield_bundle_contents(self, data):
        """Yield bundle contents from the given dict.

        Each item yielded will be either a string representing a file path
        or a bundle."""
        if isinstance(data, list):
            contents = data
        else:
            contents = data.get('contents', [])
            if isinstance(contents, six.string_types):
                contents = contents,
        for content in contents:
            if isinstance(content, dict):
                content = self._create_bundle(content)
            yield content

    def _create_bundle(self, data):
        """Return a bundle initialised by the given dict."""
        kwargs = {}
        filters = None
        if isinstance(data, dict):
            kwargs.update(
                filters=data.get('filters', None),
                output=data.get('output', None),
                debug=data.get('debug', None),
                extra=data.get('extra', {}),
                config=data.get('config', {}),
                depends=data.get('depends', None))
        bundle = Bundle(*list(self._yield_bundle_contents(data)), **kwargs)
        return self._auto_filter_bundle(bundle)

    def _auto_filter_bundle(self, bundle):
        def filter_exists(name):
            for f in bundle.filters:
                if f.name == name:
                    return True
            return False

        # checks if all the bundle content has the same file extension
        same_ext = None
        for item in bundle.contents:
            ext = item.rsplit(".", 1)[1]
            if same_ext and (isinstance(item, Bundle) or same_ext != ext):
                same_ext = False
            if same_ext != False:
                same_ext = ext
            if isinstance(item, Bundle):
                self._auto_filter_bundle(item)

        filters = []
        if same_ext in auto_filters and bundle.output:
            f = auto_filters[same_ext][0]
            if not filter_exists(f):
                bundle.filters = list(bundle.filters) + [get_filter(f)]
        else:
            contents = []
            for item in bundle.contents:
                if not isinstance(item, Bundle):
                    item = self._auto_apply_filter(item)
                contents.append(item)
            bundle.contents = contents

        return bundle

    def _auto_apply_filter(self, filename):
        filters = []
        ext = None
        for filter_ext, spec in six.iteritems(auto_filters):
            if filename.rsplit(".", 1)[1] == filter_ext:
                filters.append(spec[0])
                ext = spec[1]
                break
        if not ext:
            return filename
        return Bundle(filename, filters=filters, output="%s.%s" % (filename.rsplit(".", 1)[0], ext))

    @property
    def env(self):
        if not self._env:
            raise PackageError("Package is not bound to any environment")
        return self._env

    @env.setter
    def env(self, env):
        self._env = env
        if env:
            for bundle in self.typed_bundles.itervalues():
                env.env.add(bundle)

    @property
    def _webassets_env(self):
        return self._env.env if self._env else None

    @property
    def asset_types(self):
        return self.typed_bundles.keys()

    def _ref(self, name):
        if not self._env:
            raise PackageError("Package includes references to other bundles but is not bound to an environment")
        return self._env[name]

    def urls_for_depends(self, asset_type, *args, **kwargs):
        urls = []
        for ref in self.depends:
            urls.extend(self._ref(ref).urls_for(asset_type, *args, **kwargs))
        return urls

    def urls_for_self(self, asset_type, *args, **kwargs):
        typed_bundle = self.typed_bundles.get(asset_type)
        if typed_bundle:
            return typed_bundle.urls(*args, **kwargs)
        return []

    def urls_for(self, asset_type, *args, **kwargs):
        """Returns urls needed to include all assets of asset_type
        """
        return self.urls_for_depends(asset_type, *args, **kwargs) + \
               self.urls_for_self(asset_type, *args, **kwargs)

    def html_tags_for(self, asset_type, *args, **kwargs):
        """Return html tags for urls of asset_type
        """
        html = []
        for ref in self.depends:
            html.append(self._ref(ref).html_tags_for(asset_type, *args, **kwargs))
        if asset_type in self.typed_bundles:
            html.append(render_asset_html_tags(asset_type, self.urls_for_self(asset_type, *args, **kwargs)))
        return "\n".join(html)

    def html_tags(self, *args, **kwargs):
        """Return all html tags for all asset_type
        """
        html = []
        for asset_type in list_asset_types():
            html.append(self.html_tags_for(asset_type.name, *args, **kwargs))
        return "\n".join(html)

    def __iter__(self):
        return self.typed_bundles.itervalues()

    def __str__(self):
        return self.html_tags()

    def __repr__(self):
        parts = []
        if self.depends:
            parts.append("depends=%s" % ",".join(self.depends))
        if self.typed_bundles:
            parts.extend(["%s=%s" % (k, repr(v)) for k, v in self.typed_bundles.iteritems()])
        return "<%s(%s)>" % (self.__class__.__name__, ", ".join(parts))
