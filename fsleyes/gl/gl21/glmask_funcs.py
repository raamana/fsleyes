#!/usr/bin/env python
#
# glmask_funcs.py - OpenGL 2.1 functions used by the GLMask class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides functions which are used by the :class:`.GLMask`
class to render :class:`.Image` overlays in an OpenGL 2.1 compatible manner.
"""


import numpy as np

import fsleyes.gl.shaders as shaders
from . import                glvolume_funcs


def init(self):
    """Calls the :func:`compileShaders` and :func:`updateShaderState`
    functions.
    """
    self.shader = None
    compileShaders(   self)
    updateShaderState(self)


def destroy(self):
    """Destroys the shader programs. """
    self.shader.destroy()
    self.shader = None


def compileShaders(self):
    """Loads the vertex/fragment shader source code, and creates a
    :class:`.GLSLShader` program.
    """

    if self.shader is not None:
        self.shader.destroy()

    vertSrc = shaders.getVertexShader(  'glvolume')
    fragSrc = shaders.getFragmentShader('glmask')

    self.shader = shaders.GLSLShader(vertSrc, fragSrc)


def updateShaderState(self):
    """Updates all shader program variables. """

    if not self.ready():
        return

    opts       = self.opts
    shader     = self.shader
    imageShape = np.array(self.image.shape[:3])
    vvx        = self.imageTexture.voxValXform

    shader.load()

    changed  = False
    changed |= shader.set('imageTexture',  0)
    changed |= shader.set('voxValXform',   vvx)
    changed |= shader.set('imageShape',    imageShape)
    changed |= shader.set('threshold',     self.getThreshold())
    changed |= shader.set('invert',        opts.invert)
    changed |= shader.set('colour',        self.getColour())

    shader.unload()

    return changed


def draw2D(self, zpos, axes, *args, **kwargs):
    """Draws the mask overlay in 2D. See :meth:`.GLObject.draw2D`."""
    glvolume_funcs.draw2D(self, zpos, axes, *args, **kwargs)


def drawAll(self, axes, *args, **kwargs):
    """Draws the mask overlay in 2D. See :meth:`.GLObject.draw2D`."""
    glvolume_funcs.drawAll(self, axes, *args, **kwargs)


preDraw  = glvolume_funcs.preDraw
draw3D   = glvolume_funcs.draw3D
postDraw = glvolume_funcs.postDraw