# -*- coding: utf-8 -*-

# --------------------------------------------------------------------
# The MIT License (MIT)
#
# Copyright (c) 2014 Jonathan Labéjof <jonathan.labejof@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# --------------------------------------------------------------------

"""Specification of the class Configurable."""

__all__ = ['Configurable']

from six import string_types
from six.moves import reload_module

from inspect import getargspec, isclass

from b3j0f.utils.path import lookup
from b3j0f.utils.version import getcallargs

from b3j0f.annotation import PrivateInterceptor

from ..model.conf import Configuration, configuration
from ..model.cat import Category, category
from ..model.param import Parameter
from ..driver.file.json import JSONFileConfDriver
from ..driver.file.ini import INIFileConfDriver
from ..driver.file.xml import XMLFileConfDriver
from ..parser.resolver.core import (
    DEFAULT_SAFE, DEFAULT_SCOPE, DEFAULT_BESTEFFORT
)

__CONFIGURABLES__ = '__configurables__'


class Configurable(PrivateInterceptor):
    """Manage class conf synchronisation with conf resources.

    According to critical parameter updates, this class uses a dirty state.

    In such situation, it is possible to go back to a stable state in calling
    the method `restart`. Without failure, the dirty status is canceled."""

    CATEGORY = 'CONFIGURABLE'  #: configuration category name.

    CONF = 'conf'  #: self configuration attribute name.

    CONFPATHS = 'paths'  #: paths attribute name.
    DRIVERS = 'drivers'  #: drivers attribute name.
    INHERITEDCONF = 'inheritedconf'  #: usecls conf attribute name.
    CONFPATH = 'confpath'  #: conf path attribute name.
    STORE = 'store'  #: store attribute name.
    FOREIGNS = 'foreigns'  #: not specified params setting attribute name.
    AUTOCONF = 'autoconf'  #: auto conf attribute name.
    SAFE = 'safe'  #: safe attribute name.
    SCOPE = 'scope'  #: scope attribute name.
    BESTEFFORT = 'besteffort'  #: best effort attribute name.

    DEFAULT_CONFPATHS = ('b3j0fconf-configurable.conf', )  #: default conf path.
    DEFAULT_INHERITEDCONF = True  #: default inheritedconf value.
    DEFAULT_STORE = True  #: default store value.
    DEFAULT_FOREIGNS = True  #: default value for setting not specified params.
    # default drivers which are json and ini.
    DEFAULT_DRIVERS = (
        JSONFileConfDriver(), INIFileConfDriver(), XMLFileConfDriver()
    )
    DEFAULT_AUTOCONF = True  #: default value for auto configuration.

    SUB_CONF_PREFIX = ':'  #: sub conf prefix.

    def __init__(
            self,
            conf=None, inheritedconf=DEFAULT_INHERITEDCONF, confpath=None,
            store=DEFAULT_STORE, paths=None, drivers=DEFAULT_DRIVERS,
            foreigns=DEFAULT_FOREIGNS, autoconf=DEFAULT_AUTOCONF,
            toconfigure=(), safe=DEFAULT_SAFE, scope=DEFAULT_SCOPE,
            besteffort=DEFAULT_BESTEFFORT, modules=None, callparams=True,
            *args, **kwargs
    ):
        """
        :param Configuration conf: conf to use at instance level.
        :param bool inheritedconf: if True (default) add conf and paths to cls
            conf and paths.
        :param str confpath: instance configuration path.
        :param toconfigure: object(s) to reconfigure. Such object may
            implement the methods configure applyconfiguration and configure.
        :type toconfigure: list or instance.
        :param bool store: if True (default) and toconfigure is given,
            store this instance into toconfigure instance with the attribute
            ``STORE_ATTR``.
        :param paths: paths to parse.
        :type paths: Iterable or str
        :param bool foreigns: if True (default), set parameters not specified by
            this conf but given by conf resources.
        :param ConfDriver(s) drivers: list of drivers to use. Default
            Configurable.DEFAULT_DRIVERS.
        :param list toconfigure: objects to configure.
        :param bool autoconf: if autoconf, configurate this `toconfigure`
            objects as soon as possible. (at toconfigure instanciation or after
            updating this paths/conf/toconfigure).
        :param bool safe: if True (default), expression parser are used in a
            safe context to resolve python object. For example, if safe,
            builtins function such as `open` are not resolvable.
        :param dict scope: expression resolver scope.
        :param bool besteffort: expression resolver best effort flag.
        :param list modules: required modules.
        :param bool callparams: if True (default), use parameters in the
            configured callable function."""

        super(Configurable, self).__init__(*args, **kwargs)

        # init protected attributes
        self._paths = None
        self._conf = None
        self._toconfigure = []
        self._confpath = confpath
        self._modules = []

        # init public attributes
        self.store = store

        self.inheritedconf = inheritedconf
        self.drivers = drivers
        self.foreigns = foreigns
        self.toconfigure = toconfigure
        # dirty hack: falsify autoconf in order to avoid auto applyconfiguration
        self.autoconf = False
        self.conf = conf
        self.confpath = confpath
        self.paths = paths
        self.safe = safe
        self.scope = scope
        self.besteffort = besteffort
        self.autoconf = autoconf  # end of dirty hack
        self.modules = modules
        self.callparams = callparams

    def _interception(self, joinpoint):

        if self.callparams:

            conf = self.conf

            params = conf.params.values()

            args, kwargs = joinpoint.args, joinpoint.kwargs

            target = joinpoint.target

            try:
                argspec = getargspec(target)

            except TypeError:
                argspec = None
                callargs = None

            else:
                callargs = getcallargs(
                    target, args, kwargs
                )

            for param in params:

                if argspec is None:
                    args.append(param.value)

                elif param.name not in callargs and (
                        param.name in argspec.args or self.foreigns
                ):

                    kwargs[param.name] = param.value

        toconfigure = result = joinpoint.proceed()

        if self.autoconf:

            if isclass(target):

                if toconfigure is None:
                    if 'self' in kwargs:
                        toconfigure = kwargs['self']

                    else:
                        toconfigure = args[0]

                if isinstance(toconfigure, target):

                    self.toconfigure += [toconfigure]

                    self.applyconfiguration(toconfigure=toconfigure)

        return result

    @property
    def modules(self):
        """Get this required modules."""

        return self._modules

    @modules.setter
    def modules(self, value):
        """Change required modules.

        Reload modules given in the value.

        :param list value: new modules to use."""

        self._modules = value
        if value:
            for module in value:
                reload_module(lookup(module))

    @property
    def confpath(self):
        """Get configuration path.

        :rtype: str"""

        return self._confpath

    @confpath.setter
    def confpath(self, value):
        """Change of configuration path.

        :param str value: new conf path to use."""

        if value is None:
            value = ''

        conf = self.getconf(paths=value)
        # force to get parameters if values are parameters
        for cat in conf.values():
            for param in cat.values():
                if isinstance(param.value, Parameter):
                    conf[cat.name] = param.value

        self.conf = conf

    @property
    def toconfigure(self):
        """Get this toconfigure objects.

        :rtype: list"""

        return self._toconfigure

    @toconfigure.setter
    def toconfigure(self, value):
        """Change of objects to configure."""

        if type(value) in (set, tuple):  # transform value

            value = list(value)

        elif type(value) is not list:
            value = [value]

        excluded = set(value) - set(self._toconfigure)

        for exclude in excluded:  # clean old references
            try:
                configurables = getattr(exclude, __CONFIGURABLES__)

            except AttributeError:
                pass

            else:
                if self in configurables:
                    configurables.remove(self)

                if not configurables:
                    delattr(exclude, __CONFIGURABLES__)

        if self.store:  # if store, save self in toconfigure elements

            for to_conf in value:

                configurables = getattr(to_conf, __CONFIGURABLES__, [])

                if self not in configurables:
                    configurables.append(self)

                try:
                    setattr(to_conf, __CONFIGURABLES__, configurables)

                except AttributeError:
                    pass

        self._toconfigure = value

    @property
    def conf(self):
        """Get conf with parsers and self property values.

        :rtype: Configuration.
        """

        return self._conf

    @conf.setter
    def conf(self, value):
        """Change of configuration.

        :param value: new configuration to use.
        :type value: Category or Configuration
        """

        if value is None:
            value = Configuration()

        elif isinstance(value, Category):
            value = Configuration(value)

        if self.inheritedconf:
            self._conf = self.clsconf()
            self._conf.update(value)

        else:
            self._conf = value

        if self.autoconf:
            self.applyconfiguration()

    @classmethod
    def clsconf(cls):
        """Method to override in order to specify class configuration."""

        result = configuration(
            category(
                Configurable.CATEGORY,
                Parameter(name=Configurable.CONF, ptype=Configuration),
                Parameter(name=Configurable.DRIVERS, ptype=tuple),
                Parameter(name=Configurable.CONFPATHS, ptype=tuple),
                Parameter(name=Configurable.INHERITEDCONF, ptype=bool),
                Parameter(name=Configurable.STORE, ptype=bool),
                Parameter(name=Configurable.SCOPE, ptype=dict),
                Parameter(name=Configurable.SAFE, ptype=bool),
                Parameter(name=Configurable.BESTEFFORT, ptype=bool)
            )
        )

        return result

    @property
    def paths(self):
        """Get all type conf files and user files.

        :return: self conf files
        :rtype: tuple
        """

        result = tuple(self._paths)

        return result

    @paths.setter
    def paths(self, value):
        """Change of paths in adding it in watching list."""

        if value is None:
            value = ()

        elif isinstance(value, string_types):
            value = (value, )

        if self.inheritedconf:
            self._paths = self.clspaths() + tuple(value)

        else:
            self._paths = tuple(value)

        if self.autoconf:
            self.applyconfiguration()

    def clspaths(self):
        """Get class paths."""

        return tuple(self.DEFAULT_CONFPATHS)

    def applyconfiguration(
            self, conf=None, paths=None, drivers=None, logger=None,
            toconfigure=None, scope=None, safe=None, besteffort=None
    ):
        """Apply conf on a destination in those phases:

        1. identify the right driver to use with paths to parse.
        2. for all paths, get conf which matches input conf.
        3. apply parsing rules on path parameters.
        4. fill input conf with resolved parameters.
        5. apply filled conf on toconfigure.

        :param Configuration conf: conf from where get conf.
        :param paths: conf files to parse. If paths is a str, it is
            automatically putted into a list.
        :type paths: list of str
        :param toconfigure: object to configure. self by default.
        :param dict scope: local variables to use for expression resolution.
        """

        if scope is None:
            scope = self.scope

        if safe is None:
            safe = self.safe

        if besteffort is None:
            besteffort = self.besteffort

        if toconfigure is None:  # init toconfigure
            toconfigure = self.toconfigure

        if type(toconfigure) is list:

            for target in toconfigure:

                self.applyconfiguration(
                    conf=conf, paths=paths, drivers=drivers,
                    logger=logger, toconfigure=target, scope=scope, safe=safe,
                    besteffort=besteffort
                )

        else:
            # get conf from drivers and paths
            conf = self.getconf(
                conf=conf, paths=paths, logger=logger, drivers=drivers
            )
            # resolve all values
            conf.resolve(
                configurable=self,
                scope=scope, safe=safe, besteffort=besteffort
            )
            # configure resolved configuration
            self.configure(conf=conf, toconfigure=toconfigure)

    def getconf(self, conf=None, paths=None, drivers=None, logger=None):
        """Get a configuration from paths.

        :param Configuration conf: conf to update. Default this conf.
        :param str(s) paths: list of conf files. Default this paths.
        :param Logger logger: logger to use for logging info/error messages.
        :param list drivers: ConfDriver to use. Default this drivers.
        """

        result = None

        # start to initialize input params
        if conf is None:
            conf = self.conf

        if paths is None:
            paths = self.paths

        if isinstance(paths, string_types):
            paths = [paths]

        if drivers is None:
            drivers = self.drivers

        # iterate on all paths
        for path in paths:

            for driver in drivers:  # find the best driver

                rscconf = driver.getconf(
                    path=path, conf=conf, logger=logger
                )

                if rscconf is None:
                    continue

                if result is None:
                    result = rscconf

                else:
                    result.update(conf=rscconf)

            if result is None:
                # if no conf found, display a warning log message
                if logger is not None:
                    logger.warning(
                        'No driver found among {0} for processing {1}'.format(
                            drivers, path
                        )
                    )

        return result

    def configure(self, conf=None, toconfigure=None, logger=None):
        """Apply input conf on toconfigure objects.

        Specialization of this method is done in the _configure method.

        :param Configuration conf: configuration model to configure. Default is
            this conf.
        :param toconfigure: object to configure. self if equals None.
        :param Logger logger: specific logger to use.
        :raises: Parameter.Error for any raised exception.
        """

        if conf is None:
            conf = self.conf

        if toconfigure is None:  # init toconfigure
            toconfigure = self.toconfigure

        if type(toconfigure) is list:

            for toconfigure in toconfigure:

                self.configure(
                    conf=conf, toconfigure=toconfigure, logger=logger
                )

        else:

            self._configure(conf=conf, logger=logger, toconfigure=toconfigure)

    def _configure(self, conf=None, logger=None, toconfigure=None):
        """Configure this class with input conf only if auto_conf or
        configure is true.

        This method should be overriden for specific conf

        :param Configuration conf: configuration model to configure. Default is
            this conf.
        :param bool configure: if True, force full self conf
        :param toconfigure: object to configure. self if equals None.
        """

        if conf is None:
            conf = self.conf

        if toconfigure is None:  # init toconfigure
            toconfigure = self.toconfigure

        if type(toconfigure) is list:

            for toconfigure in toconfigure:

                self._configure(
                    conf=conf, logger=logger, toconfigure=toconfigure
                )

        else:

            sub_confs = []
            params = []

            for cat in conf.values():
                if cat.name.startswith(self.SUB_CONF_PREFIX):
                    sub_confs.append(cat.name)

                else:
                    cparams = cat.params
                    params += cparams.values()

                    for param in cparams.values():

                        value = param.value

                        if param.error:
                            continue

                        if self.foreigns or param.local:
                            setattr(toconfigure, param.name, value)

            for param in params:

                sub_conf_name = '{0}{1}'.format(self.SUB_CONF_PREFIX, param.name)

                if sub_conf_name in sub_confs:

                    cat = sub_confs[sub_conf_name]

                    kwargs = {}

                    for param in cat.params:

                        kwargs[param.name] = param.value

                    value = param.value(**kwargs)

                    self._configure(
                        toconfigure=value, logger=logger, conf=value
                    )


def getconfigurables(toconfigure):
    """Get configurables attached to input toconfigure.

    :rtype: list"""

    return getattr(toconfigure, __CONFIGURABLES__, [])


def applyconfiguration(toconfigure, *args, **kwargs):
    """Apply configuration on input toconfigure.

    :param tuple args: applyconfiguration var args.
    :param dict kwargs: applyconfiguration keywords.
    """

    configurables = getconfigurables(toconfigure)

    for configurable in configurables:

        configurable.applyconfiguration(
            toconfigure=toconfigure, *args, **kwargs
        )
