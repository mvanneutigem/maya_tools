
loc = 'locator1'

objects = cmds.ls(sl=True)

rot_offset = [0,90,0]
trans_offset = [50,30,10]

#freeze the transforms on the locator in the position you want to use as pivot before starting.
cmds.makeIdentity(loc, apply=True, t=1, r=1, s=1, n=0)

#create relations.
object_mapping = {}
for object in objects:
    dummy_object = cmds.polyCube()[0]
    object_mapping[object] = dummy_object
    multiply = cmds.createNode('multMatrix')
    decompose = cmds.createNode('decomposeMatrix')
    cmds.connectAttr('{obj}.worldMatrix[0]'.format(obj=object), '{mult}.matrixIn[0]'.format(mult=multiply))
    cmds.connectAttr('{loc}.worldMatrix[0]'.format(loc=loc), '{mult}.matrixIn[1]'.format(mult=multiply))
    cmds.connectAttr('{mult}.matrixSum'.format(mult=multiply), '{dec}.inputMatrix'.format(dec=decompose))
    cmds.connectAttr('{dec}.outputRotate'.format(dec=decompose), '{obj}.rotate'.format(obj=dummy_object))
    cmds.connectAttr('{dec}.outputTranslate'.format(dec=decompose), '{obj}.translate'.format(obj=dummy_object))
    cmds.connectAttr('{dec}.outputScale'.format(dec=decompose), '{obj}.scale'.format(obj=dummy_object))
    
#move locator to desired new position.
cmds.xform(loc, ro=rot_offset, t=trans_offset)

#bake offsets into keys.
flip_allowance = 90

data = {}
flip_data = {}

for object in objects:
    data[object] = {}
    flip_data[object] = {}
    keys = set(cmds.keyframe(object, q=True, tc=True, a=True) or [])
    if not keys:
        data[object]['static'] = {}
        data[object]['static']['ro'] = cmds.xform(object_mapping[object], q=True, ws=True, ro=True)
        data[object]['static']['t'] = cmds.xform(object_mapping[object], q=True, ws=True, t=True)
    prev_key = None
    for key in sorted(list(keys)):
        cmds.currentTime(key)
        data[object][key] = {}
        data[object][key]['t'] = cmds.xform(object_mapping[object], q=True, ws=True, t=True)
        data[object][key]['ro'] = cmds.xform(object_mapping[object], q=True, ws=True, ro=True)
        
        # fix for flipping rotation as a result of quaternion to euler transformation
        # needs more research; doesnt seem to work well for fast spinning objects with little keys.
        # this is not necessary if we bake the curves after offsetting.
        if prev_key:
            flip = 0
            counter = 0
            prev_rot=None
            for frame in range(int(prev_key), int(key)):
                cmds.currentTime(frame)
                cur_rot = cmds.xform(object_mapping[object], q=True, ro=True)
                if not prev_rot:
                    prev_rot = cur_rot
                    continue
                
                dif_x = abs(cur_rot[0] - prev_rot[0])
                dif_y = abs(cur_rot[1] - prev_rot[1])
                dif_z = abs(cur_rot[2] - prev_rot[2])
                
                if dif_x > flip_allowance or dif_y > flip_allowance or dif_z > flip_allowance:
                    flip += 1

                prev_rot = cur_rot
            
                if flip > counter:
                    data[object][frame] = {}
                    data[object][frame]['t'] = cmds.xform(object_mapping[object], q=True, ws=True, t=True)
                    data[object][frame]['ro'] = cmds.xform(object_mapping[object], q=True, ws=True, ro=True)
                    
                    cmds.currentTime(frame - 1)
                    data[object][frame-1] = {}
                    data[object][frame-1]['t'] = cmds.xform(object_mapping[object], q=True, ws=True, t=True)
                    data[object][frame-1]['ro'] = cmds.xform(object_mapping[object], q=True, ws=True, ro=True)
                    counter = flip
                    flip_data[object][frame] = True
                    flip_data[object][frame-1] = True
        prev_key = key
        
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
    
#run euler filter and remove the extra keyframes
curves = cmds.listConnections(objects, type='animCurve')
cmds.filterCurve( curves )
for object in flip_data:
    for frame in flip_data[object]:
        cmds.cutKey(object, t=(frame,frame))
