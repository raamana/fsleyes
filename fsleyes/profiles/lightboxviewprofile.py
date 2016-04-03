#!/usr/bin/env python
#
# lightboxviewprofile.py - The LightBoxViewProfile class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`LightBoxViewProfile` class, an interaction
:class:`.Profile` for :class:`.LightBoxPanel` views.
"""

import logging

import fsleyes.profiles as profiles
import fsl.utils.async  as async


log = logging.getLogger(__name__)


class LightBoxViewProfile(profiles.Profile):
    """The ``LightBoxViewProfile`` is an interaction profile for
    :class:`.LightBoxPanel` views. It defines mouse/keyboard handlers which
    allow the user to navigate through the ``LightBoxPanel`` display of the
    overlays in the :class:`.OverlayList`.

    ``LightBoxViewProfile`` defines two *modes* (see the :class:`.Profile`
    class documentation):

    ======== ==================================================================
    ``view`` The user can change the :attr:`.DisplayContext.location` via
             left mouse drags, and can change the
             :attr:`.LightBoxCanvasOpts.topRow` via the mouse wheel.

    ``zoom`` The user can change the :attr:`.LightBoxCanvasOpts.ncols` property
             with the mouse wheel (effectively zooming in/out of the canvas).
    ======== ==================================================================
    """

    
    def __init__(self, viewPanel, overlayList, displayCtx):
        """Create a ``LightBoxViewProfile``.

        :arg viewPanel:    A :class:`.LightBoxPanel` instance.
        :arg overlayList:  The :class:`.OverlayList` instance.
        :arg displayCtx:   The :class:`.DisplayContext` instance.        
        """
        
        profiles.Profile.__init__(self,
                                  viewPanel,
                                  overlayList,
                                  displayCtx,
                                  modes=['view', 'zoom'])

        self.__canvas = viewPanel.getCanvas()

        
    def getEventTargets(self):
        """Returns the :class:`.LightBoxCanvas` contained in the
        :class:`.LightBoxPanel`, which is the target for all mouse/keyboard
        events.
        """
        return [self.__canvas]

        
    def _viewModeMouseWheel(self,
                            ev,
                            canvas,
                            wheel,
                            mousePos=None,
                            canvasPos=None):
        """Handles mouse wheel events in ``view`` mode.

        Updates the :attr:.LightBoxCanvasOpts.topRow` property, thus scrolling
        through the slices displayed on the canvas.
        """

        if   wheel > 0: wheel = -1
        elif wheel < 0: wheel =  1

        # See comment in OrthoViewProfile._zoomModeMouseWheel
        # about timeout
        def update():
            self._viewPanel.getCanvas().topRow += wheel

        async.idle(update, timeout=0.1)

        
    def _viewModeLeftMouseDrag(self, ev, canvas, mousePos, canvasPos):
        """Handles left mouse drags in ``view`` mode.

        Updates the :attr:`.DisplayContext.location` property to track the
        mouse location.
        """

        if canvasPos is None:
            return

        self._displayCtx.location.xyz = canvasPos


    def _zoomModeMouseWheel(self,
                            ev,
                            canvas,
                            wheel,
                            mousePos=None,
                            canvasPos=None):
        """Handles mouse wheel events in ``zoom`` mode.

        Zooms in/out of the canvas by updating the :attr:`.SceneOpts.zoom`
        property.
        """

        if   wheel > 0: wheel =  50
        elif wheel < 0: wheel = -50

        # see comment in OrthoViewProfile._zoomModeMouseWheel
        # about timeout
        def update():
            self._viewPanel.getSceneOptions().zoom += wheel

        async.idle(update, timeout=0.1)
