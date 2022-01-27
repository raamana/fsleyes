#!/usr/bin/env python
#
# glmesh_funcs.py - OpenGL 2.1 functions used by the GLMesh class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides functions which are used by the :class:`.GLMesh`
class to render :class:`.Mesh` overlays in an OpenGL 2.1 compatible
manner.

A :class:`.GLSLShader` is used to manage the ``glmesh`` vertex/fragment
shader programs.
"""


import OpenGL.GL as gl

import fsl.transform.affine as affine
import fsleyes.gl.shaders   as shaders


def compileShaders(self):
    """Loads the ``glmesh`` vertex/fragment shader source and creates
    :class:`.GLSLShader` instance(s).
    """

    if self.threedee:

        flatVertSrc = shaders.getVertexShader(  'glmesh_3d_flat')
        flatFragSrc = shaders.getFragmentShader('glmesh_3d_flat')
        dataVertSrc = shaders.getVertexShader(  'glmesh_3d_data')
        dataFragSrc = shaders.getFragmentShader('glmesh_3d_data')

        self.flatShader = shaders.GLSLShader(flatVertSrc,
                                             flatFragSrc,
                                             indexed=True)
        self.dataShader = shaders.GLSLShader(dataVertSrc,
                                             dataFragSrc,
                                             indexed=True)

    else:

        flatVertSrc    = shaders.getVertexShader(  'glmesh_2d_flat')
        flatFragSrc    = shaders.getFragmentShader('glmesh_2d_flat')
        dataVertSrc    = shaders.getVertexShader(  'glmesh_2d_data')
        dataFragSrc    = shaders.getFragmentShader('glmesh_2d_data')
        xsectcpVertSrc = shaders.getVertexShader(  'glmesh_2d_crosssection_clipplane')
        xsectcpFragSrc = shaders.getFragmentShader('glmesh_2d_crosssection_clipplane')
        xsectblVertSrc = shaders.getVertexShader(  'glmesh_2d_crosssection_blit')
        xsectblFragSrc = shaders.getFragmentShader('glmesh_2d_crosssection_blit')

        self.dataShader    = shaders.GLSLShader(dataVertSrc,    dataFragSrc)
        self.flatShader    = shaders.GLSLShader(flatVertSrc,    flatFragSrc)
        self.xsectcpShader = shaders.GLSLShader(xsectcpVertSrc, xsectcpFragSrc)
        self.xsectblShader = shaders.GLSLShader(xsectblVertSrc, xsectblFragSrc)


def updateShaderState(self, **kwargs):
    """Updates the shader program according to the current :class:`.MeshOpts``
    configuration.
    """

    dopts      = self.opts
    dshader    = self.dataShader
    fshader    = self.flatShader
    xscpshader = self.xsectcpShader
    xsblshader = self.xsectblShader

    dshader.load()
    dshader.set('cmap',           0)
    dshader.set('negCmap',        1)
    dshader.set('useNegCmap',     kwargs['useNegCmap'])
    dshader.set('cmapXform',      kwargs['cmapXform'])
    dshader.set('flatColour',     kwargs['flatColour'])
    dshader.set('invertClip',     dopts.invertClipping)
    dshader.set('discardClipped', dopts.discardClipped)
    dshader.set('modulateAlpha',  dopts.modulateAlpha)
    dshader.set('modScale',       kwargs['modScale'])
    dshader.set('modOffset',      kwargs['modOffset'])
    dshader.set('clipLow',        dopts.clippingRange.xlo)
    dshader.set('clipHigh',       dopts.clippingRange.xhi)

    if self.threedee:
        dshader.setAtt('vertex', self.vertices)
        dshader.setAtt('normal', self.normals)

        vdata = self.getVertexData('vertex')
        mdata = self.getVertexData('modulate')

        # if modulate data is not set,
        # we use the vertex data
        if mdata is None:
            mdata = vdata

        if vdata is not None: dshader.setAtt('vertexData',   vdata.ravel('C'))
        if mdata is not None: dshader.setAtt('modulateData', mdata.ravel('C'))

        dshader.setIndices(self.indices)

    dshader.unload()

    with xscpshader.loaded():
        xscpshader.setAtt('vertex', self.vertices)
        xscpshader.setIndices(      self.indices)
    with xsblshader.loaded():
        xsblshader.set('colour', kwargs['flatColour'])
    with fshader.loaded():
        fshader.set('colour', kwargs['flatColour'])
        if self.threedee:
            fshader.setAtt('vertex', self.vertices)
            fshader.setAtt('normal', self.normals)
            fshader.setIndices(self.indices)


def draw(self,
         glType,
         vertices,
         indices=None,
         normals=None,
         vdata=None,
         mdata=None,
         xform=None):
    """Called for 3D meshes, and when :attr:`.MeshOpts.vertexData` is not
    ``None``. Loads and runs the shader program.

    :arg glType:   The OpenGL primitive type.

    :arg vertices: ``(n, 3)`` array containing the mesh vertices to draw.

    :arg indices:  Indices into the ``vertices`` array. If not provided,
                   ``glDrawArrays`` is used.

    :arg normals:  Vertex normals.

    :arg vdata:    ``(n, )`` array containing data for each vertex.

    :arg mdata:    ``(n, )`` array containing alpha modulation data for
                   each vertex.

    :arg xform:    Transformation matrix to apply to the vertices, in
                   addition to the canvas mvp matrix.
    """

    canvas = self.canvas
    mvmat  = canvas.viewMatrix
    mvpmat = canvas.mvpMatrix

    if xform is not None:
        mvmat  = affine.concat(mvmat,  xform)
        mvpmat = affine.concat(mvpmat, xform)

    # for 3D, shader attributes are
    # configured in updateShaderState
    if self.threedee:
        vertices = None
        normals  = None
        vdata    = None
        mdata    = None

    shader.set('MVP', mvpmat)

    if vertices is not None: shader.setAtt('vertex',       vertices)
    if normals  is not None: shader.setAtt('normal',       normals)
    if vdata    is not None: shader.setAtt('vertexData',   vdata)
    if mdata    is not None: shader.setAtt('modulateData', mdata)

    if self.threedee:

        normmat  = affine.invert(mvmat[:3, :3]).T
        lightPos = affine.transform(canvas.lightPos, mvmat)

        shader.set('lighting',  canvas.opts.light)
        shader.set('lightPos',  lightPos)
        shader.set('MV',        mvmat)
        shader.set('normalmat', normmat)

    if indices is None:
        gl.glDrawArrays(glType, 0, vertices.shape[0])
    else:
        nverts = indices.shape[0]
        if self.threedee:
            indices = None
        gl.glDrawElements(glType, nverts, gl.GL_UNSIGNED_INT, indices)
