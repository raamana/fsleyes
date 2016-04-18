#!/usr/bin/env python
#
# __init__.py - FSLeyes control panels.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""The ``controls`` package is the home of all *FSLeyes controls*, as
described in the :mod:`~fsleyes` package documentation.


Every control panel is a sub-class of either the :class:`.FSLEyesPanel` or
:class:`.FSLEyesToolBar`, and each panel allows the user to control some
aspect of either the specific :class:`.ViewPanel` that the control panel is
embedded within, or some general aspect of *FSLeyes*.
"""


from . import atlaspanel
from . import canvassettingspanel
from . import clusterpanel
from . import histogramcontrolpanel
from . import lightboxtoolbar
from . import locationpanel
from . import lookuptablepanel
from . import melodicclassificationpanel
from . import orthoedittoolbar
from . import orthotoolbar
from . import overlaydisplaypanel
from . import overlaydisplaytoolbar
from . import overlayinfopanel
from . import overlaylistpanel
from . import plotlistpanel
from . import powerspectrumcontrolpanel
from . import timeseriescontrolpanel
from . import timeseriestoolbar


AtlasPanel                 = atlaspanel.AtlasPanel
CanvasSettingsPanel        = canvassettingspanel.CanvasSettingsPanel
ClusterPanel               = clusterpanel.ClusterPanel
HistogramControlPanel      = histogramcontrolpanel.HistogramControlPanel
LightBoxToolBar            = lightboxtoolbar.LightBoxToolBar
LocationPanel              = locationpanel.LocationPanel
LookupTablePanel           = lookuptablepanel.LookupTablePanel
MelodicClassificationPanel = melodicclassificationpanel.MelodicClassificationPanel
OrthoEditToolBar           = orthoedittoolbar.OrthoEditToolBar
OrthoToolBar               = orthotoolbar.OrthoToolBar
OverlayDisplayPanel        = overlaydisplaypanel.OverlayDisplayPanel
OverlayDisplayToolBar      = overlaydisplaytoolbar.OverlayDisplayToolBar
OverlayInfoPanel           = overlayinfopanel.OverlayInfoPanel
OverlayListPanel           = overlaylistpanel.OverlayListPanel
PlotListPanel              = plotlistpanel.PlotListPanel
PowerSpectrumControlPanel  = powerspectrumcontrolpanel.PowerSpectrumControlPanel
TimeSeriesControlPanel     = timeseriescontrolpanel.TimeSeriesControlPanel
TimeSeriesToolBar          = timeseriestoolbar.TimeSeriesToolBar
