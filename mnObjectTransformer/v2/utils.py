"""OpenMaya matrix transform utilities."""
import math
from maya.api import OpenMaya, OpenMayaAnim


def get_transform_attrs():
    """Cycles over rotate and transform xyz channels and returns attributes.

    Returns:
        list: rotate and translate xyz short attribute names.
    """
    return ['{0}{1}'.format(attr, axis) for attr in 'tr' for axis in 'xyz']


def get_array_plug_from_dag_object(m_dag_object, attribute):
    """Get the array plug for the given attribute from the dag object.

    Args:
        m_dag_object (OpenMaya.MFnDagNode): dag node to get plug from.
        attribute (str): name of the attribute to get plug from.

    Returns:
        OpenMaya.MPlug: array plug object for the attribute.
    """
    plug_array = m_dag_object.findPlug(attribute, False)
    if not plug_array.isArray:
        return None
    plug_array.evaluateNumElements()
    return plug_array.elementByPhysicalIndex(0)


def get_matrix_from_plug(plug, context):
    """Get the matrix from the plug using the given context.

    Args:
        plug (OpenMaya.MPlug): plug to get matrix from.
        context (OpenMaya.MDGContext): context for mobject to query.

    Returns:
        OpenMaya.MMatrix: matrix object from the plug.
    """
    matrix_object = plug.asMObject(context)
    fn_matrix_data = OpenMaya.MFnMatrixData(matrix_object)
    matrix = fn_matrix_data.matrix()
    return matrix


def set_transform_keys_on_curve(input, transform, anim_curves):
    """Set keyframes on the given animcurves using the input as time.

    Args:
        input (int): frame to set keyframes on.
        transform (list): transformation values in tr xyz order.
        anim_curves (dict): the curves to set the keys on.
    """
    for attribute, value in zip(get_transform_attrs(), transform):
        anim_curves[attribute].addKey(OpenMaya.MTime(input), value)


def get_dag_node(object_path):
    """Get maya dependency node for given object path.

    Args:
        object_path (str): path of object in maya scene.
    Returns:
        OpenMaya.MFnDagNode: dagnode object from given path.
    """
    selection_list = OpenMaya.MSelectionList()
    selection_list.add(object_path)
    m_object = selection_list.getDependNode(0)
    return OpenMaya.MFnDagNode(m_object)


def get_animcurve(m_dag_node, attribute):
    """Get MFnAnimCurve for given object and attribute.

    Args:
        m_dag_node (OpenMaya.MFnDagNode): maya object to get curve from.
        attribute (str): name of attribute to get curve from.

    Returns:
        OpenMayaAnim.MFnAnimCurve:
            the animation curve for given object, attribute.
    """
    m_plug = m_dag_node.findPlug(attribute, False)
    m_source = m_plug.source()
    if m_source.isNull:
        return

    m_source_node = m_source.node()
    if not m_source_node.apiTypeStr.startswith('kAnimCurve'):
        return

    fn_curve = OpenMayaAnim.MFnAnimCurve(m_source_node)
    return fn_curve


def get_additive_rotation(
    parent_matrix,
    transform_matrix,
    pivot_matrix,
):
    """Apply the transformation matrix to the world matrix using the given
    pivot and rotation order.

    Args:
        world_matrix(OpenMaya.MMatrix): matrix to transform.
        transform_matrix(OpenMaya.MMatrix): the transformation matrix.
        pivot_matrix(OpenMaya.MMatrix): pivot point to transform on.
    Returns:
        OpenMaya.MTransformationMatrix: transformed world matrix.
    """
    print 'transform matrix rot', OpenMaya.MTransformationMatrix(transform_matrix).rotation()
    space_matrix = transform_matrix * pivot_matrix
    print 'space matrix', OpenMaya.MTransformationMatrix(space_matrix).rotation()
    local_matrix = space_matrix * parent_matrix
    print 'local matrix', OpenMaya.MTransformationMatrix(local_matrix).rotation()
    rotation = OpenMaya.MTransformationMatrix(local_matrix).rotation()
    print 'rot values', rotation
    return rotation
    #just add this to the original values?

def get_new_matrix(
    world_matrix,
    transform_matrix,
    pivot_matrix,
):
    """Apply the transformation matrix to the world matrix using the given
    pivot and rotation order.

    Args:
        world_matrix(OpenMaya.MMatrix): matrix to transform.
        transform_matrix(OpenMaya.MMatrix): the transformation matrix.
        pivot_matrix(OpenMaya.MMatrix): pivot point to transform on.
    Returns:
        OpenMaya.MTransformationMatrix: transformed world matrix.
    """
    pivot_world_matrix = world_matrix * pivot_matrix.inverse()
    transformed_pivot_world_matrix = pivot_world_matrix * transform_matrix
    transformed_world_matrix = transformed_pivot_world_matrix * pivot_matrix  # noqa
    return OpenMaya.MTransformationMatrix(transformed_world_matrix)

def naive_flip_diff(a1, a2):
    #if difference between values is large than 180 degrees
    # add 360 degrees in the direction of the rotation
    while abs(a1 - a2) > math.pi:
        if a1 < a2:
            a2 -= 2 * math.pi
        else:
            a2 += 2 * math.pi

    return a2

def flip_euler(euler, rotation_order):
    # resolve cases where middle rotations are offloaded to outer rotations.
    result = OpenMaya.MEulerRotation()
    inner_axis = rotation_order[0]
    middle_axis = rotation_order[1]
    outer_axis = rotation_order[2]
    
    inner_value = getattr(euler, inner_axis) + math.pi
    setattr(result, inner_axis, inner_value)

    outer_value = getattr(euler, outer_axis) + math.pi
    setattr(result, outer_axis, outer_value)

    middle_value = getattr(euler, middle_axis) * -1 + math.pi
    setattr(result, middle_axis, middle_value)

    return result

def euler_distance(e1, e2):
    return abs(e1.x - e2.x) + abs(e1.y - e2.y) + abs(e1.z - e2.z)

def apply_euler_filter_to_transformed_data(
    transformed_data,
    frames,
    rotation_order='xyz'
):
    """"""
    euler_data = {}
    for frame in frames:
        print frame
        if (frame-1) not in transformed_data:
            'first one'
            continue
        print 'current', transformed_data[frame]
        print 'previous', transformed_data[frame - 1]
        current_rotation = transformed_data[frame]['r']
        previous_rotation = transformed_data[frame-1]['r']

        new_rotation = OpenMaya.MEulerRotation()
        new_rotation.x = naive_flip_diff(previous_rotation.x, current_rotation.x)
        new_rotation.y = naive_flip_diff(previous_rotation.y, current_rotation.y)
        new_rotation.z = naive_flip_diff(previous_rotation.z, current_rotation.z)

        result_rotation = flip_euler(new_rotation, rotation_order)
        result_rotation.x = naive_flip_diff(previous_rotation.x, result_rotation.x)
        result_rotation.y = naive_flip_diff(previous_rotation.y, result_rotation.y)
        result_rotation.z = naive_flip_diff(previous_rotation.z, result_rotation.z)

        new_rotation_distance = euler_distance(previous_rotation, new_rotation)
        result_rotation_distance = euler_distance(previous_rotation, result_rotation)
        
        if result_rotation_distance < new_rotation_distance:
            new_rotation = result_rotation

        transformed_data[frame]['r'] = new_rotation