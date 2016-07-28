#!/usr/bin/env python
#
# __init__.py - OpenGL data and rendering for FSLeyes.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This package contains the OpenGL data and rendering stuff for *FSLeyes*.
On-screen and off-screen rendering is supported, and two OpenGL versions (1.4
and 2.1) are supported.  The contents of this package can be broadly
categorised into the following:

 - *Canvases*: A canvas is a thing that can be drawn on.

 - *Objects*:  An object is a thing which can be drawn on a canvas.


-----------
Quick start
-----------

::

    import fsleyes.gl as fslgl
    import fsleyes.gl.wxglslicecanvas as slicecanvas

    # Make sure that an OpenGL context
    # has been created. This procedure
    # requires a dummy canvas to be
    # created.
    ctx, dummyFrame = fslgl.getWXGLContext()

    # Call gl.bootstrap, to initialise
    # some package-level stuff
    fslgl.bootstrap()

    # Now you can do stuff! The
    # SliceCanvas will take care
    # of creating and managing
    # GLObjects for each overlay
    # in the overlay list.
    canvas = slicecanvas.WXGLSliceCanvas(parent, overlayList, displayCtx)

    # But make sure to delete the
    # dummy canvas after you have
    # created a real canvas.
    if dummyFrame is not None:
        dummyFrame.Destroy()


--------
Canvases
--------


A *canvas* is the destination for an OpenGL scene render. The following
canvases are defined in the ``gl`` package:

.. autosummary::
   :nosignatures:

   ~fsleyes.gl.slicecanvas.SliceCanvas
   ~fsleyes.gl.lightboxcanvas.LightBoxCanvas
   ~fsleyes.gl.colourbarcanvas.ColourBarCanvas


These classes are not intended to be used directly. This is because the ``gl``
package has been written to support two primary use-cases:

  - *On-screen* display of a scene using a :class:`wx.glcanvas.GLCanvas`
    canvas.

  - *Off-screen* renering of a scene using OSMesa.


Because of this, the canvas classes listed above are not dependent upon the
OpenGL environment in which they are used (i.e. on-screen or off-screen).
Instead, two base classes are provided for each of the use-cases:


.. autosummary::
   :nosignatures:

   WXGLCanvasTarget
   OSMesaCanvasTarget


And the following sub-classes are defined, providing use-case specific
implementations for each of the available canvases:

.. autosummary::
   :nosignatures:

   ~fsleyes.gl.wxglslicecanvas.WXGLSliceCanvas
   ~fsleyes.gl.wxgllightboxcanvas.WXGLLightBoxCanvas
   ~fsleyes.gl.wxglcolourbarcanvas.WXGLColourBarCanvas
   ~fsleyes.gl.osmesaslicecanvas.OSMesaSliceCanvas
   ~fsleyes.gl.osmesalightboxcanvas.OSMesaLightBoxCanvas
   ~fsleyes.gl.osmesacolourbarcanvas.OSMesaColourBarCanvas


The classes listed above are the ones which are intended to be instantiated
and used by application code.


--------------
``gl`` objects
--------------


With the exception of the :class:`.ColourBarCanvas`, everything that is drawn
on a canvas derives from the :class:`.GLObject` base class. A ``GLObject``
manages the underlying data structures, GL resources (e.g. shaders and
textures), and rendering routines required to draw an object to a canvas.  The
following ``GLObject`` sub-classes correspond to each of the possible types
(the :attr:`.Display.overlayType` property) that an overlay can be displayed
as:

.. autosummary::

   ~fsleyes.gl.glvolume.GLVolume
   ~fsleyes.gl.glmask.GLMask
   ~fsleyes.gl.gllabel.GLLabel
   ~fsleyes.gl.gllinevector.GLLineVector
   ~fsleyes.gl.glrgbvector.GLRGBVector
   ~fsleyes.gl.glmodel.GLModel
   ~fsleyes.gl.gltensor.GLTensor
   ~fsleyes.gl.glsh.GLSH

These objects are created and destroyed automatically by :class:`.SliceCanvas`
instances, so application code does not need to worry about them too much.


===========
Annotations
===========


:class:`.SliceCanvas` canvases can be *annotated* in a few ways, by use of the
:class:`.Annotations` class. An ``Annotations`` object allows lines,
rectangles, and other simple shapes to be rendered on top of the ``GLObject``
renderings which represent the overlays in the :class:`.OverlayList`.  The
``Annotations`` object for a ``SliceCanvas`` instance can be accessed through
its :meth:`.SliceCanvas.getAnnotations` method.


---------------------------------
OpenGL versions and bootstrapping
---------------------------------


*FSLeyes* needs to be able to run in restricted environments, such as within a
VNC session, and over SSH. In such environments the available OpenGL version
could be quite old, so the ``gl`` package has been written to support an
environment as old as OpenGL 1.4.


The available OpenGL API version can only be determined once an OpenGL context
has been created, and a display is available for rendering. The package-level
:func:`getWXGLContext` and :func:`getOSMesaContext` functions allow a context
to be created.


The data structures and rendering logic for some ``GLObject`` classes differs
depending on the OpenGL version that is available. Therefore, the code for
these ``GLObject`` classes may be duplicated, with one version for OpenGL 1.4,
and another version for OpenGL 2.1.  The ``GLObject`` code which targets a
specific OpenGL version lives within either the :mod:`.gl14` or :mod:`.gl21`
sub-packages.


Because of this, the package-level :func:`bootstrap` function must be called
before any ``GLObject`` instances are created. 
"""


import os
import logging
import platform

import props

import fsl.utils.async                    as async
from   fsl.utils.platform import platform as fslplatform


log = logging.getLogger(__name__)


# When running under X, indirect rendering fails for
# unknown reasons, so I'm forcing direct rendering.
# If direct rendering is not available, I don't know
# what to do.
os.environ.pop('LIBGL_ALWAYS_INDIRECT', None)


import OpenGL


# Make PyOpenGL throw an error, instead of implicitly
# converting, if we pass incorrect types to OpenGL functions.
OpenGL.ERROR_ON_COPY = True


# These flags should be set to True
# for development, False for production
OpenGL.ERROR_CHECKING = True
OpenGL.ERROR_LOGGING  = True


# If FULL_LOGGING is enabled,
# every GL call will be logged.
# OpenGL.FULL_LOGGING   = True


# Using PyOpenGL 3.1 (and OSX Mavericks 10.9.4 on a MacbookPro11,3), the
# OpenGL.contextdata.setValue method throws 'unhashable type' TypeErrors
# unless we set STORE_POINTERS to False. I don't know why.
if os.environ.get('PYOPENGL_PLATFORM', None) == 'osmesa':
    OpenGL.STORE_POINTERS = False


def bootstrap(glVersion=None):
    """Imports modules appropriate to the specified OpenGL version.

    The available OpenGL API version can only be queried once an OpenGL
    context is created, and a canvas is available to draw on. This makes
    things a bit complicated, because it means that we are only able to
    choose how to draw things when we actually need to draw them.

    This function should be called after an OpenGL context has been created,
    and a canvas is available for drawing, but before any attempt to draw
    anything.  It will figure out which version-dependent package needs to be
    loaded, and will attach all of the modules contained in said package to
    the :mod:`~fsleyes.gl` package.  The version-independent modules may
    then simply access these version-dependent modules through this module.


    After the :func:`boostrap` function has been called, the following
    package-level attributes will be available on the ``gl`` package:


    ====================== ====================================================
    ``GL_VERSION``         A string containing the target OpenGL version, in 
                           the format ``major.minor``, e.g. ``2.1``.


    ``GL_RENDERER``        A string containing the name of the OpenGL renderer.

    ``glvolume_funcs``     The version-specific module containing functions for
                           rendering :class:`.GLVolume` instances.

    ``glrgbvector_funcs``  The version-specific module containing functions for
                           rendering :class:`.GLRGBVector` instances.

    ``gllinevector_funcs`` The version-specific module containing functions for
                           rendering :class:`.GLLineVector` instances.

    ``glmodel_funcs``      The version-specific module containing functions for
                           rendering :class:`.GLModel` instances.
    
    ``gllabel_funcs``      The version-specific module containing functions for
                           rendering :class:`.GLLabel` instances.
    
    ``gltensor_funcs``     The version-specific module containing functions for
                           rendering :class:`.GLTensor` instances. 
    ====================== ====================================================


    This function also sets the :attr:`.Platform.glVersion` and
    :attr:`.Platform.glRenderer` properties of the
    :attr:`fsl.utils.platform.platform` instance.
    

    :arg glVersion: A tuple containing the desired (major, minor) OpenGL API
                    version to use. If ``None``, the best possible API
                    version will be used.
    """

    import sys
    import OpenGL.GL         as gl
    import OpenGL.extensions as glexts
    from . import               gl14
    from . import               gl21

    thismod = sys.modules[__name__]

    if hasattr(thismod, '_bootstrapped'):
        return

    if glVersion is None:
        glVer        = gl.glGetString(gl.GL_VERSION).split()[0].decode('ascii')
        major, minor = [int(v) for v in glVer.split('.')][:2]
    else:
        major, minor = glVersion

    glVersion = major + minor / 10.0

    glpkg = None

    if glVersion >= 2.1:
        verstr = '2.1'
        glpkg  = gl21
    elif glVersion >= 1.4:
        verstr = '1.4'
        glpkg  = gl14
    else: raise RuntimeError('OpenGL 1.4 or newer is required '
                             '(detected version: {:0.1f}'.format(glVersion))

    # The gl21 implementation depends on a
    # few extensions - if they're not present,
    # fall back to the gl14 implementation
    if glpkg == gl21:

        # List any GL21 extensions here
        exts = ['GL_EXT_framebuffer_object',
                'GL_ARB_instanced_arrays',
                'GL_ARB_draw_instanced']
        
        if not all(map(glexts.hasExtension, exts)):
            log.debug('One of these OpenGL extensions is '
                      'not available: [{}]. Falling back '
                      'to an older OpenGL implementation.'
                      .format(', '.join(exts))) 
            verstr = '1.4'
            glpkg = gl14

    # If using GL14, and the ARB_vertex_program
    # and ARB_fragment_program extensions are
    # not present, we're screwed.
    if glpkg == gl14:
        
        exts = ['GL_EXT_framebuffer_object',
                'GL_ARB_vertex_program',
                'GL_ARB_fragment_program']
        
        if not all(map(glexts.hasExtension, exts)):
            raise RuntimeError('One of these OpenGL extensions is '
                               'not available: [{}]. This software '
                               'cannot run on the available graphics '
                               'hardware.'.format(', '.join(exts)))

        # Spline interpolation is not currently
        # available in the GL14 implementation
        import fsleyes.displaycontext         as dc
        dc.VolumeOpts   .interpolation.removeChoice('spline')
        dc.RGBVectorOpts.interpolation.removeChoice('spline')
        dc.VolumeOpts   .interpolation.updateChoice('linear',
                                                    newAlt=['spline'])
        dc.RGBVectorOpts.interpolation.updateChoice('linear',
                                                    newAlt=['spline']) 

        # Tensor/SH overlays are not available in GL14
        dc.ALL_OVERLAY_TYPES           .remove('tensor')
        dc.ALL_OVERLAY_TYPES           .remove('sh')
        dc.OVERLAY_TYPES['TensorImage'].remove('tensor')
        dc.OVERLAY_TYPES['Image']      .remove('sh') 

    renderer = gl.glGetString(gl.GL_RENDERER).decode('ascii')
    log.debug('Using OpenGL {} implementation with renderer {}'.format(
        verstr, renderer))

    # If we're using a software based renderer,
    # reduce the default performance settings
    # 
    # There doesn't seem to be any quantitative
    # method for determining whether we are using
    # software-based rendering, so a hack is
    # necessary. 
    if 'software' in renderer.lower():
        
        log.debug('Software-based rendering detected - '
                  'lowering default performance settings.')

        import fsleyes.displaycontext as dc
        dc.SceneOpts.performance.setConstraint(None, 'default', 2)

    thismod.GL_VERSION         = verstr
    thismod.GL_RENDERER        = renderer
    thismod.glvolume_funcs     = glpkg.glvolume_funcs
    thismod.glrgbvector_funcs  = glpkg.glrgbvector_funcs
    thismod.gllinevector_funcs = glpkg.gllinevector_funcs
    thismod.glmodel_funcs      = glpkg.glmodel_funcs
    thismod.gllabel_funcs      = glpkg.gllabel_funcs
    thismod.gltensor_funcs     = glpkg.gltensor_funcs
    thismod.glsh_funcs         = glpkg.glsh_funcs
    thismod._bootstrapped      = True
    
    fslplatform.glVersion      = thismod.GL_VERSION
    fslplatform.glRenderer     = thismod.GL_RENDERER


def getWXGLContext(parent=None):
    """Create and return a GL context object for rendering to a
    :class:`wx.glcanvas.GLCanvas` canvas.

    If a context object has already been created, it is returned.
    Otherwise, one is created and returned. In the latter case,
    the ``parent`` parameter must be a visible :mod:`wx` object.

    In either case, this function returns two values:
    
      - A :class:`wx.glcanvas.GLContext` instance
    
      - If a context instance has previously been created, the second return
        value is ``None``. Otherwise, a dummy :class:`wx.glcanvas.GLCanvas`
        instance is returned. This canvas should be destroyed by the caller
        when it is safe to do so. This seems to primarily be a problem under
        Linux/GTK - it does not seem to be possible to destroy the dummy
        canvas immediately after creating the context. So the calling code
        needs to destroy it at some point in the future (possibly after
        another, real ``GLCanvas`` has been created, and set as the context
        target).
    """

    import sys
    import wx
    import wx.glcanvas as wxgl

    thismod = sys.modules[__name__]

    # A context has already been created
    if hasattr(thismod, '_wxGLContext'):
        return thismod._wxGLContext, None

    if parent is None or not parent.IsShown():
        raise RuntimeError('A visible WX object is required '
                           'to create a GL context')

    # We can't create a wx GLContext without
    # a wx GLCanvas. But we can create a
    # dummy one, and destroy it after the
    # context has been created. Destroying
    # the canvas is the responsibility of the
    # calling code.

    # There's something wrong with wxPython's
    # GLCanvas (on OSX at least) - the pixel
    # format attributes have to be set on the
    # *first* GLCanvas that is created -
    # setting them on subsequent canvases will
    # have no effect. But if you set them on
    # the first canvas, all canvases that are
    # subsequently created will inherit the
    # same properties.
    attribs = [wxgl.WX_GL_RGBA,
               wxgl.WX_GL_DOUBLEBUFFER,
               wxgl.WX_GL_STENCIL_SIZE, 4,
               wxgl.WX_GL_DEPTH_SIZE,   8,
               0,
               0] 

    canvas = wxgl.GLCanvas(parent, attribList=attribs)
    canvas.SetSize((0, 0))

    # The canvas must be visible before we are
    # able to set it as the target of the GL context
    canvas.Show(True)
    canvas.Refresh()
    canvas.Update()
    wx.Yield()

    thismod._wxGLContext = wxgl.GLContext(canvas)
    thismod._wxGLContext.SetCurrent(canvas)

    return thismod._wxGLContext, canvas

    
def getOSMesaContext():
    """Create and return a GL context object for off-screen rendering using
    OSMesa.
    """

    import sys    
    import OpenGL.GL              as gl
    import OpenGL.raw.osmesa.mesa as osmesa
    import OpenGL.arrays          as glarrays

    thismod = sys.modules[__name__]
    
    if not hasattr(thismod, '_osmesaGLContext'):

        # We follow the same process as for the
        # wx.glcanvas.GLContext, described above 
        dummy = glarrays.GLubyteArray.zeros((640, 480, 43))
        thismod._osmesaGLContext = osmesa.OSMesaCreateContextExt(
            gl.GL_RGBA, 8, 4, 0, None)
        osmesa.OSMesaMakeCurrent(thismod._osmesaGLContext,
                                 dummy,
                                 gl.GL_UNSIGNED_BYTE,
                                 640,
                                 480) 

    return thismod._osmesaGLContext 


class OSMesaCanvasTarget(object):
    """Base class for canvas objects which support off-screen rendering using
    OSMesa.
    """
    
    def __init__(self, width, height):
        """Create an ``OSMesaCanvasTarget``. An off-screen buffer, to be used
        as the render target, is created.

        :arg width:    Width in pixels
        :arg height:   Height in pixels

        """
        import OpenGL.arrays as glarrays 
        self.__width  = width
        self.__height = height 
        self.__buffer = glarrays.GLubyteArray.zeros((height, width, 4))

        
    def _getSize(self):
        """Returns a tuple containing the canvas width and height."""
        return self.__width, self.__height

        
    def _setGLContext(self):
        import OpenGL.GL              as gl
        import OpenGL.raw.osmesa.mesa as osmesa
        """Configures the GL context to render to this canvas. """
        osmesa.OSMesaMakeCurrent(getOSMesaContext(),
                                 self.__buffer,
                                 gl.GL_UNSIGNED_BYTE,
                                 self.__width,
                                 self.__height)
        return True

        
    def _postDraw(self):
        """Does nothing. This canvas is for static (i.e. unchanging) rendering.
        """
        pass


    def _draw(self, *a):
        """Must be provided by subclasses."""
        raise NotImplementedError()

        
    def Refresh(self, *a):
        """Does nothing. This canvas is for static (i.e. unchanging) rendering.
        """
        pass

    
    def Freeze(self):
        """Does nothing. This canvas is for static (i.e. unchanging) rendering.
        """
        pass

        
    def Thaw(self):
        """Does nothing. This canvas is for static (i.e. unchanging) rendering.
        """
        pass 


    def draw(self):
        """Calls the :meth:`_draw` method, which must be provided by
        subclasses.
        """

        self._initGL()
        self._setGLContext()
        self._draw()

        
    def getBitmap(self):
        """Return a (width*height*4) shaped numpy array containing the
        rendered scene as an RGBA bitmap. The bitmap will be full of
        zeros if the scene has not been drawn (via a call to
        :meth:`draw`).
        """
        import OpenGL.GL        as gl
        import numpy            as np

        self._setGLContext()
        
        bmp = gl.glReadPixels(
            0, 0,
            self.__width, self.__height,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE)
        
        bmp = np.fromstring(bmp, dtype=np.uint8)
        bmp = bmp.reshape((self.__height, self.__width, 4))
        bmp = np.flipud(bmp)

        return bmp


    def saveToFile(self, filename):
        """Saves the contents of this canvas as an image, to the specified
        file.
        """
        import matplotlib.image as mplimg
        mplimg.imsave(filename, self.getBitmap()) 


WXGLMetaClass = None
"""Under Python3/wxPython-Phoenix, we must specify a meta-class which derives
from the ``wx.siplib.wrappertype``, and from the :class:`.props.PropertyOwner`
meta-class.  This is not necessary under Python2/wxPython.
"""


if fslplatform.wxFlavour == fslplatform.WX_PHOENIX:

    import wx.siplib as sip

    class PhoenixMeta(props.PropertyOwner, sip.wrappertype):
        pass

    WXGLMetaClass = PhoenixMeta
    
else:
    WXGLMetaClass = props.PropertyOwner


class WXGLCanvasTarget(object):
    """Base class for :class:`wx.glcanvas.GLCanvas` objects.

    It is assumed that subclasses of this base class are also subclasses of
    :class:`wx.glcanvas.GLCanvas`. Sub-classes must override the following
    methods:

    .. autosummary::
       :nosignatures:

       _initGL
       _draw
    """


    def __init__(self):
        """Create a ``WXGLCanvasTarget``. """

        import wx
        import wx.glcanvas as wxgl

        context = getWXGLContext()[0]

        # If we are on OSX, and using the Apple Software
        # Renderer (e.g. in a virtual machine), then it
        # seems that we have to have a separate context
        # for each display. If we don't, then strange
        # refresh problems will occur.
        if platform.system() == 'Darwin' and \
           'software' in fslplatform.glRenderer.lower():
            
            log.debug('Creating separate GL context for '
                      'WXGLCanvasTarget {}'.format(id(self)))

            context = wxgl.GLContext(self, other=context)

        self.__glReady = False
        self.__frozen  = False
        self.__context = context

        self.Bind(wx.EVT_PAINT,            self.__onPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.__onEraseBackground)

        
    def __onEraseBackground(self, ev):
        """Called on ``wx.EVT_ERASE_BACKGROUND`` events. Does nothing. """
        pass

    
    def __onPaint(self, ev):
        """Called on ``wx.EVT_PAINT`` events. Schedules :meth:`Refresh`
        to be called on the idle loop.
        """

        # GL canvases do need to be refreshed
        # on EVT_PAINT events. If they are not,
        # the canvas will be corrupted.
        async.idle(self.Refresh)
 

    def _initGL(self):
        """This method should perform any OpenGL data initialisation required
        for rendering. Must be implemented by subclasses.
        """
        raise NotImplementedError()


    def _draw(self, *a):
        """This method should implement the OpenGL drawing logic - it must be
        implemented by subclasses.

        .. note:: When runing with an on-screen display, this method should
                  never be called directly - call the :meth:`Refresh` method
                  instead.
        """
        raise NotImplementedError()
 
        
    def __realDraw(self, *a):
        """Called when the canvas needs to be refreshed.

        This method calls :meth:`_initGL` if it has not already been called.
        Otherwise, it calls the subclass :meth:`_draw` method.
        """

        import wx

        def doInit(*a):
            self.__glReady = True
            self._initGL()

            # The only purpose of __realDraw is to
            # make sure that _initGL has been called
            # before the first call to _draw.  So 
            # after initGL has been called, we replace
            # this method (__realDraw) with _draw.
            self.__realDraw = self._draw
            self._draw()

        if not self.__glReady:
            wx.CallAfter(doInit)
            return

        self._draw()

        
    def _getSize(self):
        """Returns the current canvas size. """
        return self.GetClientSize().Get()

        
    def _setGLContext(self):
        """Configures the GL context for drawing to this canvas.

        This method should be called before any OpenGL operations related to
        this canvas take place (e.g. texture/data creation, drawing, etc).
        """
        if not self.IsShownOnScreen(): return False

        log.debug('Setting context target to {} ({})'.format(
            type(self).__name__, id(self)))
        
        self.__context.SetCurrent(self)
        return True

        
    def _postDraw(self):
        """Called after the scene has been rendered. Swaps the front/back
        buffers, unless the canvas is currently frozen (see :meth:`Freeze`). 
        """
        if not self.__frozen:
            self.SwapBuffers()


    def Refresh(self, *a):
        """Triggers a redraw via the :meth:`_draw` method. """
        self.__realDraw()
        

    def Freeze(self):
        """*Freezes* updates to the canvas. This essentially involves
        inhibiting front/back buffer swaps. See :meth:`Thaw` and
        :meth:`_postDraw`.
        """
        self.__frozen = True

    
    def Thaw(self):
        """Unfreezes canvas updates. """
        self.__frozen = False

        
    def getBitmap(self):
        """Return a (width*height*4) shaped numpy array containing the
        rendered scene as an RGBA bitmap. 
        """
        import OpenGL.GL        as gl
        import numpy            as np

        self._setGLContext()

        width, height = self._getSize()

        # Make sure we're reading
        # from the front buffer
        gl.glReadBuffer(gl.GL_FRONT_LEFT)
        
        bmp = gl.glReadPixels(
            0, 0,
            width, height,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE)
        
        bmp = np.fromstring(bmp, dtype=np.uint8)
        bmp = bmp.reshape((height, width, 4))
        bmp = np.flipud(bmp)

        return bmp        
