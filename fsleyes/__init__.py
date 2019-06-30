#!/usr/bin/env python
#
# __init__.py - FSLeyes - a python based OpenGL image viewer.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""*FSLeyes* - a 3D image viewer.

This package contains the application logic for *FSLeyes*.


.. image:: images/fsleyes.png
   :scale: 50%
   :align: center


--------
Overview
--------


*FSLeyes* is an OpenGL application for displaying 3D :mod:`overlays
<.overlay>`. All overlays are stored in a single list, the
:class:`.OverlayList`. Only one ``OverlayList`` ever exists - this list is
shared throughout the application.  The primary overlay type is the NIFTI
image format; and a range of other formats are also supported including MGH
volumes, GIFTI and Freesurfer surface files, and VTK triangle meshes.


Amongst other things, *FSLeyes* provides the following features:

  - Orthographic view  (:mod:`.orthopanel`)
  - Lightbox view (:mod:`.lightboxpanel`)
  - 3D view (:mod:`.scene3dpanel`)
  - Time series plotting (:mod:`.timeseriespanel`)
  - Histogram plotting (:mod:`.histogrampanel`)
  - Power spectrum plotting (:mod:`.powerspectrumpanel`)
  - Jupyter notebook integration (:mod:`.notebook`)
  - FSL atlas explorer (:mod:`.atlaspanel`)
  - FEAT cluster results explorer (:mod:`.clusterpanel`)
  - Melodic component classification (:mod:`.melodicclassificationpanel`)
  - NIFTI image editing (:mod:`.editor`)
  - A comprehensive command line interface (:mod:`.parseargs`)


*FSLeyes* makes heavy use of the :mod:`fsleyes_props` project, which is an
event-based programming framework.


------------
Entry points
------------


*FSLeyes* may be started with the :func:`fsleyes.main.main` function. *FSLeyes*
also includes an off-screen screenshot generator called `render`, which may
be started via the :func:`fsleyes.render.main` function.


---------------------------
Frames, views, and controls
---------------------------


The :class:`.FSLeyesFrame` is the top level GUI object. It is a container for
one or more *views*. All views are defined in the :mod:`.views` sub-package,
and are sub-classes of the :class:`.ViewPanel` class. Currently there are two
primary view categories - :class:`.CanvasPanel` views, which use :mod:`OpenGL`
to display overlays, and :class:`.PlotPanel` views, which use
:mod:`matplotlib` to plot data related to the overlays.


View panels may contain one or more *control* panels which provide an
interface allowing the user to control some aspect of the view (e.g. the
:class:`.OverlayDisplayToolBar`), or to display some other data associated
with the overlays (e.g. the :class:`.ClusterPanel`).  All controls are
sub-classes of the :class:`.ControlPanel` or :class:`.ControlToolBar` classes,
and all built-in controls are defined in the :mod:`.controls` sub-package.


The view/control panel class hierarchy is shown below:

.. graphviz::

   digraph hierarchy {

     graph [size=""];

     node [style="filled",
           fillcolor="#ffffdd",
           fontname="sans"];

     rankdir="BT";
     1  [label="panel.FSLeyesPanel"];
     2  [label="views.viewpanel.ViewPanel"];
     3  [label="controls.controlpanel.ControlPanel"];
     4  [label="views.plotpanel.PlotPanel"];
     5  [label="views.canvaspanel.CanvasPanel"];
     6  [label="views.histogrampanel.HistogramPanel"];
     7  [label="<other plot panels>"];
     8  [label="views.orthopanel.OrthoPanel"];
     9  [label="<other canvas panels>"];
     10 [label="controls.overlaylistpanel.OverlayListPanel"];
     11 [label="<other control panels>"];

     2  -> 1;
     3  -> 1;
     4  -> 2;
     5  -> 2;
     6  -> 4;
     7  -> 4;
     8  -> 5;
     9  -> 5;
     10 -> 3;
     11 -> 3;
   }

All toolbars inherit from the :class:`.FSLeyesToolBar` base class:

.. graphviz::

   digraph toolbar_hierarchy {

     graph [size=""];

     node [style="filled",
           fillcolor="#ffffdd",
           fontname="sans"];

     rankdir="BT";
     1 [label="toolbar.FSLeyesToolBar"];
     2 [label="controls.controlpanel.ControlToolBar"];
     3 [label="controls.overlaydisplaytoolbar.OverlayDisplayToolBar"];
     4 [label="controls.lightboxtoolbar.LightBoxToolBar"];
     5 [label="<other toolbars>"];

     2 -> 1;
     3 -> 2;
     4 -> 2;
     5 -> 2;
   }


----------------------
The ``DisplayContext``
----------------------


In order to manage how overlays are displayed, *FSLeyes* uses a
:class:`.DisplayContext`. Because *FSLeyes* allows multiple views to be opened
simultaneously, it needs to use multiple ``DisplayContext`` instances.
Therefore, one master ``DisplayContext`` instance is owned by the
:class:`FSLeyesFrame`, and a child ``DisplayContext`` is created for every
:class:`.ViewPanel`. The display settings managed by each child
``DisplayContext`` instance can be linked to those of the master instance;
this allows display properties to be synchronised across displays.


Each ``DisplayContext`` manages a collection of :class:`.Display` objects, one
for each overlay in the ``OverlayList``. Each of these ``Display`` objects
manages a single :class:`.DisplayOpts` instance, which contains overlay
type-specific display properties. Just as child ``DisplayContext`` instances
can be synchronised with the master ``DisplayContext``, child ``Display`` and
``DisplayOpts`` instances can be synchronised to the master instances.


The above description is summarised in the following diagram:


.. image:: images/fsleyes_architecture.png
   :scale: 40%
   :align: center


In this example, two view panels are open - an :class:`.OrthoPanel`, and a
:class:`.LightBoxPanel`. The ``DisplayContext`` for each of these views, along
with their ``Display`` and ``DisplayOpts`` instances (one of each for every
overlay in the ``OverlayList``) are linked to the master ``DisplayContext``
(and its ``Display`` and ``DisplayOpts`` instances), which is managed by the
``FSLeyesFrame``.  All of this synchronisation functionality is provided by
the ``props`` package.


See the :mod:`~fsleyes.displaycontext` package documentation for more
details.


-----------------------
Events and notification
-----------------------

TODO


.. note:: The current version of FSLeyes (|version|) lives in the
          :mod:`fsleyes.version` module.
"""


import            os
import os.path as op
import            logging
import            warnings

from   fsl.utils.platform import platform as fslplatform
import fsl.utils.settings                 as fslsettings
import fsleyes.version                    as version


# The logger is assigned in
# the configLogging function
log = None


# If set to True, logging will not be configured
disableLogging = fslplatform.frozen


__version__ = version.__version__
"""The current *FSLeyes* version (read from the :mod:`fsleyes.version`
module).
"""


assetDir = op.join(op.dirname(__file__), '..')
"""Base directory which contains all *FSLeyes* assets/resources (e.g. icon
files). This is set in the :func:`initialise` function.
"""


def canWriteToAssetDir():
    """Returns ``True`` if the user can write to the FSLeyes asset directory,
    ``False`` otherwise.
    """
    return os.access(op.join(assetDir, 'assets'), os.W_OK | os.X_OK)


def initialise():
    """Called when `FSLeyes`` is started as a standalone application.  This
    function *must* be called before most other things in *FSLeyes* are used.

    Does a few initialisation steps::

      - Initialises the :mod:`fsl.utils.settings` module, for persistent
        storage  of application settings.

      - Sets the :data:`assetDir` attribute.
    """

    global assetDir

    import matplotlib      as mpl
    import fsleyes.plugins as plugins


    # implement various hacks and workarounds
    _hacksAndWorkarounds()

    # Initialise the fsl.utils.settings module
    fslsettings.initialise('fsleyes')

    # initialise FSLeyes plugins (will discover
    # any plugins saved in the settings dir)
    plugins.initialise()

    # Tell matplotlib what backend to use.
    # n.b. this must be called before
    # matplotlib.pyplot is imported.
    mpl.use('WxAgg')

    # The fsleyes.actions.frameactions module
    # monkey-patches some things into the
    # FSLeyesFrame class, so it must be
    # imported immediately after fsleyes.frame.
    import fsleyes.frame                 # noqa
    import fsleyes.actions.frameactions  # noqa

    fsleyesDir = op.dirname(__file__)
    assetDir   = None
    options    = []

    # If we are running from a bundled
    # application, we'll guess at the
    # location, which will differ depending
    # on the platform
    if fslplatform.frozen:
        mac = op.join(fsleyesDir, '..', '..', '..', '..', 'Resources')
        lnx = op.join(fsleyesDir, '..', 'share', 'FSLeyes')
        options.append(op.normpath(mac))
        options.append(op.normpath(lnx))

    # Otherwise we are running from a code install,
    # or from a source distribution. The assets
    # directory is either inside, or alongside, the
    # FSLeyes package directory.
    else:
        options = [op.join(fsleyesDir, '..'), fsleyesDir]

    for opt in options:
        if op.exists(op.join(opt, 'assets')):
            assetDir = op.abspath(opt)
            break

    if assetDir is None:
        raise RuntimeError('Could not find FSLeyes asset directory! '
                           'Searched: {}'.format(options))


def _hacksAndWorkarounds():
    """Called by :func:`initialise`. Implements hacks and workarounds for
    various things.
    """

    # Under wxPython/Phoenix, the
    # wx.html package must be imported
    # before a wx.App has been created
    import wx.html  # noqa

    # PyInstaller 3.2.1 forces matplotlib to use a
    # temporary directory for its settings and font
    # cache, and then deletes the directory on exit.
    # This is silly, because the font cache can take
    # a long time to create.  Clearing the environment
    # variable should cause matplotlib to use
    # $HOME/.matplotlib (or, failing that, a temporary
    # directory).
    #
    # https://matplotlib.org/faq/environment_variables_faq.html#\
    #   envvar-MPLCONFIGDIR
    #
    # https://github.com/pyinstaller/pyinstaller/blob/v3.2.1/\
    #   PyInstaller/loader/rthooks/pyi_rth_mplconfig.py
    #
    # n.b. This will cause issues if building FSLeyes
    #      with the pyinstaller '--onefile' option, as
    #      discussed in the above pyinstaller file.
    if fslplatform.frozen:
        os.environ.pop('MPLCONFIGDIR', None)

    # OSX sometimes sets the local environment
    # variables to non-standard values, which
    # breaks the python locale module.
    #
    # http://bugs.python.org/issue18378
    try:
        import locale
        locale.getdefaultlocale()
    except ValueError:
        os.environ['LC_ALL'] = 'C.UTF-8'


def configLogging(verbose=0, noisy=None):
    """Configures *FSLeyes* ``logging``.

    .. note:: All logging calls are usually stripped from frozen
              versions of *FSLeyes*, so this function does nothing
              when we are running a frozen version.

    :arg verbose: A number between 0 and 3, indicating the verbosity level.
    :arg noisy:   A sequence of module names - logging will be enabled on these
                  modules.
    """

    global log

    # already configured
    if log is not None:
        return

    if noisy is None:
        noisy = []

    # Show deprecations if running from code
    if fslplatform.frozen:
        warnings.filterwarnings('ignore', category=DeprecationWarning)
    else:
        warnings.filterwarnings('default', category=DeprecationWarning)

    # Set up the root logger
    logFormatter = logging.Formatter('%(levelname)8.8s '
                                     '%(filename)20.20s '
                                     '%(lineno)4d: '
                                     '%(funcName)-15.15s - '
                                     '%(message)s')
    logHandler  = logging.StreamHandler()
    logHandler.setFormatter(logFormatter)

    log = logging.getLogger()
    log.addHandler(logHandler)

    # Everything below this point sets up verbosity
    # as requested by the user. But verbosity-related
    # command line arguments are not exposed to the
    # user in frozen versions of FSLeyes, so if we're
    # running as a frozen app, there's nothing else
    # to do.
    if disableLogging:
        return

    # Now we can set up logging
    if verbose == 1:
        log.setLevel(logging.DEBUG)

        # make some noisy things quiet
        logging.getLogger('fsleyes.gl')     .setLevel(logging.WARNING)
        logging.getLogger('fsleyes.views')  .setLevel(logging.WARNING)
        logging.getLogger('fsleyes_props')  .setLevel(logging.WARNING)
        logging.getLogger('fsleyes_widgets').setLevel(logging.WARNING)
    elif verbose == 2:
        log.setLevel(logging.DEBUG)
        logging.getLogger('fsleyes_props')  .setLevel(logging.WARNING)
        logging.getLogger('fsleyes_widgets').setLevel(logging.WARNING)
    elif verbose == 3:
        log.setLevel(logging.DEBUG)
        logging.getLogger('fsleyes_props')  .setLevel(logging.DEBUG)
        logging.getLogger('fsleyes_widgets').setLevel(logging.DEBUG)

    for mod in noisy:
        logging.getLogger(mod).setLevel(logging.DEBUG)

    # The trace module monkey-patches some
    # things if its logging level has been
    # set to DEBUG, so we import it now so
    # it can set itself up.
    traceLogger = logging.getLogger('fsleyes_props.trace')
    if traceLogger.getEffectiveLevel() <= logging.DEBUG:
        import fsleyes_props.trace  # noqa
