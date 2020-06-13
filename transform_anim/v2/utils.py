"""OpenMaya matrix transform utilities."""
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


def get_new_matrix(
    world_matrix,
    transform_matrix,
    pivot_matrix,
    rotation_order
):
    """Apply the transformation matrix to the world matrix using the given
    pivot and rotation order.

    Args:
        world_matrix(OpenMaya.MMatrix): matrix to transform.
        transform_matrix(OpenMaya.MMatrix): the transformation matrix.
        pivot_matrix(OpenMaya.MMatrix): pivot point to transform on.
        rotation_order(OpenMaya.MMatrix): rotation order to apply rotation on
            world matrix with.
    Returns:
        OpenMaya.MTransformationMatrix: transformed world matrix.
    """
    m_transform_matrix = OpenMaya.MTransformationMatrix(transform_matrix)
    m_world_matrix = OpenMaya.MTransformationMatrix(world_matrix)

    # move world matrix into pivot point space.
    local_pivot_point = pivot_matrix * world_matrix.inverse()
    m_world_matrix.setRotatePivot(
        local_pivot_point.translation,
        OpenMaya.MSpace.kTransform,
        True
    )
    m_world_matrix.rotateBy(local_pivot_point.rotation)

    # transform worl matrix using transformation matrix
    m_euler_rotation = m_transform_matrix.rotation()
    m_euler_rotation.order = rotation_order
    m_world_matrix.rotateBy(m_euler_rotation, OpenMaya.MSpace.kTransform)
    m_world_matrix.translateBy(
        m_transform_matrix.translation(OpenMaya.MSpace.kTransform),
        OpenMaya.MSpace.kTransform
    )

    return OpenMaya.MTransformationMatrix(m_world_matrix.asMatrix())
