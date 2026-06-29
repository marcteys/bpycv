#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: DIYer22@github
@mail: ylxx@live.com
Created on Sat Dec 28 21:33:28 2019
"""

import tempfile
from collections import OrderedDict

import bpy
from boxx import *
from boxx import imread, os, withattr

from .exr_image_parser import ImageWithAnnotation, parser_exr
from .material_utils import set_inst_material
from .pose_utils import get_6d_pose
from .statu_recover import StatuRecover, undo
from .camera_utils import get_cam


def _set_attr_if_exists(recover, obj, attr, value):
    if hasattr(obj, attr):
        recover.set_attr(obj, attr, value)
        return True
    return False


def _set_enum_if_supported(recover, obj, attr, value):
    if not hasattr(obj, attr):
        return False
    try:
        enum_items = obj.bl_rna.properties[attr].enum_items
        enum_values = {item.identifier for item in enum_items}
    except (AttributeError, KeyError):
        enum_values = {value}
    if value not in enum_values:
        return False
    recover.set_attr(obj, attr, value)
    return True


def set_cycles_compute_device_type(compute_device_type="CUDA"):
    bpy.context.scene.cycles.device = "GPU"
    bpy.context.preferences.addons[
        "cycles"
    ].preferences.compute_device_type = compute_device_type
    bpy.context.preferences.addons["cycles"].preferences.get_devices()
    print(
        "compute_device_type =",
        bpy.context.preferences.addons["cycles"].preferences.compute_device_type,
    )
    for d in bpy.context.preferences.addons["cycles"].preferences.devices:
        d["use"] = True
        print(d["name"], d["use"])


class set_annotation_render(StatuRecover):
    def __init__(self):
        StatuRecover.__init__(self)
        # TODO detect whether in ssh X11 forward
        # if sysi.gui:  # mean "does the enviroment support GUI".
        # self.set_attr(render, "engine", "BLENDER_EEVEE")
        scene = bpy.context.scene
        render = scene.render
        if render.engine == "BLENDER_WORKBENCH":
            self.set_attr(render, "engine", "CYCLES")
        if render.engine in ["BLENDER_EEVEE"]:
            # When enviroment not support GUI, Eevee will raise Exception("Unable to open a display")  (@Blender 2.81)
            self.set_attr(render, "engine", "BLENDER_EEVEE")
            eevee = getattr(scene, "eevee", None)
            if eevee is not None:
                _set_attr_if_exists(self, eevee, "taa_render_samples", 1)
                _set_attr_if_exists(self, eevee, "use_bloom", False)
        elif render.engine == "BLENDER_EEVEE_NEXT":
            self.set_attr(render, "engine", "BLENDER_EEVEE_NEXT")
            eevee = getattr(scene, "eevee", None)
            if eevee is not None:
                _set_attr_if_exists(self, eevee, "taa_render_samples", 1)
        elif render.engine == "CYCLES":
            self.set_attr(render, "engine", "CYCLES")
            self.set_attr(scene.cycles, "samples", 1)
            # Set fewer samples for faster testing
            if hasattr(scene.cycles, "preview_samples"):
                self.set_attr(scene.cycles, "preview_samples", 1)
            if hasattr(bpy.context.view_layer, "cycles"):
                _set_attr_if_exists(
                    self, bpy.context.view_layer.cycles, "use_denoising", False
                )
        self.set_attr(render, "film_transparent", True)
        self.set_attr(scene.render, "use_motion_blur", False)

        # not support for blender3, TODO del
        # self.set_attr(scene.render, "tile_x", 256)
        # self.set_attr(scene.render, "tile_y", 256)

        image_settings = render.image_settings
        _set_enum_if_supported(self, image_settings, "media_type", "MULTI_LAYER_IMAGE")
        _set_attr_if_exists(self, image_settings, "use_exr_interleave", True)
        attrs = dict(
            file_format="OPEN_EXR_MULTILAYER",
            compression=0,
            color_mode="RGBA",
            color_depth="32",
            exr_codec="NONE",
        )
        self.set_attrs(render.image_settings, attrs)
        self.set_attrs(bpy.context.view_layer, dict(use_pass_z=True))


class set_image_render(StatuRecover):
    def __init__(self):
        StatuRecover.__init__(self)
        scene = bpy.context.scene
        render = scene.render
        _set_enum_if_supported(self, render.image_settings, "media_type", "IMAGE")
        attrs = dict(file_format="PNG", compression=15)
        self.set_attrs(render.image_settings, attrs)


def render_image(cam=None):
    cam = get_cam(cam)
    scene = bpy.context.scene
    render = scene.render
    png_path = tempfile.NamedTemporaryFile().name + ".png"
    with set_image_render(), withattr(scene, "camera", cam), withattr(
        render, "filepath", png_path
    ):
        print("Render image using:", render.engine)
        bpy.ops.render.render(write_still=True)
    image = imread(png_path)[..., :3]
    os.remove(png_path)
    return image


_render_image = render_image
befor_render_data_hooks = OrderedDict()

# @undo()
def render_data(render_image=True, render_annotation=True):
    scene = bpy.context.scene
    render = scene.render
    for hook_name, hook in befor_render_data_hooks.items():
        print(f"Run befor_render_data_hooks[{hook_name}]")
        hook()
    befor_render_data_hooks.clear()

    path = tempfile.NamedTemporaryFile().name
    render_result = {}
    if render_image:
        render_result["image"] = _render_image()
    if render_annotation:
        exr_path = path + ".exr"
        with set_inst_material(), set_annotation_render(), withattr(
            render, "filepath", exr_path
        ):
            print("Render annotation using:", render.engine)
            bpy.ops.render.render(write_still=True)
            render_result["exr"] = parser_exr(exr_path)
            os.remove(exr_path)
    result = ImageWithAnnotation(**render_result)
    if "render_6d_pose" and render_annotation:
        objs = [obj for obj in bpy.data.objects if "inst_id" in obj]
        ycb_6d_pose = get_6d_pose(objs, inst=result["inst"])
        result["ycb_6d_pose"] = ycb_6d_pose
    return result


if __name__ == "__main__":
    pass
