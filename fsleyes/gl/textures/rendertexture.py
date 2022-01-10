#!/usr/bin/env python
#
# rendertexture.py - The RenderTexture and GLObjectRenderTexture classes.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`RenderTexture` and
:class:`GLObjectRenderTexture` classes, which are :class:`.Texture2D`
sub-classes intended to be used as targets for off-screen rendering.

These classes are used by the :class:`.SliceCanvas` and
:class:`.LightBoxCanvas` classes for off-screen rendering, and in various
other situations throughout FSLeyes. See also the
:class:`.RenderTextureStack`, which uses :class:`RenderTexture` instances.
"""


import logging
import contextlib

import numpy                             as np
import OpenGL.GL                         as gl
import OpenGL.raw.GL._types              as gltypes
import OpenGL.GL.EXT.framebuffer_object  as glfbo

import fsleyes.gl          as fslgl
import fsleyes.gl.routines as glroutines
import fsleyes.gl.shaders  as shaders
from . import                 texture2d


log = logging.getLogger(__name__)


class RenderTexture(texture2d.Texture2D):
    """The ``RenderTexture`` class is a 2D RGBA texture which manages a frame
    buffer, and a render buffer or a :class:`.DepthTexture` which is used as
    the depth attachment.

    A ``RenderTexture`` is intended to be used as a target for off-screen
    rendering. Using a ``RenderTexture`` (``tex`` in the example below) as the
    rendering target is easy::

        # Set the texture size in pixels
        tex.shape = 1024, 768

        # Bind the texture/frame buffer, and configure
        # the viewport for orthoghraphic display.
        lo = (0.0, 0.0, 0.0)
        hi = (1.0, 1.0, 1.0)

        with tex.target(0, 1, lo, hi):
            # ...
            # draw the scene
            # ...


    The contents of the ``RenderTexture`` can later be drawn to the screen
    via the :meth:`.Texture2D.draw` or :meth:`.Texture2D.drawOnBounds`
    methods.


    A ``RenderTexture`` can be configured in one of three ways:

      1. Using a ``RGBA8`` :class:`.Texture2D` (the ``RenderTexture`` itself)
         as the colour attachment, and no depth or stencil attachments.

      2. As above for the colour attachment, and a :class:`.DepthTexture` as
         the depth attachment.

      3. As above for the colour attachment, and a ``DEPTH24_STENCIL8``
         renderbuffer as the combined depth+stencil attachment.


    These are the only available options due to limitations in different GL
    implementations. You can choose which option you wish to use via the
    ``rttype`` argument to ``__init__``.

    If you choose option #2, a :class:`.DepthTexture` instance will be used as
    the depth attachment. The resulting depth values created after drawing to
    the ``RenderTexture`` may be used in subsequent processing.  You can
    either access the depth texture directly via the :meth:`depthTexture`
    method, or you can draw the contents of the ``RenderTexture``, with depth
    information, by passing the ``useDepth`` flag to either the :meth:`draw`
    or :meth:`drawOnBounds` methods.
    """


    def __init__(self, name, rttype='cds', **kwargs):
        """Create a ``RenderTexture``. All keyword arguments are passed through to the
        :meth:`.Texture2D.__init__` method.

        :arg name:   Unique name for this texture

        :arg rttype: ``RenderTexture`` configuration. If provided, must be
                     passed as a keyword argument. Valid values are:

                       - ``'c'``:    Only a colour attachment is configured
                       - ``'cd'``:   Colour and depth attachments are
                                     configured
                       - ``'cds'`` : Colour, depth, and stencil attachments
                                     are configured. This is the default.

        .. note:: A rendering target must have been set for the GL context
                  before a frame buffer can be created ... in other words,
                  call ``context.SetCurrent`` before creating a
                  ``RenderTexture``.
        """

        if rttype not in ('c', 'cd', 'cds'):
            raise ValueError('Invalid rttype: {}'.format(rttype))

        texture2d.Texture2D.__init__(self,
                                     name,
                                     ndim=2,
                                     nvals=4,
                                     dtype=np.uint8,
                                     **kwargs)

        self.__frameBuffer      = glfbo.glGenFramebuffersEXT(1)
        self.__rttype           = rttype
        self.__renderBuffer     = None
        self.__depthTexture     = None
        self.__oldFrameBuffer   = None
        self.__oldRenderBuffer  = None
        self.__oldSize          = None
        self.__projectionMatrix = None
        self.__viewMatrix       = None
        self.__viewport         = None

        # Use a single renderbuffer as
        # the depth+stencil attachment
        if rttype == 'cds':
            self.__renderBuffer = glfbo.glGenRenderbuffersEXT(1)

        # Or use a texture as the depth
        # attachment (with no stencil attachment)
        elif rttype == 'cd':
            self.__depthTexture = texture2d.DepthTexture(
                '{}_depth'.format(self.name))

            # We also need a shader program in
            # case the creator is intending to
            # use the depth information in draws.
            self.__initShader()

        log.debug('Created fbo %s [%s]', self.__frameBuffer, rttype)


    def __initShader(self):
        """Called by :meth:`__init__` if this ``RenderTexture`` was
        configured to use a colour and depth texture. Compiles
        vertex/fragment shader programs which pass the colour and depth
        values through.

        These shaders are used if the :meth:`draw` or
        :meth:`.Texture2D.drawOnBounds` methods are used with the
        ``useDepth=True`` argument.
        """

        self.__shader = None

        vertSrc   = shaders.getVertexShader(  'rendertexture')
        fragSrc   = shaders.getFragmentShader('rendertexture')

        if float(fslgl.GL_COMPATIBILITY) < 2.1:
            self.__shader = shaders.ARBPShader(vertSrc, fragSrc)
        else:
            self.__shader = shaders.GLSLShader(vertSrc, fragSrc)
            self.__shader.load()
            self.__shader.set('colourTexture', 0)
            self.__shader.set('depthTexture',  1)
            self.__shader.unload()


    def destroy(self):
        """Must be called when this ``RenderTexture`` is no longer needed.
        Destroys the frame buffer and render buffer, and calls
        :meth:`.Texture2D.destroy`.
        """

        texture2d.Texture2D.destroy(self)

        log.debug('Deleting FBO%s [%s]', self.__frameBuffer, self.__rttype)

        glfbo.glDeleteFramebuffersEXT(gltypes.GLuint(self.__frameBuffer))

        if self.__renderBuffer is not None:
            rb = gltypes.GLuint(self.__renderBuffer)
            glfbo.glDeleteRenderbuffersEXT(1, rb)

        if self.__depthTexture is not None:
            self.__depthTexture.destroy()

        self.__frameBuffer     = None
        self.__renderBuffer    = None
        self.__depthTexture    = None
        self.__oldFrameBuffer  = None
        self.__oldRenderBuffer = None


    @property
    def projectionMatrix(self):
        """Return the projection matrix to use when drawing to this
        ``RenderTexture``. Only returns a value when this ``RenderTexture``
        is bound - returns ``None``at all other times.
        """
        return self.__projectionMatrix


    @property
    def viewMatrix(self):
        """Return the model-view matrix to use when drawing to this
        ``RenderTexture``. Only returns a value when this ``RenderTexture``
        is bound - returns ``None``at all other times.
        """
        return self.__viewMatrix


    @property
    def viewport(self):
        """Return the display coordinate system bounding box for this
        ``RenderTexture`` as a sequence of three ``(low, high)`` tuples.
        Only returns a value when this ``RenderTexture`` is bound - returns
        ``None``at all other times.
        """
        return self.__viewport


    @texture2d.Texture2D.data.setter
    def data(self, data):
        """Raises a :exc:`NotImplementedError`. The ``RenderTexture`` derives
        from the :class:`.Texture2D` class, but is not intended to have its
        texture data manually set - see the :class:`.Texture2D` documentation.
        """
        raise NotImplementedError('Texture data cannot be set for {} '
                                  'instances'.format(type(self).__name__))


    @property
    def depthTexture(self):
        """Returns the ``DepthTexture`` instance used as the depth buffer.
        Returns ``None`` if this ``RenderTexture`` was not configured with
        ``'cd'`` (see :meth:`__init__`).
        """
        return self.__depthTexture


    @depthTexture.setter
    def depthTexture(self, dtex):
        """Replace the depth texture currently used by this ``RenderTexture``.

        A :exc:`ValueError` is raised if ``dtex`` is not compatible with this
        ``RenderTexture``.

        :arg dtex: A :class:`.DepthTexture` instance
        """

        if self.__depthTexture is None:
            raise ValueError('This RenderTexture is not '
                             'configured to use a depth texture')

        if not isinstance(dtex, texture2d.DepthTexture)    or \
           dtex.internalFormat != gl.GL_DEPTH_COMPONENT24  or \
           dtex.shape          != self.shape:
            raise ValueError('Incompatible depth texture')

        self.__depthTexture = dtex


    @texture2d.Texture2D.shape.setter
    def shape(self, shape):
        """Overrides the :meth:`.Texture2D.shape` setter. Calls that method, and
        also calls it on the depth texture if it exists.
        """

        width, height = shape

        # We have to size the depth texture first,
        # because calling shape on ourselves will
        # result in refresh being called, which
        # expects the depth texture to be ready to
        # go.
        if self.__depthTexture is not None:
            self.__depthTexture.shape = width, height

        texture2d.Texture2D.shape.fset(self, (width, height))


    @contextlib.contextmanager
    def renderViewport(self, xax, yax, lo, hi):
        """Context manager which sets and restores the viewport via
        :meth:`setRenderViewport` and :meth:`restoreViewport`.
        """

        self.setRenderViewport(xax, yax, lo, hi)
        try:
            yield
        finally:
            self.restoreViewport()


    def setRenderViewport(self, xax, yax, lo, hi):
        """Configures the GL viewport for a 2D orthographic display. See the
        :func:`.routines.show2D` function.

        The existing viewport settings are cached, and can be restored via
        the :meth:`restoreViewport` method.

        :arg xax: The display coordinate system axis which corresponds to the
                  horizontal screen axis.

        :arg yax: The display coordinate system axis which corresponds to the
                  vertical screen axis.

        :arg lo:  A tuple containing the minimum ``(x, y, z)`` display
                  coordinates.

        :arg hi:  A tuple containing the maximum ``(x, y, z)`` display
                  coordinates.
        """

        if self.__oldSize is not None:
            raise RuntimeError('RenderTexture RB{}/FBO{} has already '
                               'configured the viewport'.format(
                                   self.__renderBuffer,
                                   self.__frameBuffer))

        log.debug('Configuring viewport for RB%s/FBO%s',
                  self.__renderBuffer, self.__frameBuffer)

        self.__oldSize = gl.glGetIntegerv(gl.GL_VIEWPORT)

        width, height  = self.shape
        projmat, mvmat = glroutines.show2D(xax, yax, lo, hi)

        gl.glViewport(0, 0, width, height)

        self.__viewport         = list(zip(lo, hi))
        self.__projectionMatrix = projmat
        self.__viewMatrix       = mvmat


    def restoreViewport(self):
        """Restores the GL viewport settings which were saved via a prior call
        to :meth:`setRenderViewport`.
        """

        if self.__oldSize is None:
            raise RuntimeError('RenderTexture RB{}/FBO{} has not '
                               'configured the viewport'.format(
                                   self.__renderBuffer,
                                   self.__frameBuffer))

        log.debug('Clearing viewport (from RB%s/FBO%s)',
                  self.__renderBuffer, self.__frameBuffer)

        gl.glViewport(*self.__oldSize)
        self.__oldSize          = None
        self.__projectionMatrix = None
        self.__viewMatrix       = None
        self.__viewport         = None


    @contextlib.contextmanager
    def target(self, *args, **kwargs):
        """Context manager which binds and unbinds this ``RenderTexture`` as
        the render target, via :meth:`bindAsRenderTarget` and
        :meth:`unbindAsRenderTarget`.

        If any arguments are provided, the viewport is also set and restored
        via :meth:`setRenderViewport` and :meth:`restoreViewport`.
        """

        setViewport = len(args) > 0 or len(kwargs) > 0

        self.bindAsRenderTarget()

        if setViewport:
            self.setRenderViewport(*args, **kwargs)
        try:
            yield
        finally:
            if setViewport:
                self.restoreViewport()
            self.unbindAsRenderTarget()


    def bindAsRenderTarget(self):
        """Configures the frame buffer and render buffer of this
        ``RenderTexture`` as the targets for rendering.

        The existing farme buffer and render buffer are cached, and can be
        restored via the :meth:`unbindAsRenderTarget` method.
        """

        if self.__oldFrameBuffer is not None:
            raise RuntimeError('RenderTexture FBO{} is already '
                               'bound'.format(self.__frameBuffer))

        self.__oldFrameBuffer  = gl.glGetIntegerv(
            glfbo.GL_FRAMEBUFFER_BINDING_EXT)

        if self.__renderBuffer is not None:
            self.__oldRenderBuffer = gl.glGetIntegerv(
                glfbo.GL_RENDERBUFFER_BINDING_EXT)

        log.debug('Setting FBO%s as render target', self.__frameBuffer)

        glfbo.glBindFramebufferEXT(
            glfbo.GL_FRAMEBUFFER_EXT, self.__frameBuffer)

        if self.__renderBuffer is not None:
            glfbo.glBindRenderbufferEXT(
                glfbo.GL_RENDERBUFFER_EXT, self.__renderBuffer)


    def unbindAsRenderTarget(self):
        """Restores the frame buffer and render buffer which were saved via a
        prior call to :meth:`bindAsRenderTarget`.
        """

        if self.__oldFrameBuffer is None:
            raise RuntimeError('RenderTexture FBO{} has not been '
                               'bound'.format(self.__frameBuffer))

        log.debug('Restoring render target to FBO%s (from FBO%s)',
                  self.__oldFrameBuffer, self.__frameBuffer)

        glfbo.glBindFramebufferEXT(
            glfbo.GL_FRAMEBUFFER_EXT, self.__oldFrameBuffer)

        if self.__renderBuffer is not None:
            glfbo.glBindRenderbufferEXT(
                glfbo.GL_RENDERBUFFER_EXT, self.__oldRenderBuffer)

        self.__oldFrameBuffer  = None
        self.__oldRenderBuffer = None


    def doRefresh(self):
        """Overrides :meth:`.Texture2D.doRefresh`. Calls the base-class
        implementation, and ensures that the frame buffer and render buffer
        of this ``RenderTexture`` are configured correctly.
        """
        texture2d.Texture2D.doRefresh(self)

        width, height = self.shape

        log.debug('Refreshing render texture FBO%s', self.__frameBuffer)

        # Bind the colour buffer
        with self.target():
            glfbo.glFramebufferTexture2DEXT(
                glfbo.GL_FRAMEBUFFER_EXT,
                glfbo.GL_COLOR_ATTACHMENT0_EXT,
                gl   .GL_TEXTURE_2D,
                self.handle,
                0)

            # Combined depth/stencil attachment
            if self.__rttype == 'cds':

                # Configure the render buffer
                glfbo.glRenderbufferStorageEXT(
                    glfbo.GL_RENDERBUFFER_EXT,
                    gl.GL_DEPTH24_STENCIL8,
                    width,
                    height)

                # Bind the render buffer
                glfbo.glFramebufferRenderbufferEXT(
                    glfbo.GL_FRAMEBUFFER_EXT,
                    gl.GL_DEPTH_STENCIL_ATTACHMENT,
                    glfbo.GL_RENDERBUFFER_EXT,
                    self.__renderBuffer)

            # Or a depth texture
            elif self.__rttype == 'cd':
                glfbo.glFramebufferTexture2DEXT(
                    glfbo.GL_FRAMEBUFFER_EXT,
                    glfbo.GL_DEPTH_ATTACHMENT_EXT,
                    gl   .GL_TEXTURE_2D,
                    self.__depthTexture.handle,
                    0)

            # Get the FBO status before unbinding it -
            # the Apple software renderer will return
            # FRAMEBUFFER_UNDEFINED otherwise.
            status = glfbo.glCheckFramebufferStatusEXT(
                glfbo.GL_FRAMEBUFFER_EXT)

        # Complain if something is not right
        if status != glfbo.GL_FRAMEBUFFER_COMPLETE_EXT:
            raise RuntimeError('An error has occurred while configuring '
                               'the frame buffer [{}]'.format(status))


    def draw(self, *args, **kwargs):
        """Overrides :meth:`.Texture2D.draw`. Calls that method, optionally
        using the information in the depth texture.


        :arg useDepth: Must be passed as a keyword argument. Defaults to
                       ``False``. If ``True``, and this ``RenderTexture``
                       was configured to use a depth texture, the texture
                       is rendered with depth information using a fragment
                       program


        A ``RuntimeError`` will be raised if ``useDepth is True``, but this
        ``RenderTexture`` was not configured appropriately (the ``'cd'``
        setting in :meth:`__init__`).
        """

        useDepth = kwargs.pop('useDepth', False)

        if useDepth and self.__depthTexture is None:
            raise RuntimeError('useDepth is True but I don\'t '
                               'have a depth texture!')

        if useDepth:
            self.__depthTexture.bindTexture(gl.GL_TEXTURE1)
            self.__shader.load()

        texture2d.Texture2D.draw(self, *args, **kwargs)

        if useDepth:
            self.__shader.unload()
            self.__depthTexture.unbindTexture()


class GLObjectRenderTexture(RenderTexture):
    """The ``GLObjectRenderTexture`` is a :class:`RenderTexture` intended to
    be used for rendering :class:`.GLObject` instances off-screen.


    The advantage of using a ``GLObjectRenderTexture`` over a
    :class:`.RenderTexture` is that a ``GLObjectRenderTexture`` will
    automatically adjust its size to suit the resolution of the
    :class:`.GLObject` - see the :meth:`.GLObject.getDataResolution` method.


    In order to accomplish this, the :meth:`setAxes` method must be called
    whenever the display orientation changes, so that the render texture
    size can be re-calculated.
    """

    def __init__(self, name, globj, xax, yax, maxResolution=2048):
        """Create a ``GLObjectRenderTexture``.

        :arg name:          A unique name for this ``GLObjectRenderTexture``.

        :arg globj:         The :class:`.GLObject` instance which is to be
                            rendered.

        :arg xax:           Index of the display coordinate system axis to be
                            used as the horizontal render texture axis.

        :arg yax:           Index of the display coordinate system axis to be
                            used as the vertical render texture axis.

        :arg maxResolution: Maximum resolution in pixels, along either the
                            horizontal or vertical axis, for this
                            ``GLObjectRenderTexture``.
        """

        self.__globj         = globj
        self.__xax           = xax
        self.__yax           = yax
        self.__maxResolution = maxResolution

        RenderTexture.__init__(self, name)

        name = '{}_{}'.format(self.name, id(self))
        globj.register(name, self.__updateShape)

        self.__updateShape()


    def destroy(self):
        """Must be called when this ``GLObjectRenderTexture`` is no longer
        needed. Removes the update listener from the :class:`.GLObject`, and
        calls :meth:`.RenderTexture.destroy`.
        """

        name = '{}_{}'.format(self.name, id(self))
        self.__globj.deregister(name)
        RenderTexture.destroy(self)


    def setAxes(self, xax, yax):
        """This method must be called when the display orientation of the
        :class:`GLObject` changes. It updates the size of this
        ``GLObjectRenderTexture`` so that the resolution and aspect ratio
        of the ``GLOBject`` are maintained.
        """
        self.__xax = xax
        self.__yax = yax
        self.__updateShape()


    @RenderTexture.shape.setter
    def shape(self, shape):
        """Overrides the :meth:`.Texture.shape` setter. Raises a
        :exc:`NotImplementedError`. The size of a ``GLObjectRenderTexture`` is
        set automatically.
        """
        raise NotImplementedError(
            'Texture size cannot be set for {} instances'.format(
                type(self).__name__))


    def __updateShape(self, *a):
        """Updates the size of this ``GLObjectRenderTexture``, basing it
        on the resolution returned by the :meth:`.GLObject.getDataResolution`
        method. If that method returns ``None``, a default resolution is used.
        """
        globj  = self.__globj
        maxRes = self.__maxResolution

        resolution = globj.getDataResolution(self.__xax, self.__yax)

        # Default resolution is based on the canvas size
        if resolution is None:

            size                   = gl.glGetIntegerv(gl.GL_VIEWPORT)
            width                  = size[2]
            height                 = size[3]
            resolution             = [100] * 3
            resolution[self.__xax] = width
            resolution[self.__yax] = height

            log.debug('Using default resolution for GLObject %s: %s',
                      type(globj).__name__, resolution)

        width  = resolution[self.__xax]
        height = resolution[self.__yax]

        if any((width <= 0, height <= 0)):
            raise ValueError('Invalid GLObject resolution: {}'.format(
                (width, height)))

        if width > maxRes or height > maxRes:
            ratio = min(width, height) / float(max(width, height))

            if width > height:
                width  = maxRes
                height = width * ratio
            else:
                height = maxRes
                width  = height * ratio

            width  = int(round(width))
            height = int(round(height))

        log.debug('Setting %s texture resolution to %sx%s',
                  type(globj).__name__, width, height)

        RenderTexture.shape.fset(self, (width, height))
