#!/usr/bin/env python
#
# __init__.py - Accessing installed FSLeyes plugins.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This package provides access to installed and built-in FSLeyes plugins.


FSLeyes uses a simple plugin architecture for loading custom views, controls,
and tools. Plugins can be installed from Python libraries (e.g. as hosted on
`PyPi <https://pypi.org/>`_), or installed directly from a ``.py`` file.


In both cases, FSLeyes uses ``setuptools`` `entry points
<https://setuptools.readthedocs.io/en/latest/pkg_resources.html#entry-points>`__
to locate the items provided by plugin library/files.


Things plugins can provide
--------------------------


FSLeyes plugins can provide custom *views*, *controls* and *tools*:

 - A *view* is a top level panel, such as an :class:`.OrthoPanel`,
   :class:`.Scene3DPanel`, or :class:`.TimeSeriesPanel`. Views provided
   by plugins are added to the top level *Views* menu.

 - A *control* is a secondary panel, or toolbar, which is embedded within a
   view, such as an :class:`.OverlayListPanel`, :class:`.OrthoToolBar`, or
   :class:`.MelodicClassificationPanel`. Controls provided by plugins are
   added to the *Settings* menu for each active view.

 - A *tool* is an :class:`.Action` which is associated with a menu item
   under the top-level *Tools* menu, such as the :class:`.ApplyFlirtXfmAction`
   and the :class:`.ResampleAction`.


Loading/installing FSLeyes plugins
----------------------------------


FSLeyes plugins are loaded into a running FSLeyes as follows:

 - Any Python libraries (e.g. installed from ``PyPi``) which are present the
   environment that FSLeyes is running in, and which have a name beginning
   with ``fsleyes-plugin-`` will automatically be detected by FSLeyes.

 - Plugin ``.py`` files, which contain view, control, and/or tool definitions,
   can be passed directly to the :func:`loadPlugin` function.

 - Plugin ``.py`` files which are present in the FSLeyes settings directory,
   or which are found in the ``FSLEYES_PLUGIN_PATH`` environment variable, will
   be loaded by the :func:`initialise` function.

 - Built-in plugins located within the ``fsleyes.plugins`` package.


A plugin can be installed permanently into FSLeyes as follows:


 - Any Python libraries (e.g. installed from ``PyPi``) which are present the
   environment that FSLeyes is running in, and which have a name beginning
   with ``fsleyes-plugin-`` will automatically be detected by FSLeyes.

 - ``.py`` plugin files can be passed to the :func:`installPlugin`
   function. This file will be saved into the FSLeyes settings directory
   (e.g. ``~/.fsleyes/plugins/``).


Writing a FSLeyes plugin
------------------------


.. note:: A minimal example of a FSLeyes plugin library can be found in
          ``tests/testdata/fsleyes_plugin_example/``, and a range of
          built-in plugins can be found in ``fsleyes/plugins/``.


A FSLeyes plugin is a Python library, or a ``.py`` file, which contains
definitions for custom views, controls, and tools.

 - Views must be sub-classes of the :class:`.ViewPanel` class.

 - Controls must be sub-classes of the :class:`.ControlPanel` class. If your
   custom control is designed to only work with a specific view, you should
   override the :mod:`.ControlMixin.supportedViews` static method to return
   the views that your control supports.

 - Tools must be sub-classes of the :class:`.Action` class. Similar to above,
   if your custom tool is designed to only work with a specific view, you
   should override the :mod:`.Action.supportedViews` static method to return
   the views that your tool should be associated with.


To write a ``.py`` file which can be loaded as a FSLeyes plugin, simply
define your views, controls, and tools in the file. The file path can then
be passed to the :func:`loadPlugin` or :func:`installPlugin` function.


To release a FSLeyes plugin as a library, you need to organise your code
as a Python library. Minimally, this requires the following:

 - Arrange your ``.py`` file(s) into a Python package.

 - Write a ``setup.py`` file.

 - Give your library a name (the ``name`` argument to the ``setup``
   function) which begins with ``fsleyes-plugin-``.

 - Expose your custom views, controls, and tools as `entry points
   <https://packaging.python.org/specifications/entry-points/>`__ (the
   ``entry_points`` argument to the ``setup`` function).


A minimal ``setup.py`` file for a FSLeyes plugin might look like this::

    import setuptools

    setup(
        # the name must begin with "fsleyes-plugin-"
        name='fsleyes-plugin-my-cool-plugin',

        # Views, controls, and tools must be exposed
        # as entry points within groups called
        # "fsleyes_views", "fsleyes_controls" and
        # "fsleyes_tools" respectively.
        entry_points={
            'fsleyes_views' : [
                'My cool view = myplugin:MyView'
            ]
            'fsleyes_controls' : [
                'My cool control = myplugin:MyControl'
            ]
            'fsleyes_tools' : [
                'My cool tool = myplugin:MyTool'
            ]
        }
    )


See the `Python Packaging guide
<https://packaging.python.org/tutorials/packaging-projects/>`_ for more
details on writing a ``setup.py`` file.


Module contents
---------------


The following functions can be used to load/install new plugins:

.. autosummary::
   :nosignatures:

   initialise
   loadPlugin
   installPlugin


The following functions can be used to access plugins:

.. autosummary::
   :nosignatures:

   listPlugins
   listViews
   listControls
   listTools
"""


import os.path        as op
import                   os
import                   sys
import                   glob
import                   pkgutil
import                   logging
import                   importlib
import importlib.util as imputil
import                   collections
import                   pkg_resources

import fsl.utils.settings            as fslsettings
import fsleyes.actions               as actions
import fsleyes.strings               as strings
import fsleyes.views.viewpanel       as viewpanel
import fsleyes.controls.controlpanel as ctrlpanel


log = logging.getLogger(__name__)


def initialise():
    """Loads all plugins, including built-ins, plugin files in the FSLeyes
    settings directory, and those found on the ``FSLEYES_PLUGIN_PATH``
    environment variable.
    """

    _loadBuiltIns()

    # plugins in fsleyes settings dir
    pluginFiles = list(fslsettings.listFiles('plugins/*.py'))
    pluginFiles = [fslsettings.filePath(p) for p in pluginFiles]

    # plugins on path
    fpp = os.environ.get('FSLEYES_PLUGIN_PATH', None)
    if fpp is not None:
        for dirname in fpp.split(op.pathsep):
            pluginFiles.extend(glob.glob(op.join(dirname, '*.py')))

    for fname in pluginFiles:
        try:
            loadPlugin(fname)
        except Exception as e:
            log.warning('Failed to load plugin file %s: %s', fname, e)


def _loadBuiltIns():
    """Called by :func:`initialise`. Loads all bulit-in plugins, from
    sub-modules of the ``fsleyes.plugins`` directory.
    """
    thismod = sys.modules[__name__]
    submods = pkgutil.iter_modules(thismod.__path__, thismod.__name__ + '.')
    for _, name, _ in submods:
        log.debug('Loading built-in plugin module %s', name)
        mod  = importlib.import_module(name)
        name = name.split('.')[-1]
        _registerEntryPoints(name, mod)


def listPlugins():
    """Returns a list containing the names of all installed FSLeyes plugins.
    """
    plugins = []
    for dist in pkg_resources.working_set:
        if dist.project_name.startswith('fsleyes-plugin-'):
            plugins.append(dist.project_name)
    return list(sorted(plugins))


def _listEntryPoints(group):
    """Returns a dictionary containing ``{name : type}`` entry points for the
    given entry point group.

    https://setuptools.readthedocs.io/en/latest/pkg_resources.html#entry-points
    """
    items = collections.OrderedDict()
    for plugin in listPlugins():
        for name, ep in pkg_resources.get_entry_map(plugin, group).items():
            if name in items:
                log.debug('Overriding entry point %s [%s] with entry point '
                          'of the same name from %s', name, group, plugin)
            items[name] = ep.load()
    return items


def listViews():
    """Returns a dictionary of ``{name : ViewPanel}`` mappings containing
    the custom views provided by all installed FSLeyes plugins.
    """
    views = _listEntryPoints('fsleyes_views')
    for name, cls in list(views.items()):
        if not issubclass(cls, viewpanel.ViewPanel):
            log.debug('Ignoring fsleyes_views entry point '
                      '{} - not a ViewPanel'.format(name))
            views.pop(name)
            continue
    return views


def listControls(viewType=None):
    """Returns a dictionary of ``{name : ControlPanel}`` mappings containing
    the custom controls provided by all installed FSLeyes plugins.

    :arg viewType: Sub-class of :class:`.ViewPanel` - if provided, only
                   controls which are compatible with this view type are
                   returned (as determined by
                   :meth:`.ControlMixin.supportedViews.`).
    """
    ctrls = _listEntryPoints('fsleyes_controls')

    for name, cls in list(ctrls.items()):
        if not issubclass(cls, (ctrlpanel.ControlPanel,
                                ctrlpanel.ControlToolBar)):
            log.debug('Ignoring fsleyes_controls entry point {} - '
                      'not a ControlPanel/ToolBar'.format(name))
            ctrls.pop(name)
            continue

        supported = cls.supportedViews()
        if viewType  is not None and \
           supported is not None and \
           viewType  not in supported:
            ctrls.pop(name)
            continue
    return ctrls


def listTools():
    """Returns a dictionary of ``{name : Action}`` mappings containing
    the custom tools provided by all installed FSLeyes plugins.
    """
    tools = _listEntryPoints('fsleyes_tools')
    for name, cls in list(tools.items()):
        if not issubclass(cls, actions.Action):
            log.debug('Ignoring fsleyes_tools entry point '
                      '{} - not an Action'.format(name))
            tools.pop(name)
            continue
    return tools


def _importModule(filename, modname):
    """Used by :func:`loadPlugin`. Imports the given Python file, setting the
    module name to ``modname``.
    """
    log.debug('Importing %s as %s', filename, modname)

    spec = imputil.spec_from_file_location(modname, filename)
    mod  = imputil.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sys.modules[modname] = mod
    return mod


def _findEntryPoints(mod):
    """Used by :func:`loadPlugin`. Finds the FSLeyes entry points (views,
    controls, or tools) that are defined within the given module.
     """

    entryPoints = collections.defaultdict(dict)

    for name in dir(mod):

        item  = getattr(mod, name)
        group = None

        if not isinstance(item, type):
            continue

        # avoid module imports
        if item is viewpanel.ViewPanel    or \
           item is ctrlpanel.ControlPanel or \
           item is actions.Action:
            continue

        if   issubclass(item, viewpanel.ViewPanel):    group = 'views'
        elif issubclass(item, ctrlpanel.ControlPanel): group = 'controls'
        elif issubclass(item, actions.Action):         group = 'tools'

        if group is not None:
            log.debug('Found %s entry point: %s', group, name)
            entryPoints['fsleyes_{}'.format(group)][name] = item

    return entryPoints


def _registerEntryPoints(name, module):
    """Called by :func:`loadPlugin`. Finds and registers all FSLeyes entry
    points defined within the gibven module.
    """
    modname  = module.__name__
    filename = module.__file__
    distname = 'fsleyes-plugin-{}'.format(name)

    if distname in listPlugins():
        log.debug('Plugin %s is already in environment - skipping', distname)
        return

    log.debug('Registering plugin %s [dist name %s]', filename, distname)

    entryPoints = _findEntryPoints(module)
    dist        = pkg_resources.Distribution(
        project_name=distname,
        location=filename,
        version='0.0.0')

    # Here I'm relying on the fact that
    # Distribution.get_entry_map returns
    # the actual dict that it uses to
    # store entry points.
    entryMap = dist.get_entry_map()

    for group, entries in entryPoints.items():
        entryMap[group] = {}

        for name in entries.keys():

            # Look up label for built-in plugins
            if group == 'fsleyes_tools':
                label = strings.actions.get(name, name)
            else:
                label = strings.titles.get(name, name)

            ep = '{} = {}:{}'.format(label, modname, name)
            ep = pkg_resources.EntryPoint.parse(ep, dist=dist)
            entryMap[group][label] = ep

    pkg_resources.working_set.add(dist)


def loadPlugin(filename):
    """Loads the given Python file as a FSLeyes plugin. """

    name    = op.splitext(op.basename(filename))[0]
    modname = 'fsleyes_plugin_{}'.format(name)
    mod     = _importModule(filename, modname)
    _registerEntryPoints(name, mod)


def installPlugin(filename):
    """Copies the given Python file into the FSLeyes settings directory,
    within a sub-directory called ``plugins``. After the file has been
    copied, the path to the copy is passed to :func:`loadPlugin`.
    """

    basename = op.splitext(op.basename(filename))[0]
    dest     = 'plugins/{}.py'.format(basename)

    log.debug('Installing plugin %s', filename)

    with open(filename, 'rt')        as inf, \
         fslsettings.writeFile(dest) as outf:
        outf.write(inf.read())

    dest = fslsettings.filePath(dest)

    try:
        loadPlugin(dest)
    except Exception:
        fslsettings.deleteFile(dest)
        raise
