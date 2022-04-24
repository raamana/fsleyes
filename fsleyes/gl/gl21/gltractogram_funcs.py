#!/usr/bin/env python
#
# gltractogram_funcs.py - GL21 functions for drawing tractogram overlays.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module comtains functions for drawing tractogram overlays witg OpenGL
2.1. These functions are used by :class:`.GLTractogram` instances.
"""

import itertools as it
import OpenGL.GL as gl
import numpy     as np

import fsl.transform.affine  as affine
import fsleyes.gl.routines   as glroutines
import fsleyes.gl.extensions as glexts
import fsleyes.gl.shaders    as shaders


def compileShaders(self):
    """Called by :meth:`.GLTractogram.compileShaders`.
    Compiles shader programs.
    """

    # See comments in gl33.gltractogram_funcs.compileShaders
    vsrc       = shaders.getVertexShader(  'gltractogram')
    orientfsrc = shaders.getFragmentShader('gltractogram_orient')
    vdatafsrc  = shaders.getFragmentShader('gltractogram_vertex_data')
    idatafsrc  = shaders.getFragmentShader('gltractogram_image_data')

    colourSources = {
        'orientation' : orientfsrc,
        'vertexData'  : vdatafsrc,
        'imageData'   : idatafsrc,
    }

    colourModes = ['orientation', 'vertexData', 'imageData']
    clipModes   = ['none',        'vertexData', 'imageData']
    kwa         = {'resourceName' : f'GLTractogram_{id(self)}',
                   'shared'       : ['vertex']}

    for colourMode, clipMode in it.product(colourModes, clipModes):

        fsrc   = colourSources[colourMode]
        consts = {
            'colourMode' : colourMode,
            'clipMode'   : clipMode,
            'lighting'   : False,
            'twod'       : not self.threedee,
        }
        shader = shaders.GLSLShader(vsrc, fsrc, constants=consts, **kwa)

        self.shaders[colourMode][clipMode].append(shader)


def draw2D(self, axes, mvp):
    """Called by :class:`.GLTractogram.draw2D`. """

    opts       = self.opts
    colourMode = opts.effectiveColourMode
    clipMode   = opts.effectiveClipMode
    res        = opts.resolution
    shader     = self.shaders[colourMode][clipMode][0]

    if res >= 4:
        vertices = glroutines.unitCircle(res, axes)
        prim     = gl.GL_TRIANGLE_FAN

    else:
        vertices = np.zeros((1, 3))
        prim     = gl.GL_POINTS
        gl.glPointSize(5)

    gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)

    with shader.loaded(), shader.loadedAtts():
        shader.set(   'MVP',          mvp)
        shader.setAtt('circleVertex', vertices)

        glexts.glDrawArraysInstanced(prim,
                                     0,
                                     len(vertices),
                                     len(self.vertices))


def draw3D(self, xform=None):
    """Called by :class:`.GLTractogram.draw3D`. """
    canvas     = self.canvas
    opts       = self.opts
    ovl        = self.overlay
    display    = self.display
    colourMode = opts.effectiveColourMode
    clipMode   = opts.effectiveClipMode
    vertXform  = ovl.affine
    mvp        = canvas.mvpMatrix
    mv         = canvas.viewMatrix
    nstrms     = ovl.nstreamlines
    lineWidth  = opts.lineWidth
    offsets    = self.offsets
    counts     = self.counts
    nstrms     = len(offsets)

    shader = self.shaders[colourMode][clipMode][0]

    if xform is None: xform = vertXform
    else:             xform = affine.concat(xform, vertXform)

    mvp = affine.concat(mvp, xform)
    mv  = affine.concat(mv,  xform)

    with shader.loaded(), shader.loadedAtts():
        shader.set('MVP', mvp)
        # See comments in gl33.gltractogram_funcs.draw3D
        with glroutines.enabled(gl.GL_CULL_FACE):
            gl.glLineWidth(lineWidth)
            gl.glCullFace(gl.GL_BACK)
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
            if display.alpha < 100 or opts.modulateAlpha:
                gl.glMultiDrawArrays(gl.GL_LINE_STRIP, offsets, counts, nstrms)
            with glroutines.enabled(gl.GL_DEPTH_TEST):
                gl.glMultiDrawArrays(gl.GL_LINE_STRIP, offsets, counts, nstrms)
