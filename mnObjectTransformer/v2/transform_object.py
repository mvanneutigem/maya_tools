"""Transform dag object functionality."""
import math

from maya.api import OpenMaya
from maya import cmds

from mnObjectTransformer.v2 import utils


def apply_transform_to_static_object(
    object_path,
    transform_matrix,
    pivot_matrix=None,
):
    """Transform object using given transformation matrix,

    Optionally the transformation can be applied from a specific pivot matrix
    otherwise the the transformation will be along world origin.

    Args:
        object_path (str): dagpath of object to transform.
        transform_matrix (OpenMaya.MMatrix): matrix to transform object with.
        pivot_matrix (OpenMaya.MMatrix):
            pivot matrix to apply transformation on.
    """
    if not pivot_matrix:
        pivot_matrix = OpenMaya.MMatrix()

    m_dag_object = utils.get_dag_node(object_path)

    # get world matrix for the given object.
    world_matrix_plug = utils.get_array_plug_from_dag_object(
        m_dag_object,
        "worldMatrix"
    )
    context = OpenMaya.MDGContext()
    world_matrix = utils.get_matrix_from_plug(
        world_matrix_plug,
        context
    )

    # get the new transformation using matrix math.
    new_matrix = utils.get_new_matrix(
        world_matrix,
        transform_matrix,
        pivot_matrix,
    )

    # set the new transformation on the object using its transformation plug.
    plug_node = world_matrix_plug.node()
    transform = OpenMaya.MFnTransform(plug_node)
    transform.setTransformation(new_matrix)


def apply_transform_to_animated_object(
    object_path,
    transform_matrix,
    pivot_matrix=None,
    apply_filter=True
):
    """Transform object using given transformation matrix,

    Optionally the transformation can be applied from a specific pivot matrix
    otherwise the the transformation will be along world origin.

    Args:
        object_path (str): dagpath of object to transform.
        transform_matrix (OpenMaya.MMatrix): matrix to transform object with.
        pivot_matrix (OpenMaya.MMatrix):
            pivot matrix to apply transformation on.
        apply_filter (bool): whether to apply a filter to counter act flipping
            rotation channels after applying the transformation.
    """
    if not pivot_matrix:
        pivot_matrix = OpenMaya.MMatrix()

    m_dag_object = utils.get_dag_node(object_path)
    rotation_order = cmds.xform(object_path, query=True, rotateOrder=True)

    # get the animation curves and their keys for rotation and translation.
    animcurves = {}
    key_inputs = set()
    for attribute in utils.get_transform_attrs():
        animcurves[attribute] = utils.get_animcurve(m_dag_object, attribute)
        for key_index in range(animcurves[attribute].numKeys):
            key_inputs.add(animcurves[attribute].input(key_index).value)

    # get world matrix and parent matrix plugs.
    world_matrix_plug = utils.get_array_plug_from_dag_object(
        m_dag_object,
        "worldMatrix"
    )

    # we will need data for inbetween frames if we're applying a filter.
    if apply_filter:
        frames = range(int(min(key_inputs)), int(max(key_inputs)) + 1)
    else:
        frames = key_inputs

    transformed_data = {}
    for frame in frames:
        # create a context to query at given frame.
        time_context = OpenMaya.MDGContext(OpenMaya.MTime(frame))

        # get the world matrix using time context.
        world_matrix = utils.get_matrix_from_plug(
            world_matrix_plug,
            time_context
        )

        # get the original euler angle values.
        rx_plug = m_dag_object.findPlug('rx', False)
        rx_angle = rx_plug.asMAngle(time_context)
        ry_plug = m_dag_object.findPlug('ry', False)
        ry_angle = ry_plug.asMAngle(time_context)
        rz_plug = m_dag_object.findPlug('rz', False)
        rz_angle = rz_plug.asMAngle(time_context)

        # get the new transformation using matrix math.
        new_matrix = utils.get_new_matrix(
            world_matrix,
            transform_matrix,
            pivot_matrix,
        )

        # append values to account for rotations >360 degrees on each channel.
        new_rotation = new_matrix.rotation()
        new_rotation.x += (rx_angle.asRadians() - rx_angle.asRadians()%(2*math.pi))
        new_rotation.y += (ry_angle.asRadians() - ry_angle.asRadians()%(2*math.pi))
        new_rotation.z += (rz_angle.asRadians() - rz_angle.asRadians()%(2*math.pi))

        # store euler data per frame.
        transformed_data[frame] = {}
        transformed_data[frame]['t'] = new_matrix.translation(
            OpenMaya.MSpace.kTransform
        )
        transformed_data[frame]['r'] = new_matrix.rotation() 
        transformed_data[frame]['r'] = new_rotation

    # apply an euler filter to counter flipping channels.
    if apply_filter:
        utils.apply_euler_filter_to_transformed_data(
            transformed_data, 
            frames,
            rotation_order
        )

    for key in key_inputs:
        # set keyframes on the anim curves.
        trans = transformed_data[key]['t']
        rot = transformed_data[key]['r']
        utils.set_transform_keys_on_curve(
            key,
            [trans.x, trans.y, trans.z, rot.x, rot.y, rot.z],
            animcurves
        )
