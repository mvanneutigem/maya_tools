"""Gui application to transform objects."""
from maya import cmds
from maya.api import OpenMaya

from transform_anim.v1 import offset_anim
from transform_anim.v2 import transform_object
# TO DO:
# - fix bug for incorrect transformation
# - add support for tangents
# - add option to add flipping keys instead of running filter.
# - code structure
# - gui

# v1
objects = cmds.ls(sl=True)
pivot_object = cmds.ls(sl=True)
object_mapping = offset_anim.create_proxy_setup(pivot_object, objects)
data, flip_data = offset_anim.store_transform_data(objects, object_mapping)
offset_anim.apply_transformation_data(data)
offset_anim.apply_flipped_key_filter(data)
offset_anim.cleanup_keys_from_data(flip_data)

# v2
transform_matrix_values = cmds.getAttr('locator1.matrix')
transform_object.apply_transform_to_animated_object(
    'pCylinder2',
    OpenMaya.MMatrix(transform_matrix_values)
)
transform_object.apply_transform_to_static_object(
    'pCylinder2',
    OpenMaya.MMatrix(transform_matrix_values)
)