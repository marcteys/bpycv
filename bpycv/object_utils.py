#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: DIYer22@github
@mail: ylxx@live.com
Created on Sat Dec 28 20:51:37 2019
"""

from boxx import *

import bpy
import numpy as np
from .material_utils import set_vertex_color_material


IMPORT_OPERATOR_PATHS = {
    "stl": ("wm.stl_import", "import_mesh.stl"),
    "obj": ("wm.obj_import", "import_scene.obj"),
    "dae": ("wm.collada_import",),
    "ply": ("wm.ply_import", "import_mesh.ply"),
    "fbx": ("wm.fbx_import", "import_scene.fbx"),
}


def _get_bpy_op(path):
    op = bpy.ops
    for attr in path.split("."):
        try:
            op = getattr(op, attr)
        except AttributeError:
            return None
    try:
        op.get_rna_type()
    except (AttributeError, KeyError):
        return None
    return op


def _import_mesh_file(ext, filepath):
    errors = []
    for op_path in IMPORT_OPERATOR_PATHS.get(ext, ()):
        import_func = _get_bpy_op(op_path)
        if import_func is None:
            continue
        try:
            return import_func(filepath=filepath)
        except Exception as exc:
            errors.append(f"{op_path}: {exc}")
    supported_exts = ", ".join(sorted(IMPORT_OPERATOR_PATHS))
    raise RuntimeError(
        f'No usable Blender import operator found for ".{ext}" file "{filepath}". '
        f"Supported extensions: {supported_exts}. Tried: {errors}"
    )


def load_obj(filepath):
    """
    Auto load mesh file, support .stl, .obj,

    Parameters
    ----------
    filepath : str
        filepath.

    Returns
    -------
    obj

    """
    ext = filepath[filepath.rindex(".") + 1 :].lower()
    _import_mesh_file(ext, filepath)
    assert len(bpy.context.selected_objects) >= 1, f'load "{filepath}" failed!'
    obj = bpy.context.selected_objects[-1]

    if not len(obj.data.materials) and ext == "ply":
        # Guess the model is Vertex Shader
        # And load Vertex Shader manual
        set_vertex_color_material(obj)
    return obj


def is_obj_valid(obj):
    try:
        dir(obj)
        return True
    except ReferenceError:
        return False


class activate_obj(object):
    def __init__(self, obj):
        self.current_obj = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = obj

    def __enter__(self):
        return self

    def __exit__(self, typee, value, traceback):
        if is_obj_valid(self.current_obj):
            bpy.context.view_layer.objects.active = self.current_obj


def remove_obj(obj_or_str):
    if isinstance(obj_or_str, str):
        obj = bpy.data.objects[obj_or_str]
    else:
        obj = obj_or_str
    bpy.data.objects.remove(obj)


class edit_mode:
    def __init__(self, obj=None, mode="EDIT"):
        self.obj = obj
        self.mode = mode

    def __enter__(self):
        if self.obj is None:
            self.obj = bpy.context.object
        self.activate = activate_obj(self.obj)
        self.activate.__enter__()
        self.old_mode = self.obj.mode
        bpy.ops.object.mode_set(mode=self.mode)

    def __exit__(self, typee, value, traceback):
        bpy.ops.object.mode_set(mode=self.old_mode)
        self.activate.__exit__(typee, value, traceback)


def subdivide(obj, number_cuts=2):
    with edit_mode(obj):
        bpy.ops.mesh.subdivide(number_cuts=number_cuts)


def duplicate(obj, copy_data=False, collection=None):
    if collection is None:
        collection = bpy.context.collection
    new_obj = obj.copy()
    if copy_data:
        new_obj.data = obj.data.copy()
    collection.objects.link(new_obj)
    return new_obj


def get_obj_size_info(obj):
    """
    In [0]: tree-size_info
    └── /: dict  4
        ├── box: (8, 3)float64  # bound_box * scale
        ├── size: (3,)float64   # xyz
        ├── circumcircle: 0.866 # radius
        └── scale: (3,)float64

    return dict(box=box, size=size, circumcircle=circumcircle, scale=scale)
    """
    scale = np.array(obj.scale)
    box = np.array([v[:] for v in obj.bound_box]) * scale[None]
    size = box.max(0) - box.min(0)
    circumcircle = np.linalg.norm(box, axis=1).max()
    size_info = dict(box=box, size=size, circumcircle=circumcircle, scale=scale)
    return size_info


if __name__ == "__main__":
    pass
