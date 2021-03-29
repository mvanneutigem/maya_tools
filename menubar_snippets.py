from maya import cmds
from maya.api import OpenMayaUI

global scriptjob_id = cmds.scriptJob(event=['modelEditorChanged'], add_to_menu_snippet)

def add_to_menu_snippet():
	model_panels = cmds.getPanel(type='modelPanel')
	TAG_NAME = '_viewport_button'
	for panel in model_panels:
		bar_layout = cmds.modelPanel(panel, query=True, barLayout=True)
		if not bar_layout:
			continue
		menu_layout = cmds.layout(bar_layout, query=True, childArray=True)[0]
		# example for icontextcheckbox
		tagged_items = [
			child for child in cmds.layout(layout, query=True, childArray=True)
			if cmds.objectTypeUI(child) == 'iconTextCheckBox'
			and cmds.iconTextCheckBox(child, query=True, label=True) == TAG_NAME
		]
		if not tagged_items:
			cmds.iconTextCheckBox(
				image=icon_path,
				style='iconOnly',
				annotation='Toggle ' + name.capitalize(),
				label=TAG_NAME
				width=18,
				height=18,
				onCommand=on_command, # some function
				offCommand=off_command, # some function
				parent=menu_layout,
			)
		OpenMayaUI.M3dView.getM3dViewFromModelPanel(menu_layout).refresh(force=True)
