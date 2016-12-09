#!/usr/bin/env python
#
# orthoeditprofile.py - The OrthoEditProfile class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`OrthoEditProfile` class, an interaction
:class:`.Profile` for :class:`.OrthoPanel` views.
"""

import logging

import wx

import numpy                       as np

import                                props
import fsl.data.image              as fslimage
import fsl.utils.async             as async
import fsl.utils.dialog            as fsldlg
import fsl.utils.status            as status
import fsleyes.overlay             as fsloverlay
import fsleyes.strings             as strings
import fsleyes.actions             as actions
import fsleyes.actions.copyoverlay as copyoverlay
import fsleyes.editor.editor       as fsleditor
import fsleyes.gl.routines         as glroutines
import fsleyes.gl.annotations      as annotations
from . import                         orthoviewprofile


log = logging.getLogger(__name__)



_suppressDisplaySpaceWarning = False
"""Whenever an :class:`OrthoEditProfile` is active, and the
:attr:`.DisplayContext.selectedOverlay` changes, the ``OrthoEditProfile``
changes the :attr:`.DisplayContext.displaySpace` to the newly selected
overlay. If this boolean flag is ``True``, a warning message is shown
to the user. The message dialog has a checkbox which updates this attribute,
and thus allows the user to suppress the warning in the future.
"""


class OrthoEditProfile(orthoviewprofile.OrthoViewProfile):
    """The ``OrthoEditProfile`` class is an interaction profile for use with
    the :class:`.OrthoPanel` class. It gives the user the ability to make
    changes to :class:`.Image` overlays, by using the functionality of the
    :mod:`~fsleyes.editor` package.


    **Modes**
    

    The ``OrthoEditProfile`` has the following modes, in addition to those
    already defined by the :class:`.OrthoViewProfile`:

    =========== ===============================================================
    ``sel``     Select mode. The user is able to manually add voxels to the
                selection using a *cursor*. The cursor size can be changed
                with the :attr:`selectionSize` property, and the cursor can be
                toggled between a 2D square and a 3D cube via the
                :attr:`selectionIs3D` property. If the :attr:`drawMode`
                property is ``True``, selected voxels are immediately filled
                with the :attr:`fillValue` when the mouse is released.
    
    ``desel``   Deselect mode. Identical to ``sel`` mode, except that the 
                cursor is used to remove voxels from the selection. If the
                :attr:`drawMode` property is ``True``, selected voxels are
                immediately set to 0 when the mouse is released.

    ``chsize``  Change-size mode. The use can change the :attr:`selectionSize`
                attribute via the mouse wheel.
    
    ``selint``  Select by intensity mode.

    ``chthres`` Change-threshold mode. The user can change the
                :attr:`intensityThres` via the mouse wheel.

    ``chrad``   Change-radius mode. The user can change the
                :attr:`searchRadius` via the mouse wheel. 
    =========== ===============================================================


    **Actions**
    

    The ``OrthoEditProfile`` defines the following actions, on top of those
    already defined by the :class:`.OrthoViewProfile`:

    .. autosummary::
       :nosignatures:

       undo
       redo
       clearSelection
       fillSelection
       eraseSelection
       copySelection
       pasteSelection

    
    **Annotations**


    The ``OrthoEditProfile`` class uses :mod:`.annotations` on the
    :class:`.SliceCanvas` panels, displayed in the :class:`.OrthoPanel`,
    to display information to the user. Two annotations are used:

     - The *cursor* annotation. This is a :class:`.Rect` annotation
       representing a cursor at the voxel, or voxels, underneath the
       current mouse location.
    
     - The *selection* annotation. This is a :class:`.VoxelSelection`
       annotation which displays the :class:`.Selection`.


    **The display space**

    
    The ``OrthoEditProfile`` class has been written in a way which requires
    the :class:`.Image` instance that is being edited to be displayed in
    *scaled voxel* (a.k.a. ``pixdim``) space.  Therefore, when an ``Image``
    overlay is selected, the ``OrthoEditProfile`` instance sets that ``Image``
    as the current :attr:`.DisplayContext.displaySpace` reference image.
    """


    selectionCursorColour = props.Colour(default=(1, 1, 0, 0.7))
    """Colour used for the cursor annotation. """

    
    selectionOverlayColour = props.Colour(default=(1, 0.25, 1, 0.4))
    """Colour used for the selection annotation, which displays the voxels
    that are currently selected.
    """
    
    
    selectionSize = props.Int(minval=1, maxval=100, default=3, clamped=True)
    """In ``sel`` and ``desel`` modes, defines the size of the selection
    cursor.
    """

    
    selectionIs3D = props.Boolean(default=False)
    """In ``sel`` and ``desel`` mode, toggles the cursor between a 2D square
    and a 3D cube. In ``selint`` mode, toggles the selection space between the
    current slice, and the full 3D volume.
    """

    
    fillValue = props.Real(default=1, clamped=True)
    """The value used when drawing/filling voxel values - all voxels in the
    selection will be filled with this value.
    """


    eraseValue = props.Real(default=0, clamped=True)
    """The value used when erasing voxel values - all voxels in the
    selection will be filled with this value.
    """ 


    drawMode = props.Boolean(default=True)
    """If ``True``, when in ``sel`` or ``desel`` mode, clicks and click+
    drags cause the image to be immediately modified. Otherwise, editing 
    is a two stage process (as described in the :class:`.Editor` class
    documentation).

    This setting is enabled by default, because it causes FSLeyes to behave
    like FSLView. However, all advanced editing/selection capabilities are
    disabled when ``drawMode`` is ``True``.
    """


    intensityThres = props.Real(
        minval=0.0, maxval=1.0, default=0, clamped=False)
    """In ``selint`` mode, the maximum distance, in intensity, that a voxel
    can be from the seed location, in order for it to be selected.
    Passed as the ``precision`` argument to the
    :meth:`.Selection.selectByValue` method.
    """


    intensityThresLimit = props.Real(minval=0.0, default=0, clamped=True)
    """This setting controls the maximum value for the :attr:`itensityThres`
    property. It is set automatically from the data when an :class:`.Image`
    is first selected, but can also be manually controlled via this property.
    """

    
    localFill = props.Boolean(default=False)
    """In ``selint`` mode, if this property is ``True``, voxels can only be
    selected if they are adjacent to an already selected voxel. Passed as the
    ``local`` argument to the :meth:`.Selection.selectByValue` method.
    """
    

    limitToRadius = props.Boolean(default=False)
    """In ``selint`` mode, if this property is ``True``, the search region
    will be limited to a sphere (in the voxel coordinate system) with its
    radius specified by the :attr:`searchRadius` property.
    """

    
    searchRadius = props.Real(
        minval=0.01, maxval=200, default=0.0, clamped=True)
    """In ``selint`` mode, if :attr:`limitToRadius` is true, this property
    specifies the search sphere radius. Passed as the ``searchRadius``
    argument to the :meth:`.Selection.selectByValue` method.
    """

    
    targetImage = props.Choice()
    """By default, all modifications that the user makes will be made on the
    currently selected overlay (the :attr:`.DisplayContext.selectedOverlay`).
    However, this property  can be used to select a different image as the
    target for modifications.
    
    This proprty is mostly useful when in ``selint`` mode - the selection
    can be made based on the voxel intensities in the currently selected
    image, but the selection can be filled in another iamge (e.g. a
    mask/label image).
    
    This property is updated whenever the :class:`.OverlayList` or the
    currently selected overlay changes, so that it contains all other
    overlays which have the same dimensions as the selected overlay.
    """ 

    
    def __init__(self, viewPanel, overlayList, displayCtx):
        """Create an ``OrthoEditProfile``.

        :arg viewPanel:   The :class:`.OrthoPanel` instance.
        :arg overlayList: The :class:`.OverlayList` instance.
        :arg displayCtx:  The :class:`.DisplayContext` instance.
        """

        # The currently selected overlay - 
        # the overlay being edited. 
        self.__currentOverlay = None

        # The 'clipboard' is created by
        # the copySelection method - it
        # contains a numpy array which
        # was copied from another overlay.
        # The clipboard source refers to
        # the overlay that the clipboard
        # was copied from.
        self.__clipboard       = None
        self.__clipboardSource = None

        # An Editor instance is created for each
        # Image overlay (on demand, as they are
        # selected), and kept in this dictionary
        # (which contains {Image : Editor} mappings).
        self.__editors = {}

        # Ref to each canvas on the ortho panel
        self.__xcanvas = viewPanel.getXCanvas()
        self.__ycanvas = viewPanel.getYCanvas()
        self.__zcanvas = viewPanel.getZCanvas()

        # The current selection is shown on each
        # canvas - a ref to the SelectionAnnotation
        # is kept here
        self.__xselAnnotation = None
        self.__yselAnnotation = None
        self.__zselAnnotation = None

        # A few performance optimisations are made
        # when in selint mode and limitToRadius is
        # active - the __record/__getSelectionMerger
        # methods populate these fields.
        self.__mergeMode   = None
        self.__mergeBlock  = None
        self.__merge3D     = None
        self.__mergeRadius = None

        # The targetImage/intensityThres/
        # intensityThresLimit property values
        # are cached on a per-overlay basis.
        # When an overlay is re-selected, its
        # values are restored from the cache.
        self.__cache = fsloverlay.PropCache(
            overlayList,
            displayCtx,
            self,
            ['targetImage', 'intensityThres', 'intensityThresLimit'])

        orthoviewprofile.OrthoViewProfile.__init__(
            self,
            viewPanel,
            overlayList,
            displayCtx,
            ['sel', 'desel', 'chsize', 'selint', 'chthres', 'chrad'])

        self.mode = 'nav'

        displayCtx .addListener('selectedOverlay',
                                self._name,
                                self.__selectedOverlayChanged)
        overlayList.addListener('overlays',
                                self._name,
                                self.__selectedOverlayChanged)

        self.addListener('targetImage',
                         self._name,
                         self.__targetImageChanged)
        self.addListener('drawMode',
                         self._name,
                         self.__drawModeChanged)
        self.addListener('selectionOverlayColour',
                         self._name,
                         self.__selectionColoursChanged)
        self.addListener('selectionCursorColour',
                         self._name,
                         self.__selectionColoursChanged)
        self.addListener('intensityThresLimit',
                         self._name,
                         self.__selintThresLimitChanged) 
        self.addListener('intensityThres',
                         self._name,
                         self.__selintPropertyChanged)
        self.addListener('searchRadius',
                         self._name,
                         self.__selintPropertyChanged)
        self.addListener('localFill',
                         self._name,
                         self.__selintPropertyChanged)
        self.addListener('limitToRadius',
                         self._name,
                         self.__selintPropertyChanged)

        self.__selectedOverlayChanged()
        self.__drawModeChanged()


    def destroy(self):
        """Removes some property listeners, destroys the :class:`.Editor`
        instances, and calls :meth:`.OrthoViewProfile.destroy`.
        """

        self._displayCtx .removeListener('selectedOverlay', self._name)
        self._overlayList.removeListener('overlays',        self._name)

        for editor in self.__editors.values():
            editor.destroy()

        xannot = self.__xcanvas.getAnnotations()
        yannot = self.__ycanvas.getAnnotations()
        zannot = self.__zcanvas.getAnnotations()

        if self.__xselAnnotation is not None:
            xannot.dequeue(self.__xselAnnotation, hold=True)
            self.__xselAnnotaiton.destroy()
            
        if self.__yselAnnotation is not None:
            yannot.dequeue(self.__yselAnnotation, hold=True)
            self.__yselAnnotaiton.destroy()
            
        if self.__zselAnnotation is not None:
            zannot.dequeue(self.__zselAnnotation, hold=True)
            self.__zselAnnotaiton.destroy()

        self.__cache.destroy()

        self.__editors         = None
        self.__xcanvas         = None
        self.__ycanvas         = None
        self.__zcanvas         = None
        self.__xselAnnotation  = None
        self.__yselAnnotation  = None
        self.__zselAnnotation  = None
        self.__currentOverlay  = None
        self.__clipboard       = None
        self.__clipboardSource = None
        self.__cache           = None
        
        orthoviewprofile.OrthoViewProfile.destroy(self)

        
    def deregister(self):
        """Destroys all :mod:`.annotations`, and calls
        :meth:`.OrthoViewProfile.deregister`.
        """

        xannot = self.__xcanvas.getAnnotations()
        yannot = self.__ycanvas.getAnnotations()
        zannot = self.__zcanvas.getAnnotations()
        
        if self.__xselAnnotation is not None:
            xannot.dequeue(self.__xselAnnotation, hold=True)
            self.__xselAnnotation.destroy()

        if self.__yselAnnotation is not None:
            yannot.dequeue(self.__yselAnnotation, hold=True)
            self.__yselAnnotation.destroy()

        if self.__zselAnnotation is not None:
            zannot.dequeue(self.__zselAnnotation, hold=True)
            self.__zselAnnotation.destroy()

        self.__xselAnnotation = None
        self.__yselAnnotation = None
        self.__zselAnnotation = None
            
        orthoviewprofile.OrthoViewProfile.deregister(self)


    @actions.action
    def createMask(self):
        """Create a 3D mask which has the same size as the currently selected
        overlay, and insert it into the overlay list.
        """
        if self.__currentOverlay is None:
            return
        
        copyoverlay.copyImage(self._overlayList,
                              self._displayCtx,
                              self.__currentOverlay,
                              createMask=True,
                              copy4D=False,
                              copyDisplay=False)


    @actions.action
    def clearSelection(self):
        """Clears the current selection. See :meth:`.Editor.clearSelection`.
        """
        
        if self.__currentOverlay is None:
            return

        editor = self.__editors[self.__currentOverlay]

        editor.clearSelection()
        
        self.__refreshCanvases()


    @actions.action
    def fillSelection(self):
        """Fills the current selection with the :attr:`fillValue`. See
        :meth:`.Editor.fillSelection`.
        """
        if self.__currentOverlay is None:
            return

        editor = self.__editors[self.__currentOverlay]

        if self.targetImage is not None:
            editor = self.__getTargetImageEditor(editor)

        editor.startChangeGroup()
        editor.fillSelection(self.fillValue)
        editor.clearSelection()
        editor.endChangeGroup()


    @actions.action
    def eraseSelection(self):
        """Fills the current selection with zero. See
        :meth:`.Editor.fillSelection`.
        """
        if self.__currentOverlay is None:
            return

        editor = self.__editors[self.__currentOverlay]

        if self.targetImage is not None:
            editor = self.__getTargetImageEditor(editor) 

        editor.startChangeGroup()
        editor.fillSelection(self.eraseValue)
        editor.clearSelection()
        editor.endChangeGroup()


    @actions.action
    def copySelection(self):
        """Copies the data within the selection from the currently selected
        overlay, and stores it in an internal "clipboard".
        """

        overlay = self.__currentOverlay

        if overlay is None:
            return

        editor = self.__editors[overlay]

        self.__clipboard       = editor.copySelection()
        self.__clipboardSource = overlay

        self.__setCopyPasteState()


    @actions.action
    def pasteSelection(self):
        """Pastes the data currently stored in the clipboard into the currently
        selected image, if possible.
        """
        
        if self.__currentOverlay is None:
            return

        overlay         = self.__currentOverlay
        clipboard       = self.__clipboard
        clipboardSource = self.__clipboardSource

        if     overlay   is None:                  return
        if     clipboard is None:                  return
        if not clipboardSource.sameSpace(overlay): return

        editor = self.__editors[overlay]

        if self.targetImage is not None:
            editor = self.__getTargetImageEditor(editor)

        editor.startChangeGroup()
        editor.pasteSelection(clipboard)
        editor.clearSelection()
        editor.endChangeGroup()
 

    @actions.action
    def undo(self):
        """Un-does the most recent change to the selection or to the
        :class:`.Image` data. See :meth:`.Editor.undo`.
        """

        if self.__currentOverlay is None:
            return
        
        editor = self.__editors[self.__currentOverlay]

        # We're disabling notification of changes to the selection
        # during undo/redo. This is because a single undo
        # will probably involve multiple modifications to the
        # selection (as changes are grouped by the editor),
        # with each of those changes causing the selection object
        # to notify its listeners. As one of these listeners is a
        # SelectionTexture, these notifications can get expensive,
        # due to updates to the GL texture buffer. So we disable
        # notification, and then manually refresh the texture
        # afterwards
        with editor.getSelection().skipAll():
            editor.undo()
        
        self.__xselAnnotation.texture.refresh()
        self.__refreshCanvases()


    @actions.action
    def redo(self):
        """Re-does the most recent undone change to the selection or to the
        :class:`.Image` data. See :meth:`.Editor.redo`.
        """

        if self.__currentOverlay is None:
            return

        editor = self.__editors[self.__currentOverlay]

        # See comment in undo method 
        # about disabling notification
        with editor.getSelection().skipAll():
            editor.redo()
        
        self.__xselAnnotation.texture.refresh()
        self.__refreshCanvases()


    def __drawModeChanged(self, *a):
        """Called when the :attr:`drawMode` changes. Updates the enabled
        state of various actions that are irrelevant when in draw mode.
        """

        # The only possible profile modes 
        # when drawMode==True are sel/desel.
        if self.drawMode and self.mode not in ('nav', 'sel', 'desel'):
            self.mode = 'sel'

        if self.drawMode: self.getProp('mode').disableChoice('selint', self)
        else:             self.getProp('mode').enableChoice( 'selint', self)

        self.clearSelection.enabled = not self.drawMode
        self.fillSelection .enabled = not self.drawMode
        self.eraseSelection.enabled = not self.drawMode

        if self.__currentOverlay is not None:
            self.__editors[self.__currentOverlay].clearSelection()
            self.__refreshCanvases()
            
        self.__updateTargetImage()
        self.__setCopyPasteState()


    def __setCopyPasteState(self):
        """Enables/disables the :meth:`copySelection`/ :meth:`pasteSelection`
        actions as needed.
        """

        overlay   = self.__currentOverlay
        clipboard = self.__clipboard
        source    = self.__clipboardSource

        enableCopy  = (not self.drawMode)     and \
                      (overlay is not None)

        enablePaste =  enableCopy             and \
                      (clipboard is not None) and \
                      (overlay.sameSpace(source))

        self.copySelection .enabled = enableCopy
        self.pasteSelection.enabled = enablePaste
 

    def __selectionColoursChanged(self, *a):
        """Called when either of the :attr:`selectionOverlayColour` or
        :attr:`selectionCursorColour` properties change.
        
        Updates the  :mod:`.annotations` colours accordingly.
        """
        if self.__xselAnnotation is not None:
            self.__xselAnnotation.colour = self.selectionOverlayColour
            
        if self.__yselAnnotation is not None:
            self.__yselAnnotation.colour = self.selectionOverlayColour
            
        if self.__zselAnnotation is not None:
            self.__zselAnnotation.colour = self.selectionOverlayColour


    def __updateTargetImage(self):
        """Resets the value and choices on the :attr:`targetImage`.
        It is populated with all :class:`.Image` instances which are in the
        same space as the currently selected overlay.
        """

        with props.skip(self, 'targetImage', self._name):
            self.targetImage = None
            
        overlay = self.__currentOverlay

        if overlay is None:
            return

        compatibleOverlays = [None]
        if not self.drawMode:
            for ovl in self._overlayList:
                if ovl is not overlay and overlay.sameSpace(ovl):
                    compatibleOverlays.append(ovl)
                    
        self.getProp('targetImage').setChoices(compatibleOverlays,
                                               instance=self)


    def __getTargetImageEditor(self, srcEditor):
        """If the :attr:`targetImage` is set to an image other than the
        currently selected one, this method returns an :class:`.Editor`
        for the target image. 
        """

        if self.targetImage is None:
            return srcEditor
        
        tgtEditor = self.__editors[self.targetImage]
        srcSel    = srcEditor.getSelection()
        tgtSel    = tgtEditor.getSelection()
        
        tgtSel.setSelection(srcSel.getSelection(), (0, 0, 0))
        srcSel.clearSelection()
        
        return tgtEditor


    def __targetImageChanged(self, *a):
        """Called every time the :attr:`targetImage` is changed. Makes sure
        that an :class:`.Editor` instance for the selected target image exists.
        """

        image = self.targetImage

        if image is None: image = self.__currentOverlay
        if image is None: return
        
        editor = self.__editors.get(image, None)

        if editor is None:
            editor = fsleditor.Editor(image,
                                      self._overlayList,
                                      self._displayCtx)
            self.__editors[image] = editor 


    def __setPropertyLimits(self):
        """Called by the :meth:`__selectedOverlayChanged` method. 
        """

        overlay = self.__currentOverlay
        if overlay is None:
            # TODO 
            return
        
        if issubclass(overlay.dtype.type, np.integer):
            dmin = np.iinfo(overlay.dtype).min
            dmax = np.iinfo(overlay.dtype).max
        else:
            dmin = None
            dmax = None

        self.setConstraint('fillValue',  'minval', dmin)
        self.setConstraint('fillValue',  'maxval', dmax)
        self.setConstraint('eraseValue', 'minval', dmin)
        self.setConstraint('eraseValue', 'maxval', dmax) 

        thres = self.__cache.get(overlay, 'intensityThres',      None)
        limit = self.__cache.get(overlay, 'intensityThresLimit', None)

        if limit is None or limit == 0:
            dmin, dmax = overlay.dataRange
            limit      = (dmax - dmin) / 2.0
 
        if thres is None: thres = 0
        else:             thres = min(thres, limit)

        with props.skip(self, 'intensityThres', self._name):
            self.setConstraint('intensityThres', 'maxval', limit)
            self.intensityThres = thres
            
        with props.skip(self, 'intensityThresLimit', self._name):
            self.intensityThresLimit = limit


    def __selectedOverlayChanged(self, *a):
        """Called when either the :class:`.OverlayList` or
        :attr:`.DisplayContext.selectedOverlay` change.

        Destroys all old :mod:`.annotations`. If the newly selected overlay is
        an :class:`Image`, new annotations are created.
        """
        # Overview:
        #  1. Destroy Editor instances associated with
        #     overlays that no longer exist
        #
        #  2. Destroy old canvas annotations
        #
        #  3. Remove property listeners on editor/selection
        #     objects associated with the previous overlay
        #
        #  4. Load/create a new Editor for the new overlay
        #
        #  5. Transfer the exsiting selection to the new
        #     overlay if possible.
        #
        #  6. Add property listeners to the editor/selection
        #
        #  7. Create canvas annotations
        #
        # Here we go....

        # Destroy any Editor instances which are associated
        # with overlays that are no longer in the overlay list
        #
        # TODO - If the current overlay has been removed,
        #        this will cause an error later on. You
        #        need to handle this scenario here.
        # 
        # for overlay, editor in self.__editors:
        #     if overlay not in self._overlayList:
        #         self.__editors.pop(overlay)
        #         editor.destroy()

        oldOverlay = self.__currentOverlay
        overlay    = self._displayCtx.getSelectedOverlay()

        # If the selected overlay hasn't changed,
        # we don't need to do anything
        if overlay == oldOverlay:
            self.__updateTargetImage()
            return

        # Destroy all existing canvas annotations
        xannot = self.__xcanvas.getAnnotations()
        yannot = self.__ycanvas.getAnnotations()
        zannot = self.__zcanvas.getAnnotations()        

        # Clear the selection annotation
        if self.__xselAnnotation is not None:
            xannot.dequeue(self.__xselAnnotation, hold=True)
            self.__xselAnnotation.destroy()
            
        if self.__yselAnnotation is not None:
            yannot.dequeue(self.__yselAnnotation, hold=True)
            self.__yselAnnotation.destroy()
            
        if self.__zselAnnotation is not None:
            zannot.dequeue(self.__zselAnnotation, hold=True)
            self.__zselAnnotation.destroy()
            
        self.__xselAnnotation = None
        self.__yselAnnotation = None
        self.__zselAnnotation = None

        # Remove property listeners from the
        # editor/selection instances associated
        # with the previously selected overlay
        if oldOverlay is not None:
            editor = self.__editors[oldOverlay]

            log.debug('De-registering listeners from Editor {} ({})'.format(
                id(editor), oldOverlay.name))
            self.undo.unbindProps('enabled', editor.undo)
            self.redo.unbindProps('enabled', editor.redo)

        self.__currentOverlay = overlay

        # Update the limits/options on all properties.
        self.__updateTargetImage()
        self.__setPropertyLimits()
        self.__setCopyPasteState()
        
        # If there is no selected overlay (the overlay
        # list is empty), don't do anything.
        if overlay is None:
            return

        display = self._displayCtx.getDisplay(overlay)
        opts    = display.getDisplayOpts()

        # Edit mode is only supported on
        # images with the 'volume', 'mask'
        # or 'label' types
        if not isinstance(overlay, fslimage.Image) or \
           display.overlayType not in ('volume', 'mask', 'label'):
            
            self.__currentOverlay = None
            return

        # Update the limits/options on all properties. 
        self.__setPropertyLimits()
        self.__setCopyPasteState()

        # Change the display space so that the newly
        # selected image is the reference image -
        # display a message to the user, as this may
        # otherwise be confusing
        if self._displayCtx.displaySpace != overlay:

            msg  = strings.messages[self, 'imageChange']
            hint = strings.messages[self, 'imageChangeHint']
            msg  = msg.format(overlay.name)
            hint = hint.format(overlay.name) 

            global _suppressDisplaySpaceWarning
            if not _suppressDisplaySpaceWarning:

                cbMsg = strings.messages[self, 'imageChange.suppress']
                title = strings.titles[  self, 'imageChange']
                
                dlg   = fsldlg.CheckBoxMessageDialog(
                    self._viewPanel,
                    title=title,
                    message=msg,
                    cbMessages=[cbMsg],
                    cbStates=[_suppressDisplaySpaceWarning],
                    hintText=hint,
                    focus='yes',
                    icon=wx.ICON_INFORMATION)

                dlg.ShowModal()

                _suppressDisplaySpaceWarning  = dlg.CheckBoxState()

            status.update(msg) 
            self._displayCtx.displaySpace = overlay

        # Load the editor for the overlay (create
        # one if necessary), and add listeners to
        # some editor/selection properties
        editor = self.__editors.get(overlay, None)
        
        if editor is None:
            editor = fsleditor.Editor(overlay,
                                      self._overlayList,
                                      self._displayCtx)
            self.__editors[overlay] = editor

        # Transfer or clear the selection
        # for the old overlay.
        if oldOverlay is not None:

            oldSel = self.__editors[oldOverlay].getSelection()

            # Currently we only transfer
            # the selection for images
            # with the same dimensions/space
            if oldOverlay.sameSpace(overlay):

                log.debug('Transferring selection from {} to {}'.format(
                    oldOverlay.name,
                    overlay.name))

                newSel = editor.getSelection()
                newSel.setSelection(oldSel.getSelection(), (0, 0, 0))
            else:
                oldSel.clearSelection()

        # Restore the targetImage for this
        # overlay, if there is a cached value
        targetImage = self.__cache.get(overlay, 'targetImage', None)
        if targetImage is not None and targetImage in self._overlayList:
            with props.skip(self, 'targetImage', self._name):
                self.targetImage = targetImage

        # Register property listeners with the
        # new Editor and Selection instances.
        log.debug('Registering listeners with Editor {} ({})'.format(
            id(editor),
            self.__currentOverlay.name))

        # Bind undo/redo action enabled states
        self.undo.bindProps('enabled', editor.undo)
        self.redo.bindProps('enabled', editor.redo)
    
        # Create a selection annotation and
        # queue it on the canvases for drawing
        self.__xselAnnotation = annotations.VoxelSelection(
            self.__xcanvas.xax,
            self.__xcanvas.yax,
            editor.getSelection(),
            opts.getTransform('display', 'voxel'),
            opts.getTransform('voxel',   'display'),
            opts.getTransform('voxel',   'texture'),
            colour=self.selectionOverlayColour)
        
        self.__yselAnnotation = annotations.VoxelSelection(
            self.__ycanvas.xax,
            self.__ycanvas.yax,
            editor.getSelection(),
            opts.getTransform('display', 'voxel'),
            opts.getTransform('voxel',   'display'),
            opts.getTransform('voxel',   'texture'),
            colour=self.selectionOverlayColour)
        
        self.__zselAnnotation = annotations.VoxelSelection(
            self.__zcanvas.xax,
            self.__zcanvas.yax,
            editor.getSelection(),
            opts.getTransform('display', 'voxel'),
            opts.getTransform('voxel',   'display'),
            opts.getTransform('voxel',   'texture'),
            colour=self.selectionOverlayColour) 

        xannot.obj(self.__xselAnnotation, hold=True)
        yannot.obj(self.__yselAnnotation, hold=True)
        zannot.obj(self.__zselAnnotation, hold=True)

        self.__refreshCanvases()


    def __getVoxelLocation(self, canvasPos):
        """Returns the voxel location, for the currently selected overlay,
        which corresponds to the specified canvas position. Returns ``None``
        if the current canvas position is out of bounds for the current
        overlay.
        """

        if self.__currentOverlay is None:
            return None
        
        opts = self._displayCtx.getOpts(self.__currentOverlay)
        return opts.getVoxel(canvasPos)


    def __drawCursorAnnotation(self, canvas, voxel, blockSize=None):
        """Draws the cursor annotation. Highlights the specified voxel with a
        :class:`~fsleyes.gl.annotations.Rect` annotation.
        
        This is used by mouse motion event handlers, so the user can
        see the possible selection, and thus what would happen if they
        were to click.

        :arg canvas:    The :class:`.SliceCanvas` on which to make the
                        annotation.
        :arg voxel:     Voxel which is at the centre of the cursor.
        :arg blockSize: Size of the cursor square/cube.
        """

        overlay  = self.__currentOverlay
        opts     = self._displayCtx.getOpts(overlay)
        canvases = [self.__xcanvas, self.__ycanvas, self.__zcanvas]

        # Create a cursor annotation for each canvas
        kwargs  = {'colour' : self.selectionCursorColour,
                   'width'  : 2,
                   'expiry' : 0.5}

        cursors = []

        for c in canvases:
            r = annotations.Rect(c.xax, c.yax, (0, 0), 0, 0, **kwargs)
            cursors.append(r)

        # If we are running in a low
        # performance mode, the cursor
        # is only drawn on the current
        # canvas.
        if self._viewPanel.getSceneOptions().performance < 4:
            cursors  = [cursors[canvases.index(canvas)]]
            canvases = [canvas]

        # If a block size was not specified,
        # it defaults to selectionSize
        if blockSize is None:
            blockSize = self.selectionSize

        # We need to specify the block
        # size in scaled voxels along
        # each voxel dimension. So we
        # scale the block size by the
        # shortest voxel axis - we're
        # aiming for a square (if 2D)
        # or a cube (if 3D) selection.
        blockSize = np.min(overlay.pixdim) * blockSize
        blockSize = [blockSize] * 3

        # Limit to the current plane
        # if in 2D selection mode
        if self.selectionIs3D: axes = (0, 1, 2)
        else:                  axes = (canvas.xax, canvas.yax)

        # Calculate a box in the voxel coordinate
        # system, centred at the current voxel,
        # and of the specified block size
        corners = glroutines.voxelBox(voxel,
                                      overlay.shape,
                                      overlay.pixdim,
                                      blockSize,
                                      axes=axes,
                                      bias='high')
 
        if corners is None:
            return

        # We want the selection to follow voxel
        # edges, but the transformCoords method
        # will map voxel coordinates to the
        # displayed voxel centre. So we offset
        # by -0.5 to get the corners.
        corners = opts.transformCoords(corners - 0.5, 'voxel', 'display')

        cmin = corners.min(axis=0)
        cmax = corners.max(axis=0)

        for cursor, canvas in zip(cursors, canvases):
            xax = canvas.xax
            yax = canvas.yax
            zax = canvas.zax

            if canvas.pos.z < cmin[zax] or canvas.pos.z > cmax[zax]:
                cursor.w = 0
                cursor.h = 0
                continue
            
            cursor.xy = cmin[[xax, yax]]
            cursor.w  = cmax[xax] - cmin[xax]
            cursor.h  = cmax[yax] - cmin[yax]

        # Queue the cursors
        for cursor, canvas in zip(cursors, canvases):
            canvas.getAnnotations().obj(cursor)


    def __refreshCanvases(self):
        """Short cut to refresh the canvases of the :class:`.OrthoPanel`.

        .. note:: This is done instead of calling ``OrthoPanel.Refresh``
                  because the latter introduces flickering.
        """
        self.__xcanvas.Refresh()
        self.__ycanvas.Refresh()
        self.__zcanvas.Refresh()


    def __dynamicRefreshCanvases(self,
                                 ev,
                                 canvas,
                                 mousePos=None,
                                 canvasPos=None):
        """Called by mouse event handlers when the user is interacting with
        a canvas.

        If the current :class:`.ViewPanel` performance setting (see
        :attr:`.SceneOpts.performance`) is at its maximum, all three
        :class:`.OrthoPanel` :class:`.SliceCanvas` canvases are refreshed
        on selection updates.

        On all lower performance settings, only the source canvas is updated.
        """
        perf = self._viewPanel.getSceneOptions().performance

        # If the given location is already
        # equal to the display location,
        # calling _navModeLeftMouseDrag we
        # will not trigger a refresh, so
        # we will force the refresh instead.
        forceRefresh = (
            canvasPos is not None and
            np.all(np.isclose(canvasPos, self._displayCtx.location.xyz)))

        # If running in high performance mode, we make
        # the canvas location track the edit cursor
        # location, so that the other two canvases
        # update to display the current cursor location.
        if perf == 4               and \
           (mousePos  is not None) and \
           (canvasPos is not None):
            
            self._navModeLeftMouseDrag(ev, canvas, mousePos, canvasPos)

            if forceRefresh:
                for c in self.getEventTargets():
                    c.Refresh()

        else:
            canvas.Refresh()
            

    def __applySelection(self, canvas, voxel, add=True, combine=False):
        """Called by ``sel`` mode mouse handlers. Adds/removes a block
        of voxels, centred at the specified voxel, to/from the current
        :class:`.Selection`.

        :arg canvas: The source :class:`.SliceCanvas`.
        :arg voxel:  Coordinates of centre voxel.
        :arg add:    If ``True`` a block is added to the selection,
                     otherwise it is removed.
        """

        if self.selectionIs3D: axes = (0, 1, 2)
        else:                  axes = (canvas.xax, canvas.yax)

        overlay   = self.__currentOverlay
        editor    = self.__editors[overlay]
        selection = editor.getSelection()
        blockSize = self.selectionSize * np.min(overlay.pixdim)

        block, offset = glroutines.voxelBlock(
            voxel,
            overlay.shape,
            overlay.pixdim,
            blockSize,
            axes=axes,
            bias='high')

        if add: selection.addToSelection(     block, offset, combine)
        else:   selection.removeFromSelection(block, offset, combine)

        if add: self.__recordSelectionMerger('sel',   offset, block.shape)
        else:   self.__recordSelectionMerger('desel', offset, block.shape)


    def __recordSelectionMerger(self, mode, offset, size):
        """This method is called whenever a change is made to the
        :class:`.Selection` object. It stores some information which is used
        to improve subsequent selection performance when in ``selint`` mode,
        and when :attr:`limitToRadius` is ``True``.

        
        Basically, if the current selection is limited by radius, and a new,
        similarly limited selection is made, we do not need to clear the
        entire selection before making the new selection - we just need to
        clear the cuboid region in which the previous selection was located.


        This behaviour is referred to as a 'merge' because, ultimately, the
        region of the first selection is merged with the region of the second
        selection, and only this part of the ``Selection`` image is refreshed.

        
        This method (and the :meth:`__getSelectionMerger` method) contains some
        simple, but awkward, logic which figures out when a merge can happen
        and, conversely, when the full selection does need to be cleared.

        
        :arg offset: Offset into the selection array of the change.
        :arg size:   Shape of the change.
        """

        # If the user has manually selected anything,
        # we can't merge 
        if self.__mergeMode == 'sel':
            return

        self.__mergeMode   = mode
        self.__merge3D     = self.selectionIs3D
        self.__mergeRadius = self.limitToRadius

        # We only care about merging
        # selint+radius blocks
        if mode == 'selint' and self.__mergeRadius:
            self.__mergeBlock  = offset, size


    def __getSelectionMerger(self):
        """This method is called just before a select-by-intensity selection
        is about to happen. It rteturns one of three values:

          - The string ``'clear'``, indicating that the whole selection (or
            the whole slice, if :attr:`selectionIs3D` is ``False``) needs to
            be cleared.
        
          - The value ``None`` indicating that the selection does not need to
            be cleared, and a merge does not need to be made.
        
          - A tuple containing the ``(offset, size)`` of a previous change
            to the selection, specifying the portion of the selection which
            needs to be cleared, and which can be subsequently merged with
            a new selection.
        """

        try:
            # If not limiting by radius, the new
            # selectByValue call will clobber the
            # old selection, so we don't need to
            # merge or clear it.
            if not self.limitToRadius:
                return None

            # If the user was selecting voxels,
            # we don't know where those selected
            # voxels are, so we have to clear
            # the full selection.
            if self.__mergeMode == 'sel':
                return 'clear'

            # If the user was just deselecting,
            # we can merge the old block
            if self.__mergeMode == 'desel':
                return self.__mergeBlock

            # If the user was in 2D, but is now
            # in 3D, we have to clear the whole
            # selection. Similarly, if the user
            # was not limiting by radius, but
            # now is, we have to clear.
            if (not self.__merge3D)     and self.selectionIs3D: return 'clear'
            if (not self.__mergeRadius) and self.limitToRadius: return 'clear'

            # Otherwise we can merge the old
            # selection with the new selection.
            return self.__mergeBlock
        
        finally:
            self.__mergeMode   = None
            self.__merge3D     = None
            self.__mergeRadius = None
            self.__mergeBlock  = None


    def _selModeMouseMove(self, ev, canvas, mousePos, canvasPos):
        """Handles mouse motion events in ``sel`` mode.

        Draws a cursor annotation at the current mouse location
        (see :meth:`__draweCursorAnnotation`).
        """
        voxel = self.__getVoxelLocation(canvasPos)

        if voxel is not None:
            self.__drawCursorAnnotation(canvas, voxel)
            self.__dynamicRefreshCanvases(ev,  canvas)

        return voxel is not None


    def _selModeLeftMouseDown(self,
                              ev,
                              canvas,
                              mousePos,
                              canvasPos,
                              add=True,
                              mode='sel'):
        """Handles mouse down events in ``sel`` mode.

        Starts an :class:`.Editor` change group, and adds to the current
        :class:`Selection`.

        This method is also used by :meth:`_deselModeLeftMouseDown`, which
        may set the ``add`` parameter to ``False``.

        :arg add:  If ``True`` (default) a block at the cursor is added to the
                   selection. Otherwise it is removed.

        :arg mode: The current profile mode (defaults to ``'sel'``).
        """
        if self.__currentOverlay is None:
            return False

        if self.drawMode:

            # If in immediate draw mode, we clear
            # the Selection object's most recent
            # saved change - all additions to the
            # selection during this click+drag
            # event are merged together (by using
            # the combine flag to addToSelection -
            # see __applySelection). Then, on the
            # up event, we know what part of the
            # selection needs to be refreshed.
            selection = self.__editors[self.__currentOverlay].getSelection()
            selection.setChange(None, None)

        voxel = self.__getVoxelLocation(canvasPos)

        if voxel is not None:
            self.__applySelection(      canvas, voxel, add=add, combine=True)
            self.__drawCursorAnnotation(canvas, voxel)
            self.__dynamicRefreshCanvases(ev,  canvas, mousePos, canvasPos)
 

        return voxel is not None


    def _selModeLeftMouseDrag(self,
                              ev,
                              canvas,
                              mousePos,
                              canvasPos,
                              add=True,
                              mode='sel'):
        """Handles mouse drag events in ``sel`` mode.

        Adds to the current :class:`Selection`.

        This method is also used by :meth:`_deselModeLeftMouseDown`, which
        may set the ``add`` parameter to ``False``. 
        
        :arg add:  If ``True`` (default) a block at the cursor is added to the
                   selection. Otherwise it is removed.

        :arg mode: The current profile mode (defaults to ``'sel'``).
        """ 
        voxel = self.__getVoxelLocation(canvasPos)

        if voxel is not None:
            self.__applySelection(      canvas, voxel, add=add, combine=True)
            self.__drawCursorAnnotation(canvas, voxel)
            self.__dynamicRefreshCanvases(ev,  canvas, mousePos, canvasPos)

        return voxel is not None


    def _selModeLeftMouseUp(
            self, ev, canvas, mousePos, canvasPos, fillValue=None):
        """Handles mouse up events in ``sel`` mode.

        Ends the :class:`.Editor` change group that was started in the
        :meth:`_selModeLeftMouseDown` method.

        This method is also used by :meth:`_deselModeLeftMouseUp`, which
        sets ``fillValue`` to :attr:`eraseValue`.

        :arg fillValue: If :attr:`drawMode` is ``True``, the value to
                        fill the selection with. If not provided, defaults
                        to :attr:`fillValue`.
        """
        
        if self.__currentOverlay is None:
            return False
        
        editor    = self.__editors[self.__currentOverlay]
        selection = editor.getSelection()

        # Immediate draw mode - fill
        # the selection, and then
        # clear the selection.
        if self.drawMode:
            
            if fillValue is None:
                fillValue = self.fillValue

            editor.fillSelection(fillValue)

            # The Selection object contains the
            # full extent of the changes that
            # were made to the selection during
            # this click+drag event. We only need
            # to clear this part of the selection.
            old, new, off = selection.getLastChange()
            restrict      = [slice(o, o + s) for o, s in zip(off, new.shape)]

            selection.clearSelection(restrict=restrict)
        
        self.__refreshCanvases()

        return True


    def _selModeMouseLeave(self, ev, canvas, mousePos, canvasPos):
        """Handles mouse leave events in ``sel`` mode. Makes sure that the
        selection cursor annotation is not shown on any canvas.
        """
        
        self.__dynamicRefreshCanvases(ev, canvas)

    
    def _deselModeLeftMouseDown(self, ev, canvas, mousePos, canvasPos):
        """Handles mouse down events in ``desel`` mode.

        Calls :meth:`_selModeLeftMouseDown`.
        """
        self._selModeLeftMouseDown(ev,
                                   canvas,
                                   mousePos,
                                   canvasPos,
                                   add=self.drawMode,
                                   mode='desel')


    def _deselModeLeftMouseDrag(self, ev, canvas, mousePos, canvasPos):
        """Handles mouse drag events in ``desel`` mode.

        Calls :meth:`_selModeLeftMouseDrag`.
        """
        self._selModeLeftMouseDrag(ev,
                                   canvas,
                                   mousePos,
                                   canvasPos,
                                   add=self.drawMode,
                                   mode='desel')

        
    def _deselModeLeftMouseUp(self, ev, canvas, mousePos, canvasPos):
        """Handles mouse up events in ``desel`` mode.

        Calls :meth:`_selModeLeftMouseUp`.
        """
        self._selModeLeftMouseUp(
            ev, canvas, mousePos, canvasPos, fillValue=self.eraseValue)


    def _chsizeModeMouseWheel(self, ev, canvas, wheelDir, mousePos, canvasPos):
        """Handles mouse wheel events in ``chsize`` mode.

        Increases/decreases the current :attr:`selectionSize`.
        """

        if   wheelDir > 0: self.selectionSize += 1
        elif wheelDir < 0: self.selectionSize -= 1

        voxel = self.__getVoxelLocation(canvasPos)

        if voxel is None:
            return False

        # See comment in OrthoViewProfile._zoomModeMouseWheel
        # about timeout
        def update():
            self.__drawCursorAnnotation(canvas, voxel)
            self.__dynamicRefreshCanvases(ev, canvas)

        async.idle(update, timeout=0.1)

        return True


    def __selintPropertyChanged(self, *a):
        """Called when the :attr:`intensityThres`, :attr:`localFill`,
        :attr:`limitToRadius`, or :attr:`searchRadius` properties change.
        Re-runs select-by-intensity (via :meth:`__selintSelect`), with
        the new settings.
        """

        if self.__currentOverlay is None:
            return

        mousePos, canvasPos = self.getLastMouseUpLocation()
        canvas              = self.getLastCanvas()

        if mousePos is None or canvas is None:
            return

        voxel = self.__getVoxelLocation(canvasPos)

        def update():
            self.__selintSelect(voxel, canvas)
            self.__refreshCanvases()

        if voxel is not None:
            
            # Asynchronously update the select-by-intensity
            # selection - we do it async, and with a time out,
            # so we don't queue loads of redundant jobs while
            # the user is e.g. dragging the intensityThres
            # slider real fast.
            async.idle(update, timeout=0.1)


    def __selintThresLimitChanged(self, *a):
        """Called when the :attr:`intensityThresLimit` changes. Updates the
        maximum value on the :attr:`intensityThres` accordingly.
        """
        self.setConstraint('intensityThres',
                           'maxval',
                           self.intensityThresLimit)

    
    def __selintSelect(self, voxel, canvas):
        """Selects voxels by intensity, using the specified ``voxel`` as
        the seed location.

        Called by the :meth:`_selintModeLeftMouseDown`,
        :meth:`_selintModeLeftMouseDrag`, 
        :meth:`_selintModeLeftMouseWheel`, and :meth:`__selintPropertyChanged`
        methods.  See :meth:`.Selection.selectByValue`.
        """
        
        overlay = self.__currentOverlay

        if overlay is None:
            return False

        editor = self.__editors[self.__currentOverlay]
        
        if not self.limitToRadius:
            searchRadius = None
        else:
            searchRadius = (self.searchRadius / overlay.pixdim[0],
                            self.searchRadius / overlay.pixdim[1],
                            self.searchRadius / overlay.pixdim[2])

        if self.selectionIs3D:
            restrict = None
        else:
            zax           = canvas.zax
            restrict      = [slice(None, None, None) for i in range(3)]
            restrict[zax] = slice(voxel[zax], voxel[zax] + 1)

        # We may need to manually clear part or all
        # of the selection before running the select
        # by value routine. The get/recordSelectionMerger
        # methods take care of the logic needed to
        # figure out what we need to do.
        selection = editor.getSelection()
        merge     = self.__getSelectionMerger()

        # The whole selection/slice needs clearing.
        # We suppress any notification by the Selection
        # object at this point - notification will
        # happen via the selectByValue method call below.
        if merge == 'clear':
            with selection.skipAll():
                selection.clearSelection(restrict=restrict)

        # We only need to clear a region 
        # within the selection
        elif merge is not None:

            # Note that we are telling the
            # selectByValuem method below 
            # 'combine' any previous selection
            # change with the new one, This
            # means that the entire selection
            # image is going to be replaced
            with selection.skipAll():

                # If we're in 2D mode, we just clear
                # the whole slice, as it should be fast
                # enough.
                if not self.selectionIs3D:
                     
                    selection.clearSelection(restrict=restrict)

                # Otherwise we just clear the region
                else:
                    off, size  = merge
                    clearBlock = [slice(o, o + s) for o, s in zip(off, size)]

                    selection.clearSelection(restrict=clearBlock)

        # The 'combine' flag tells the selection object
        # to merge the last change (the clearSelection
        # call above) with the new change, so that the
        # Selection.getLastChange method will return
        # the union of those two regions.
        #
        # This is important, because the SelectionTexture
        # object, which is listening to changes on the
        # Selection object, will only need to update that
        # part of the GL texture.
        selected, offset = selection.selectByValue(
            voxel,
            precision=self.intensityThres,
            searchRadius=searchRadius,
            local=self.localFill,
            restrict=restrict,
            combine=merge is not None)

        self.__recordSelectionMerger('selint', offset, selected.shape)

        return True


    def _selintModeMouseMove(self, ev, canvas, mousePos, canvasPos):
        """Handles mouse motion events in ``selint`` mode. Draws a selection
        annotation at the current location (see
        :meth:`__drawCursorAnnotation`).
        """
        voxel = self.__getVoxelLocation(canvasPos)

        if voxel is not None:
            self.__drawCursorAnnotation(canvas, voxel, 1)
            self.__dynamicRefreshCanvases(ev,  canvas)

        return voxel is not None

        
    def _selintModeLeftMouseDown(self, ev, canvas, mousePos, canvasPos):
        """Handles mouse down events in ``selint`` mode.

        Starts an :class:`.Editor` change group, then clears the current
        selection, and selects voxels by intensity (see
        :meth:`__selintSelect`).
        """

        if self.__currentOverlay is None:
            return False
        
        voxel = self.__getVoxelLocation(canvasPos)

        if voxel is not None:
            self.__selintSelect(voxel, canvas)
            self.__dynamicRefreshCanvases(ev, canvas, mousePos, canvasPos)

        return voxel is not None

        
    def _selintModeLeftMouseDrag(self, ev, canvas, mousePos, canvasPos):
        """Handles mouse drag events in ``selint`` mode.

        A select-by-intensity is re-run with the current mouse location.  See
        the :meth:`__selintSelect` method.
        """ 

        voxel = self.__getVoxelLocation(canvasPos)

        if voxel is not None:
            
            refreshArgs = (ev, canvas, mousePos, canvasPos)

            self.__drawCursorAnnotation(canvas, voxel, 1)
            self.__selintSelect(voxel, canvas)
            self.__dynamicRefreshCanvases(*refreshArgs)

        return voxel is not None

        
    def _selintModeLeftMouseUp(self, ev, canvas, mousePos, canvasPos):
        """Handles mouse up events in ``selint`` mode. Ends the :class:`.Editor`
        change group that was started in the :meth:`_selintModeLeftMouseDown`
        method.
        """
        if self.__currentOverlay is None:
            return False
        
        self.__refreshCanvases()

        return True


    def _chthresModeMouseWheel(self, ev, canvas, wheel, mousePos, canvasPos):
        """Handles mouse wheel events in ``chthres`` mode.

        The :attr:`intensityThres` value is decreased/increased according to
        the mouse wheel direction. If the mouse button is down,
        select-by-intensity is re-run at the current mouse location.
        """ 
        overlay   = self._displayCtx.getSelectedOverlay()
        dataRange = overlay.dataRange[1] - overlay.dataRange[0]
        step      = 0.01 * dataRange

        if   wheel > 0: offset =  step
        elif wheel < 0: offset = -step
        else:           return False

        self.intensityThres += offset
        
        return True

                
    def _chradModeMouseWheel(self, ev, canvas, wheel, mousePos, canvasPos):
        """Handles mouse wheel events in ``chrad`` mode.

        The :attr:`searchRadius` value is decreased/increased according
        to the mouse wheel direction. If the mouse button is down,
        select-by-intensity is re-run at the current mouse location.
        """ 

        if   wheel > 0: offset =  2.5
        elif wheel < 0: offset = -2.5
        else:           return False

        self.searchRadius += offset

        return True
