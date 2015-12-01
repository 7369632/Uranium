# Copyright (c) 2015 Ultimaker B.V.
# Uranium is released under the terms of the AGPLv3 or higher.

from PyQt5.QtGui import QColor, QOpenGLBuffer, QOpenGLContext, QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat, QSurfaceFormat, QOpenGLVersionProfile, QImage

from UM.Application import Application
from UM.View.Renderer import Renderer
from UM.Math.Vector import Vector
from UM.Math.Matrix import Matrix
from UM.Resources import Resources
from UM.Logger import Logger
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.Scene.Selection import Selection
from UM.Scene.PointCloudNode import PointCloudNode
from UM.Math.Color import Color

from UM.Mesh.MeshBuilder import MeshBuilder
from UM.View.CompositePass import CompositePass
from UM.View.DefaultPass import DefaultPass
from UM.View.SelectionPass import SelectionPass
from UM.View.GL.OpenGL import OpenGL
from UM.View.RenderBatch import RenderBatch
from UM.Qt.GL.QtOpenGL import QtOpenGL

import numpy
import copy
from ctypes import c_void_p

vertexBufferProperty = "__qtgl2_vertex_buffer"
indexBufferProperty = "__qtgl2_index_buffer"

##  A Renderer implementation using OpenGL2 to render.
class QtRenderer(Renderer):
    def __init__(self):
        super().__init__()

        self._controller = Application.getInstance().getController()
        self._scene = self._controller.getScene()

        self._vertex_buffer_cache = {}
        self._index_buffer_cache = {}

        self._initialized = False

        self._light_position = Vector(0, 0, 0)
        self._background_color = QColor(128, 128, 128)
        self._viewport_width = 0
        self._viewport_height = 0
        self._window_width = 0
        self._window_height = 0

        self._batches = []

        self._quad_geometry = None

        self._camera = None

    def getPixelMultiplier(self):
        # Standard assumption for screen pixel density is 96 DPI. We use that as baseline to get
        # a multiplication factor we can use for screens > 96 DPI.
        return round(Application.getInstance().primaryScreen().physicalDotsPerInch() / 96.0)

    def getBatches(self):
        return self._batches

    def addRenderPass(self, render_pass):
        super().addRenderPass(render_pass)
        render_pass.setSize(self._viewport_width, self._viewport_height)

    ##  Set background color of the rendering.
    def setBackgroundColor(self, color):
        self._background_color = color

    def setViewportSize(self, width, height):
        self._viewport_width = width
        self._viewport_height = height

        for render_pass in self._render_passes:
            render_pass.setSize(width, height)

    def setWindowSize(self, width, height):
        self._window_width = width
        self._window_height = height

    def getWindowSize(self):
        return (self._window_width, self._window_height)

    def beginRendering(self):
        if not self._initialized:
            self._initialize()

        self._gl.glViewport(0, 0, self._viewport_width, self._viewport_height)
        self._gl.glClearColor(self._background_color.redF(), self._background_color.greenF(), self._background_color.blueF(), self._background_color.alphaF())
        self._gl.glClear(self._gl.GL_COLOR_BUFFER_BIT | self._gl.GL_DEPTH_BUFFER_BIT)
        self._gl.glClearColor(0.0, 0.0, 0.0, 0.0)

    ##  Put a node in the render queue
    def queueNode(self, node, **kwargs):
        type = RenderBatch.RenderType.Solid
        if kwargs.get("transparent", False):
            type = RenderBatch.RenderType.Transparent
        elif kwargs.get("overlay", False):
            type = RenderBatch.RenderType.Overlay

        batch = RenderBatch(
            type = type,
            mode = kwargs.get("mode", RenderBatch.RenderMode.Triangles),
            shader = kwargs.get("shader", self._default_material),
            backface_cull = kwargs.get("backface_cull", True),
            range = kwargs.get("range", None)
        )

        batch.addItem(node.getWorldTransformation(), kwargs.get("mesh", node.getMeshData()))

        self._batches.append(batch)


        #queue_item = { "node": node }

        #if "mesh" in kwargs:
            #queue_item["mesh"] = kwargs["mesh"]

        #queue_item["material"] = kwargs.get("material", self._default_material)

        #mode = kwargs.get("mode", Renderer.RenderTriangles)
        #if mode is Renderer.RenderLines:
            #queue_item["mode"] = self._gl.GL_LINES
        #elif mode is Renderer.RenderLineLoop:
            #queue_item["mode"] = self._gl.GL_LINE_LOOP
        #elif mode is Renderer.RenderPoints:
            #queue_item["mode"] = self._gl.GL_POINTS
        #else:
            #queue_item["mode"] = self._gl.GL_TRIANGLES

        #queue_item["wireframe"] = (mode == Renderer.RenderWireframe)

        #queue_item["force_single_sided"] = kwargs.get("force_single_sided", False)

        #if kwargs.get("end", None):
            #queue_item["range"] = [kwargs.get("start", 0), kwargs.get("end")]

        #if kwargs.get("transparent", False):
            #self._transparent_queue.append(queue_item)
        #elif kwargs.get("overlay", False):
            #self._overlay_queue.append(queue_item)
        #else:
            #self._solids_queue.append(queue_item)
    
    ##  Render all nodes in the queue
    def renderQueuedNodes(self):
        self._batches.sort()

        for render_pass in self.getRenderPasses():
            render_pass.render()

        #self._gl.glEnable(self._gl.GL_DEPTH_TEST)
        #self._gl.glDepthFunc(self._gl.GL_LESS)
        #self._gl.glDepthMask(self._gl.GL_TRUE)
        #self._gl.glDisable(self._gl.GL_CULL_FACE)
        #self._gl.glLineWidth(self.getPixelMultiplier())

        #self._scene.acquireLock()

        #self._camera = self._scene.getActiveCamera()
        #if not self._camera:
            #Logger.log("e", "No active camera set, can not render")
            #self._scene.releaseLock()
            #return

        ## Render the selection image
        #selectable_nodes = []
        #for node in DepthFirstIterator(self._scene.getRoot()):
            #if node.isSelectable() and node.getMeshData():
                #selectable_nodes.append(node)

        #if not selectable_nodes:
            #self._selection_image = None

        #if selectable_nodes:
            ##TODO: Use a limited area around the mouse rather than a full viewport for rendering
            #if self._selection_buffer.width() != self._viewport_width or self._selection_buffer.height() != self._viewport_height:
                #self._selection_buffer = self.createFrameBuffer(self._viewport_width, self._viewport_height)

            #self._selection_buffer.bind()
            #self._gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            #self._gl.glClear(self._gl.GL_COLOR_BUFFER_BIT | self._gl.GL_DEPTH_BUFFER_BIT)
            #self._gl.glDisable(self._gl.GL_BLEND)
            #self._selection_map.clear()
            #for node in selectable_nodes:
                #if type(node) is PointCloudNode: #Pointcloud node sets vertex color (to be used for point precise selection)
                    #self._renderItem({
                        #"node": node,
                        #"material": self._handle_material,
                        #"mode": self._gl.GL_POINTS
                    #})
                #else :
                    #color = self._getObjectColor(node)
                    #self._selection_map[color] = id(node)
                    #self._selection_material.setUniformValue("u_color", color)
                    #self._renderItem({
                        #"node": node,
                        #"material": self._selection_material,
                        #"mode": self._gl.GL_TRIANGLES
                    #})
            #tool = self._controller.getActiveTool()
            #if tool:
                #tool_handle = tool.getHandle()
                #if tool_handle and tool_handle.getSelectionMesh() and tool_handle.getParent():
                    #self._selection_map.update(tool_handle.getSelectionMap())
                    #self._gl.glDisable(self._gl.GL_DEPTH_TEST)
                    #self._renderItem({
                        #"node": tool_handle,
                        #"mesh": tool_handle.getSelectionMesh(),
                        #"material": self._handle_material,
                        #"mode": self._gl.GL_TRIANGLES
                    #})
                    #self._gl.glEnable(self._gl.GL_DEPTH_TEST)

            #self._selection_image = self._selection_buffer.toImage()
            #self._selection_buffer.release()

        # Workaround for a MacOSX Intel HD Graphics 6000 Bug
        # Apparently, performing a glReadPixels call on a bound framebuffer breaks releasing the
        # depth buffer, which means the rest of the depth tested geometry never renders. To work-
        # around this we perform a clear here. Note that for some reason we also need to set
        # glClearColor since it is apparently not stored properly.
        #self._gl.glClearColor(self._background_color.redF(), self._background_color.greenF(), self._background_color.blueF(), self._background_color.alphaF())
        #self._gl.glClear(self._gl.GL_COLOR_BUFFER_BIT | self._gl.GL_DEPTH_BUFFER_BIT)

        #self._gl.glEnable(self._gl.GL_STENCIL_TEST)
        #self._gl.glStencilMask(0xff)
        #self._gl.glClearStencil(0)
        #self._gl.glClear(self._gl.GL_STENCIL_BUFFER_BIT)
        #self._gl.glStencilFunc(self._gl.GL_ALWAYS, 0xff, 0xff)
        #self._gl.glStencilOp(self._gl.GL_REPLACE, self._gl.GL_REPLACE, self._gl.GL_REPLACE)
        #self._gl.glStencilMask(0)

        #for item in self._solids_queue:
            #if Selection.isSelected(item["node"]):
                #self._gl.glStencilMask(0xff)
                #self._renderItem(item)
                #self._gl.glStencilMask(0)
            #else:
                #self._renderItem(item)

        #if self._render_selection:
            #self._gl.glStencilMask(0)
            #self._gl.glStencilFunc(self._gl.GL_EQUAL, 0, 0xff)
            #self._gl.glLineWidth(2 * self.getPixelMultiplier())
            #for node in Selection.getAllSelectedObjects():
                #if node.getMeshData() and type(node) is not PointCloudNode:
                    #self._renderItem({
                        #"node": node,
                        #"material": self._outline_material,
                        #"mode": self._gl.GL_TRIANGLES,
                        #"wireframe": True
                    #})

            #self._gl.glLineWidth(self.getPixelMultiplier())

        #self._gl.glDisable(self._gl.GL_STENCIL_TEST)
        #self._gl.glDepthMask(self._gl.GL_FALSE)
        #self._gl.glEnable(self._gl.GL_BLEND)
        #self._gl.glEnable(self._gl.GL_CULL_FACE)
        #self._gl.glBlendFunc(self._gl.GL_SRC_ALPHA, self._gl.GL_ONE_MINUS_SRC_ALPHA)

        #for item in self._transparent_queue:
            #self._renderItem(item)

        #self._gl.glDisable(self._gl.GL_DEPTH_TEST)
        #self._gl.glDisable(self._gl.GL_CULL_FACE)

        #for item in self._overlay_queue:
            #self._renderItem(item)

        #self._scene.releaseLock()

    def endRendering(self):
        self._batches.clear()

    def renderFullScreenQuad(self, shader):
        if not self._quad_geometry:
            mb = MeshBuilder()
            mb.addQuad(Vector(-1.0, -1.0, 0.0), Vector(-1.0, 1.0, 0.0), Vector(1.0, 1.0, 0.0), Vector(1.0, -1.0, 0.0))
            self._quad_geometry = mb.getData()
            self._quad_geometry.setVertexUVCoordinates(0, 0.0, 0.0)
            self._quad_geometry.setVertexUVCoordinates(1, 1.0, 1.0)
            self._quad_geometry.setVertexUVCoordinates(2, 0.0, 1.0)
            self._quad_geometry.setVertexUVCoordinates(3, 0.0, 0.0)
            self._quad_geometry.setVertexUVCoordinates(4, 1.0, 0.0)
            self._quad_geometry.setVertexUVCoordinates(5, 1.0, 1.0)

            self._createVertexBuffer(self._quad_geometry)

        self._gl.glDisable(self._gl.GL_DEPTH_TEST)
        self._gl.glDisable(self._gl.GL_BLEND)

        shader.setUniformValue("u_modelViewProjectionMatrix", Matrix())

        vertex_buffer = getattr(self._quad_geometry, vertexBufferProperty)
        vertex_buffer.bind()

        shader.enableAttribute("a_vertex", "vector3f", 0)
        offset = self._quad_geometry.getVertexCount() * 3 * 4

        shader.enableAttribute("a_uvs", "vector2f", offset)
        offset += self._quad_geometry.getVertexCount() * 2 * 4

        self._gl.glDrawArrays(self._gl.GL_TRIANGLES, 0, self._quad_geometry.getVertexCount())

        shader.disableAttribute("a_vertex")
        shader.disableAttribute("a_uvs")
        vertex_buffer.release()

    def _initialize(self):
        OpenGL.setInstance(QtOpenGL())
        self._gl = OpenGL.getInstance().getBindingsObject()

        self._default_material = OpenGL.getInstance().createShaderProgram(Resources.getPath(Resources.Shaders, "default.shader"))

        self._render_passes.add(DefaultPass(self._viewport_width, self._viewport_height))
        self._render_passes.add(SelectionPass(self._viewport_width, self._viewport_height))
        self._render_passes.add(CompositePass(self._viewport_width, self._viewport_height))

        self._initialized = True

    def _renderItem(self, item):
        node = item["node"]
        mesh = item.get("mesh", node.getMeshData())
        if not mesh:
            return #Something went wrong, node has no mesh.
        transform = node.getWorldTransformation()
        material = item["material"]
        mode = item["mode"]
        wireframe = item.get("wireframe", False)
        range = item.get("range", None)

        culling_enabled = self._gl.glIsEnabled(self._gl.GL_CULL_FACE)
        if item.get("force_single_sided") and not culling_enabled:
            self._gl.glEnable(self._gl.GL_CULL_FACE)

        material.bind()
        material.setUniformValue("u_projectionMatrix", self._camera.getProjectionMatrix(), cache = False)
        material.setUniformValue("u_viewMatrix", self._camera.getWorldTransformation().getInverse(), cache = False)
        material.setUniformValue("u_viewPosition", self._camera.getWorldPosition(), cache = False)
        material.setUniformValue("u_modelMatrix", transform, cache = False)
        material.setUniformValue("u_lightPosition", self._camera.getWorldPosition() + Vector(0, 50, 0), cache = False)

        if mesh.hasNormals():
            normal_matrix = copy.deepcopy(transform)
            normal_matrix.setRow(3, [0, 0, 0, 1])
            normal_matrix.setColumn(3, [0, 0, 0, 1])
            normal_matrix = normal_matrix.getInverse().getTransposed()
            material.setUniformValue("u_normalMatrix", normal_matrix, cache = False)

        vertex_buffer = None
        try:
            vertex_buffer = getattr(mesh, vertexBufferProperty)
        except AttributeError:
            pass

        if vertex_buffer is None:
            vertex_buffer =  self._createVertexBuffer(mesh)

        vertex_buffer.bind()

        if mesh.hasIndices():
            index_buffer = None
            try:
                index_buffer = getattr(mesh, indexBufferProperty)
            except AttributeError:
                pass

            if index_buffer is None:
                index_buffer = self._createIndexBuffer(mesh)

            index_buffer.bind()

        material.enableAttribute("a_vertex", "vector3f", 0)
        offset = mesh.getVertexCount() * 3 * 4

        if mesh.hasNormals():
            material.enableAttribute("a_normal", "vector3f", offset)
            offset += mesh.getVertexCount() * 3 * 4

        if mesh.hasColors():
            material.enableAttribute("a_color", "vector4f", offset)
            offset += mesh.getVertexCount() * 4 * 4

        if mesh.hasUVCoordinates():
            material.enableAttribute("a_uvs", "vector2f", offset)
            offset += mesh.getVertexCount() * 2 * 4

        if wireframe and hasattr(self._gl, "glPolygonMode"):
            self._gl.glPolygonMode(self._gl.GL_FRONT_AND_BACK, self._gl.GL_LINE)

        if mesh.hasIndices():
            if range is None:
                if mode == self._gl.GL_TRIANGLES:
                    self._gl.glDrawElements(mode, mesh.getFaceCount() * 3 , self._gl.GL_UNSIGNED_INT, None)
                else:
                    self._gl.glDrawElements(mode, mesh.getFaceCount(), self._gl.GL_UNSIGNED_INT, None)
            else:
                if mode == self._gl.GL_TRIANGLES:
                    self._gl.glDrawRangeElements(mode, range[0], range[1], range[1] - range[0], self._gl.GL_UNSIGNED_INT, None)
                else:
                    self._gl.glDrawRangeElements(mode, range[0], range[1], range[1] - range[0], self._gl.GL_UNSIGNED_INT, None)
        else:
            self._gl.glDrawArrays(mode, 0, mesh.getVertexCount())

        if wireframe and hasattr(self._gl, "glPolygonMode"):
            self._gl.glPolygonMode(self._gl.GL_FRONT_AND_BACK, self._gl.GL_FILL)

        material.disableAttribute("a_vertex")
        material.disableAttribute("a_normal")
        material.disableAttribute("a_color")
        material.disableAttribute("a_uvs")
        vertex_buffer.release()

        if mesh.hasIndices():
            index_buffer.release()

        material.release()

        if item.get("force_single_sided") and not culling_enabled:
            self._gl.glDisable(self._gl.GL_CULL_FACE)

    def _createVertexBuffer(self, mesh):
        buffer = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        buffer.create()
        buffer.bind()

        buffer_size = mesh.getVertexCount() * 3 * 4 # Vertex count * number of components * sizeof(float32)
        if mesh.hasNormals():
            buffer_size += mesh.getVertexCount() * 3 * 4 # Vertex count * number of components * sizeof(float32)
        if mesh.hasColors():
            buffer_size += mesh.getVertexCount() * 4 * 4 # Vertex count * number of components * sizeof(float32)
        if mesh.hasUVCoordinates():
            buffer_size += mesh.getVertexCount() * 2 * 4 # Vertex count * number of components * sizeof(float32)

        buffer.allocate(buffer_size)

        offset = 0
        vertices = mesh.getVerticesAsByteArray()
        if vertices is not None:
            buffer.write(0, vertices, len(vertices))
            offset += len(vertices)

        if mesh.hasNormals():
            normals = mesh.getNormalsAsByteArray()
            buffer.write(offset, normals, len(normals))
            offset += len(normals)

        if mesh.hasColors():
            colors = mesh.getColorsAsByteArray()
            buffer.write(offset, colors, len(colors))
            offset += len(colors)

        if mesh.hasUVCoordinates():
            uvs = mesh.getUVCoordinatesAsByteArray()
            buffer.write(offset, uvs, len(uvs))
            offset += len(uvs)

        buffer.release()

        setattr(mesh, vertexBufferProperty, buffer)
        return buffer

    def _createIndexBuffer(self, mesh):
        buffer = QOpenGLBuffer(QOpenGLBuffer.IndexBuffer)
        buffer.create()
        buffer.bind()

        data = mesh.getIndicesAsByteArray()
        buffer.allocate(data, len(data))
        buffer.release()

        setattr(mesh, indexBufferProperty, buffer)
        return buffer
    
    ##  Create object color based on ID of node.
    #   \param node Node to get color for
    #   \return Color
    def _getObjectColor(self, node):
        obj_id = id(node)
        r = (obj_id & 0xff000000) >> 24
        g = (obj_id & 0x00ff0000) >> 16
        b = (obj_id & 0x0000ff00) >> 8
        a = (obj_id & 0x000000ff) >> 0
        return Color(r, g, b, a)
