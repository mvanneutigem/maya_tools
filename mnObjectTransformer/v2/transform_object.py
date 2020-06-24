"""Transform dag object functionality."""
import math

from maya.api import OpenMaya

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

    # get world matrix and parent matrix plugs.
    world_matrix_plug = utils.get_array_plug_from_dag_object(
        m_dag_object,
        "worldMatrix"
    )

    context = OpenMaya.MDGContext()
    world_matrix = utils.get_matrix_from_plug(
        world_matrix_plug,
        context
    )
    new_matrix = utils.get_new_matrix(
        world_matrix,
        transform_matrix,
        pivot_matrix,
    )

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

    # grab the world matrix for each found input on any channel.
    # do this for every frame instead of just the keys if we want to apply the
    # rotation filter
    if apply_filter:
        frames = range(int(min(key_inputs)), int(max(key_inputs)) + 1)
    else:
        frames = key_inputs

    transformed_matrices = {}
    for frame in frames:
        time_context = OpenMaya.MDGContext(OpenMaya.MTime(frame))

        world_matrix = utils.get_matrix_from_plug(
            world_matrix_plug,
            time_context
        )

        new_matrix = utils.get_new_matrix(
            world_matrix,
            transform_matrix,
            pivot_matrix,
        )
        transformed_matrices[frame] = new_matrix

    filtered_data = {}
    if apply_filter:
        counter = [0, 0, 0]
        offset_rotation = None
        for frame in transformed_matrices:
            if not frame - 1 in transformed_matrices:
                continue

            previous_matrix = transformed_matrices[frame - 1]
            current_matrix = transformed_matrices[frame]

            prev_rot = previous_matrix.rotation()
            current_rot = current_matrix.rotation()

            difference_rot = current_rot - prev_rot
            # full rotation transfer to single different axis
            if abs(difference_rot.x) > math.pi:
                counter[0] += 2

            if abs(difference_rot.y) > math.pi:
                counter[1] += 2

            if abs(difference_rot.z) > math.pi:
                counter[2] += 2

            # dual rotation transfer to single different axis
            if abs(difference_rot.x) == math.pi:
                if abs(difference_rot.y) == math.pi:
                    counter[2] += 2
                if abs(difference_rot.z) == math.pi:
                    counter[1] += 2
            if abs(difference_rot.y) == math.pi:
                if abs(difference_rot.z) == math.pi:
                    counter[0] += 2

            if frame in key_inputs:
                print frame
                # direction of rotation
                direction_x = direction_y = direction_z = 1
                if difference_rot.x < 0:
                    direction_x *= -1
                if difference_rot.y < 0:
                    direction_y *= -1
                if difference_rot.z < 0:
                    direction_z *= -1
                # store the data
                rot = transformed_matrices[frame].rotation()
                print 'rot', rot
                print 'counter', counter
                added_rotation = OpenMaya.MEulerRotation(
                    counter[0] * math.pi * direction_x,
                    counter[1] * math.pi * direction_y,
                    counter[2] * math.pi * direction_z
                )

                if offset_rotation:
                    print 'offset rot', offset_rotation
                    rot += offset_rotation

                filtered_data[frame] = rot + added_rotation
                print 'final rot', rot + added_rotation

                if not offset_rotation:
                    offset_rotation = added_rotation
                else:
                    offset_rotation += added_rotation
                counter = [0, 0, 0]

    for key in key_inputs:
        # set keyframes on the anim curves.
        trans = transformed_matrices[key].translation(
            OpenMaya.MSpace.kTransform
        )

        if key in filtered_data:
            rot = filtered_data[key]
        else:
            rot = transformed_matrices[key].rotation()

        utils.set_transform_keys_on_curve(
            key,
            [trans.x, trans.y, trans.z, rot.x, rot.y, rot.z],
            animcurves
        )
