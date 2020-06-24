"""Offset anim code."""
from maya import cmds


def create_offset_handle():
    """Create visually distinct locator to use as offset handle (pivot).

    Returns:
        str: name of created object.
    """
    offset_handle = next(iter(cmds.spaceLocator(name="Offset_Handle")), None)
    for axis in "XYZ":
        cmds.setAttr(
            "{offset_handle}.localScale{axis}".format(
                offset_handle=offset_handle,
                axis=axis
            ),
            2
        )
    cmds.setAttr(
        "{offset_handle}.overrideEnabled".format(offset_handle=offset_handle),
        True
    )
    cmds.setAttr(
        "{offset_handle}.overrideDisplayType".format(
            offset_handle=offset_handle
        ),
        0
    )
    cmds.setAttr(
        "{offset_handle}.overrideColor".format(
            offset_handle=offset_handle
        ),
        18
    )
    return offset_handle


def create_proxy_setup(pivot_object, objects):
    """Create proxy objects and offset handle.

    Args:
        pivot_object (str): name of object to use as pivot.
        objects (list): list of objects to create proxies for.

    Returns:
        dict: mapping of object to proxy
    """
    offset_handle = create_offset_handle()
    cmds.delete(cmds.parentConstraint(pivot_object, offset_handle, mo=False))
    cmds.makeIdentity(
        offset_handle,
        apply=True,
        translate=True,
        rotate=True,
        scale=True,
        normal=False
    )

    # create proxy objects.
    object_mapping = {}
    for object in objects:
        proxy_object = cmds.polyCylinder()[0]
        object_mapping[object] = proxy_object

        # multiply object worldmatrix with offset_handle world matrix
        # connect as input to proxy object to give an indication of what
        # offsetted objects will look like.
        multiply = cmds.createNode('multMatrix')
        decompose = cmds.createNode('decomposeMatrix')
        cmds.connectAttr(
            '{obj}.worldMatrix[0]'.format(obj=object),
            '{mult}.matrixIn[0]'.format(mult=multiply)
        )
        cmds.connectAttr(
            '{loc}.worldMatrix[0]'.format(loc=offset_handle),
            '{mult}.matrixIn[1]'.format(mult=multiply)
        )
        cmds.connectAttr(
            '{mult}.matrixSum'.format(mult=multiply),
            '{dec}.inputMatrix'.format(dec=decompose)
        )
        cmds.connectAttr(
            '{dec}.outputRotate'.format(dec=decompose),
            '{obj}.rotate'.format(obj=proxy_object)
        )
        cmds.connectAttr(
            '{dec}.outputTranslate'.format(dec=decompose),
            '{obj}.translate'.format(obj=proxy_object)
        )
        cmds.connectAttr(
            '{dec}.outputScale'.format(dec=decompose),
            '{obj}.scale'.format(obj=proxy_object)
        )
    return object_mapping


def get_transform_for_object(object):
    """Query translate and rotate for given object.

    Args:
        dict: rotation and translation data for object.
    """
    data = {}
    data['ro'] = cmds.xform(
        object,
        query=True,
        rotation=True
    )
    data['t'] = cmds.xform(
        object,
        query=True,
        translation=True
    )
    return data


def store_transform_data(objects, object_mapping):
    """Query keyframed transformation data and store.

    Accurately gets values at keyframed times, stores any flipping by
    analyzing the timeline.
    TO DO: currently tangents are not supported yet.

    Args:
        objects (list): list of objects to store data for.
        object_mapping (dict): mapping of objects to proxies.

    Returns:
        tuple: dictionary of data and flip_data
    """
    # bake offsets into keys.
    flip_allowance = 90
    data = {}
    flip_data = {}

    for object in objects:
        data[object] = {}
        flip_data[object] = {}
        keys = set(
            cmds.keyframe(
                object,
                query=True,
                timeChange=True,
                absolute=True
            ) or []
        )
        if not keys:
            # if object has no keyframes store static data.
            data[object]['static'] = get_transform_for_object(
                object_mapping[object]
            )

        prev_key = None
        for key in sorted(list(keys)):
            # store transform for every keyframe
            cmds.currentTime(key)
            data[object][key] = get_transform_for_object(
                object_mapping[object]
            )

            if prev_key:
                flip = 0
                counter = 0
                prev_rot = None
                for frame in range(int(prev_key), int(key)):
                    # analyze frames between current and previous keys
                    # for any flipping rotation channels.
                    cmds.currentTime(frame)
                    cur_rot = cmds.xform(
                        object_mapping[object],
                        query=True,
                        rotation=True
                    )
                    if not prev_rot:
                        prev_rot = cur_rot
                        continue

                    max_difference = 0
                    for i in range(3):
                        difference = abs(cur_rot[i] - prev_rot[i])
                        if difference > max_difference:
                            max_difference = difference

                    if max_difference > flip_allowance:
                        flip += 1

                    if flip > counter:
                        data[object][frame] = get_transform_for_object(
                            object_mapping[object]
                        )

                        cmds.currentTime(frame - 1)
                        data[object][frame - 1] = get_transform_for_object(
                            object_mapping[object]
                        )

                        counter = flip
                        flip_data[object][frame] = True
                        flip_data[object][frame-1] = True
                    prev_rot = cur_rot
            prev_key = key
    return (data, flip_data)


def apply_transformation_data(data):
    """Set translation and rotation for given objects.

    Args:
        dict: stored objects with key rotation and translational data.
    """
    for object in data:
        if data[object].get('static'):
            cmds.xform(object, ro=data[object]['static']['ro'])
            cmds.xform(object, t=data[object]['static']['t'])
        else:
            for key in data[object]:
                cmds.currentTime(key)
                cmds.xform(object, ro=data[object][key]['ro'], ws=True)
                cmds.xform(object, t=data[object][key]['t'], ws=True)
                cmds.setKeyframe(object, at='r')
                cmds.setKeyframe(object, at='t')


def apply_flipped_key_filter(data):
    """Go through data and apply rotational data for flipped channels.

    Args:
        data (dict): stored objects with key rotation and translational data.
    """
    for object in data:
        for axis in 'XYZ':
            prev_key = 0
            count = 0
            velocity = 1
            for frame in sorted(data[object]):
                # loop through keyframes, if difference between two adjacent
                # keys is larger than 180 degrees then apply a 360 offset
                # as the channel was flipped.
                # sidenote: these adjacent keys were created as part of the
                # transformation data storing.
                if prev_key:
                    curr_value = next(
                        iter(
                            cmds.keyframe(
                                object,
                                at='rotate{0}'.format(axis),
                                t=(frame, frame),
                                q=True,
                                vc=True,
                                a=True
                            ) or []),
                        None
                    )
                    if count:
                        cmds.keyframe(
                            object,
                            t=(frame, frame),
                            at='rotate{0}'.format(axis),
                            e=True,
                            vc=curr_value+360*count*velocity,
                            a=True
                        )
                    if frame - prev_key > 1:
                        prev_key = frame
                        continue
                    prev_value = next(
                        iter(
                            cmds.keyframe(
                                object,
                                at='rotate{0}'.format(axis),
                                t=(prev_key, prev_key),
                                q=True,
                                vc=True,
                                a=True
                            ) or []
                        ), None
                    )
                    if curr_value is None or prev_value is None:
                        prev_key = frame
                        continue
                    diff = abs(curr_value - prev_value)
                    if diff >= 180:
                        # apply rotation in direction object was rotating to.
                        if curr_value > prev_value:
                            velocity = -1
                        else:
                            velocity = 1
                        count += 1
                        cmds.keyframe(
                            object,
                            t=(frame, frame),
                            at='rotate{0}'.format(axis),
                            e=True,
                            vc=curr_value+360*count,
                            a=True
                        )
                prev_key = frame


def cleanup_keys_from_data(data):
    """Remove keys listed in given data object.

    Args:
        dict: data object with objects and frames to delete keys from.
    """
    for object in data:
        for frame in data[object]:
            cmds.cutKey(object, t=(frame, frame))
