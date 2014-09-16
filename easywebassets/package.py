from .asset_types import detect_asset_type, render_asset_html_tags
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


class PackageRef(object):
    """A reference to another package
    """
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "@%s" % self.name


class PackageError(Exception):
    pass


class Package(object):
    """A list of mixed-typed bundles and urls
    """
    def __init__(self, *items, **kwargs):
        self._items = []
        self._env = kwargs.pop("env", None)
        self._current_typed_bundles = {}
        if items:
            self.append(*items)

    def append(self, *items):
        self._items.extend(self._process_items(items, self._current_typed_bundles))

    def preprend(self, *items):
        self._items = list(self._process_items(items, {}), *self._items)

    def _process_items(self, items, current_typed_bundles):
        processed_items = []
        for item in items:
            if isinstance(item, (list, tuple)):
                item = Package(*item)
            elif isinstance(item, six.string_types) and item.startswith("@"):
                item = PackageRef(item[1:])
            if isinstance(item, (Package, PackageRef)):
                item.env = self._env
                processed_items.append(item)
                current_typed_bundles.clear()
                continue
            if isinstance(item, Bundle):
                self._auto_filter_bundle(item)
            elif isinstance(item, dict):
                item = self._create_bundle(item)
            elif not (item.startswith("http://") or item.startswith("https://")):
                item = self._auto_apply_filter(item)

            asset_type = detect_asset_type(item)
            typed_bundle = current_typed_bundles.get(asset_type)
            if not typed_bundle:
                typed_bundle = TypedBundle(asset_type, env=self._webassets_env)
                current_typed_bundles[asset_type] = typed_bundle
                processed_items.append(typed_bundle)
            typed_bundle.contents.append(item)

        return processed_items

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
        """auto applies minfication filters, less filter and coffeescript filter
        Process:
          1. checks if all files are of the same type (ie. of type less or coffee). sub-bundles disqualify all files
          2. checks if some files are already minified (ie. the extension is either .min.css or .min.js).
             sub-bundles disqualify all files
          3. applies _auto_filter_bundle() on sub-bundles
          4. checks if the bundle's output contains a minified extension (ie. .min.css or .min.js)
          5. if the bundle needs to be minified and none of its content is already minified, the appropriate
             minification filter is applied to the whole bundle
          6. if all files are either coffee or less files, applies the appropriate filter on the bundle
          7. if not all files are of the same type, checks each files independently using _auto_apply_filter()
        """
        def minified(filename):
            if filename:
                if filename.endswith(".min.js"):
                    return "jsmin"
                elif filename.endswith(".min.css"):
                    return "cssmin"
            return False

        # checks if all the bundle content has the same file extension and
        # if all the contents needs to be minified
        same_ext = None
        minify_all = True
        for item in bundle.contents:
            ext = item.rsplit(".", 1)[1]
            if same_ext and (isinstance(item, Bundle) or same_ext != ext):
                same_ext = False
            if same_ext != False:
                same_ext = ext
            if minify_all and (isinstance(item, Bundle) or minified(item)):
                minify_all = False
            if isinstance(item, Bundle):
                self._auto_filter_bundle(item)

        filters = []
        minify = minified(bundle.output)
        if minify_all and minify:
            filters.append(minify)

        if same_ext in auto_filters and bundle.output:
            filters.append(auto_filters[same_ext][0])
        else:
            contents = []
            for item in bundle.contents:
                if not isinstance(item, Bundle):
                    item = self._auto_apply_filter(item, not minify_all and minify)
                    if not isinstance(item, Bundle) and not minify_all and minify and not minified(item):
                        item = Bundle(item, filters=minify, output="%s.min.%s" % tuple(item.rsplit(".", 1)))
                contents.append(item)
            bundle.contents = contents

        def filter_exists(name):
            for f in bundle.filters:
                if f.name == name:
                    return True
            return False

        bundle.filters = list(bundle.filters)
        for f in filters:
            if not filter_exists(f):
                bundle.filters.append(get_filter(f))

        return bundle

    def _auto_apply_filter(self, filename, with_min=True):
        filters = []
        ext = None
        for filter_ext, spec in six.iteritems(auto_filters):
            if filename.rsplit(".", 1)[1] == filter_ext:
                filters.append(spec[0])
                ext = spec[1]
                break
        if not ext:
            return filename
        if with_min and ext in ("css", "js"):
            filters.append("%smin" % ext)
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
            for item in self._items:
                if isinstance(item, Bundle):
                    item.env = env.env
                else:
                    item.env = env

    @property
    def _webassets_env(self):
        return self._env.env if self._env else None

    @property
    def items(self):
        """Returns all items in the package. If there are PackageRef's,
        they will be resolved using self.env
        """
        for item in self._items:
            if isinstance(item, PackageRef):
                if not self._env:
                    raise PackageError("Package includes references to other bundles but is not bound to an environment")
                yield self._env[item.name]
            else:
                yield item

    @property
    def asset_types(self):
        types = set()
        for item in self.items:
            if isinstance(item, Package):
                types.update(item.asset_types)
            else:
                types.add(item.asset_type)
        return list(types)

    def urls_for(self, asset_type, *args, **kwargs):
        """Returns urls needed to include all assets of asset_type
        """
        urls = []
        for item in self.items:
            if isinstance(item, Package):
                urls.extend(item.urls_for(asset_type, *args, **kwargs))
            elif not asset_type or item.asset_type == asset_type:
                urls.extend(item.urls(*args, **kwargs))
        return urls

    def urls(self, *args, **kwargs):
        """Returns a generator of tuples (asset_type, urls)
        """
        return self.urls_for(None, *args, **kwargs)

    def html_tags_for(self, asset_type, *args, **kwargs):
        """Return html tags for urls of asset_type
        """
        return render_asset_html_tags(asset_type, self.urls_for(asset_type, *args, **kwargs))

    def html_tags(self, *args, **kwargs):
        """Return all html tags for all asset_type
        """
        html = []
        for asset_type in self.asset_types:
            html.append(self.html_tags_for(asset_type, *args, **kwargs))
        return "\n".join(html)

    def __iter__(self):
        return iter(self.items)

    def __str__(self):
        return self.html_tags()

    def __repr__(self):
        return "<%s(%s)>" % (self.__class__.__name__, ", ".join(map(repr, self._items if not self._env else self.items)))
