#!/usr/bin/env python
#
# selectiontexture.py - The SelectionTexture class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`SelectionTexture2D` and
:class:`SelectionTexture3D` classes, :class:`.Texture` types which can be used
to store :class:`.Selection` instances.

The ``SelectionTexture2D/3D`` classes are used by the :class:`.VoxelSelection`
annotation to display the contents of a :class:`.Selection` instance.
"""


import logging

import numpy     as np
import OpenGL.GL as gl

from . import       texture2d
from . import       texture3d


log = logging.getLogger(__name__)


class SelectionTextureBase(object):
    """Base class shared by the :class:`SelectionTexture2D` and
    :class:`SelectionTexture3D`. Manages updates from the :class:`.Selection`
    object.
    """

    def __init__(self, selection):
        """
        This method must be called *after* :meth:`.Texture.__init__`.
        """
        self.__selection = selection
        selection.register(self.name, self.__selectionChanged)
        self.__selectionChanged()


    @property
    def selection(self):
        """Returns a reference to the :class:`.Selection` object. """
        return self.__selection


    def destroy(self):
        """Must be called when this ``SelectionTextureBase`` is no longer
        needed. Removes the listener on the :attr:`.Selection.selection`
        property.
        """
        self.__selection.deregister(self.name)
        self.__selection = None


    def __selectionChanged(self, *a):
        """Called when the :attr:`.Selection.selection` changes. Updates
        the texture data via the :meth:`.Texture.doPatch` method.
        """

        old, new, offset = self.__selection.getLastChange()

        if new is None:
            data = self.__selection.getSelection()
            data = (data * 255).astype(np.uint8)
            self.set(data=data)

        else:
            data = (new * 255).astype(np.uint8)
            self.doPatch(data, offset)


class SelectionTexture3D(texture3d.Texture3D, SelectionTextureBase):
    """The ``SelectionTexture3D`` class is a :class:`.Texture3D` which can be
    used to store a :class:`.Selection` instance.  The ``Selection`` image
    array is stored as a single channel 3D texture, which is updated whenever
    the :attr:`.Selection.selection` property changes - updates are managed by
    the :class:`SelectionTextureBase` class.
    """


    def __init__(self, name, selection):
        """Create a ``SelectionTexture3D``.

        :arg name:      A unique name for this ``SelectionTexture3D``.
        :arg selection: The :class:`.Selection` instance.
        """

        texture3d.Texture3D .__init__(self,
                                      name,
                                      nvals=1,
                                      textureFormat=gl.GL_ALPHA,
                                      internalFormat=gl.GL_ALPHA8)
        SelectionTextureBase.__init__(self, selection)


    def destroy(self):
        """Must be called when this ``SelectionTexture3D`` is no longer needed.
        Calls the :meth:`.Texture.destroy` method, and removes the listener
        on the :attr:`.Selection.selection` property.
        """
        texture3d.Texture3D .destroy(self)
        SelectionTextureBase.destroy(self)


class SelectionTexture2D(texture2d.Texture2D, SelectionTextureBase):
    """The ``SelectionTexture2D`` class is a :class:`.Texture2D` which can be
    used to store a :class:`.Selection` instance.  The ``Selection`` image
    array is stored as a single channel 2D texture, which is updated whenever
    the :attr:`.Selection.selection` property changes - updates are managed by
    the :class:`SelectionTextureBase` class..
    """


    def __init__(self, name, selection):
        """Create a ``SelectionTexture2D``.

        :arg name:      A unique name for this ``SelectionTexture2D``.
        :arg selection: The :class:`.Selection` instance.
        """

        texture2d.Texture2D .__init__(self,
                                      name,
                                      nvals=1,
                                      textureFormat=gl.GL_ALPHA,
                                      internalFormat=gl.GL_ALPHA8)
        SelectionTextureBase.__init__(self, selection)


    def destroy(self):
        """Must be called when this ``SelectionTexture2D`` is no longer needed.
        Calls the :meth:`.Texture.destroy` method, and removes the listener
        on the :attr:`.Selection.selection` property.
        """
        texture2d.Texture2D .destroy(self)
        SelectionTextureBase.destroy(self)
