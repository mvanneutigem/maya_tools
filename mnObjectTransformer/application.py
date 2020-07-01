"""Transformation tool.

Copyright (C) 2020  Marieke van Neutigem

# TO DO:
# - improve + stabilize flipping filter
# - add support for tangents

Contact: mvn882@hotmail.com
https://mariekevanneutigem.nl/blog


To add this tool to your shelf;
- copy below code into a python tab in the script editor.
- Replace [CODEPATH] with the path to the transform anim folder.
- Highlight the code and drag it onto the shelf where you want to add it.
-------------------------------------------------------------------------
import sys
sys.path.append( [CODEPATH] )
from mnObjectTransformer import application
dialog = application.TransformDialog()
dialog.show()
-------------------------------------------------------------------------
"""

# transform addition rotation to the local space and just add.

from contextlib import contextmanager
import functools
import logging
import math

from PySide2 import QtCore, QtWidgets
from maya import cmds
from maya.api import OpenMaya

from mnObjectTransformer.v1 import offset_anim
from mnObjectTransformer.v2 import transform_object

LOGGER = logging.getLogger(__name__)


class TransformDialog(QtWidgets.QDialog):
    """Dialog for testing logic for transforming objects in space.

    Args:
        parent (QWidget): Parent object of this window.
    """
    def __init__(self, parent=None):
        super(TransformDialog, self).__init__(parent)
        self.setWindowFlags(
            self.windowFlags() & ~ QtCore.Qt.WindowContextHelpButtonHint
        )
        self.setGeometry(0, 0, 300, 100)
        self.setWindowTitle('Transform objects')

        main_layout = QtWidgets.QGridLayout()

        tab_widget = QtWidgets.QTabWidget()
        tab_widget.addTab(Version1Tab(), u"V1")
        tab_widget.addTab(Version2Tab(), u"V2")
        tab_widget.setCurrentIndex(1)

        main_layout.addWidget(tab_widget)
        self.setLayout(main_layout)
        self.center()
        self.read_settings()
        
    def center(self):
        """Center this window on active screen."""
        frame_geometry = self.frameGeometry()
        available_geometry = QtWidgets.QDesktopWidget().availableGeometry()
        center_point = available_geometry.center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())
        
    def closeEvent(self, event):
        """Override close event to store geometry/state settings.
        
        Args:
            event (QEvent): event references passed by close emitter.
        """
        self.settings.setValue('geometry', self.saveGeometry())
        super(TransformDialog, self).closeEvent(event)

    def read_settings(self):
        """Read settings to restore geometry/state of window."""
        self.settings = QtCore.QSettings('mvn', 'transformer')
        geometry = self.settings.value('geometry', '')
        if geometry:
            self.restoreGeometry(geometry)


class Version1Tab(QtWidgets.QWidget):
    """Tab for transforming objects in space.

    Args:
        parent (QWidget): Parent object of this widget.
    """
    def __init__(self, parent=None):
        super(Version1Tab, self).__init__(parent)
        self.object_mapping = None
        self.objects = None
        
        main_layout = QtWidgets.QGridLayout()
        main_layout.setAlignment(QtCore.Qt.AlignTop)

        description_label = QtWidgets.QLabel(
            'Select objects to transform, then object to use as pivot.'
        )
        main_layout.addWidget(description_label)

        create_proxy_button = QtWidgets.QPushButton("Create proxy setup.")
        create_proxy_button.clicked.connect(self.create_proxy_setup)
        main_layout.addWidget(create_proxy_button)

        self.apply_filter_checkbox = QtWidgets.QCheckBox(
            "Apply flipping filter."
        )
        main_layout.addWidget(self.apply_filter_checkbox)

        transform_button = QtWidgets.QPushButton("Apply transformation.")
        transform_button.clicked.connect(self.mnObjectTransformers)
        main_layout.addWidget(transform_button)

        self.setLayout(main_layout)
    
    def create_proxy_setup(self):
        """Create proxy setup for creating offsets."""
        selection = cmds.ls(selection=True)
        if len(selection) < 2:
            LOGGER.warn("Select objects to offset and pivot")
            return
        pivot_object = selection[-1]
        self.objects = selection[:-1]
        self.object_mapping = offset_anim.create_proxy_setup(
            pivot_object, 
            self.objects
        )
        
    def mnObjectTransformers(self):
        """Transform objects as specified by proxy setup."""
        if not self.objects or not self.object_mapping:
            LOGGER.warn("Create proxy setup first")
            return
        apply_filter = self.apply_filter_checkbox.isChecked()
        data, flip_data = offset_anim.store_transform_data(
            self.objects, 
            self.object_mapping
        )
        offset_anim.apply_transformation_data(data)
        if apply_filter:
            offset_anim.apply_flipped_key_filter(data)
        offset_anim.cleanup_keys_from_data(flip_data)
            
    
class Version2Tab(QtWidgets.QWidget):
    """Tab for transforming objects in space.

    Args:
        parent (QWidget): Parent object of this widget.
    """
    def __init__(self, parent=None):
        super(Version2Tab, self).__init__(parent)

        main_layout = QtWidgets.QGridLayout()

        transform_label = QtWidgets.QLabel('Transformation')
        main_layout.addWidget(transform_label)

        self.transform_value_widget = TransformWidget()
        main_layout.addWidget(self.transform_value_widget, 1, 0, 1, 2)
        
        pivot_label = QtWidgets.QLabel('Pivot')
        main_layout.addWidget(pivot_label, 2, 0)

        self.pivot_value_widget = TransformWidget()
        main_layout.addWidget(self.pivot_value_widget, 3, 0, 1, 2)

        transform_from_obj_button = QtWidgets.QPushButton(
            "Get from selected"
        )
        transform_from_obj_button.clicked.connect(
            functools.partial(
                self.set_transform_widget_from_selected,
                self.transform_value_widget
            )
        )
        main_layout.addWidget(transform_from_obj_button, 0, 1)
        
        pivot_from_obj_button = QtWidgets.QPushButton(
            "Get from selected"
        )
        pivot_from_obj_button.clicked.connect(
            functools.partial(
                self.set_transform_widget_from_selected,
                self.pivot_value_widget
            )
        )
        main_layout.addWidget(pivot_from_obj_button, 2, 1)
        
        self.apply_filter_checkbox = QtWidgets.QCheckBox(
            "Apply flipping filter (experimental)"
        )
        main_layout.addWidget(self.apply_filter_checkbox, 4, 0, 1, 2)
        self.apply_filter_checkbox.setChecked(True)

        apply_transform_button = QtWidgets.QPushButton("Transform selected")
        apply_transform_button.clicked.connect(
            self.apply_transform_to_selected
        )
        main_layout.addWidget(apply_transform_button, 5, 0, 1, 2)

        self.setLayout(main_layout)
        
    def get_matrix_from_widget(self, widget):
        """Create a matrix from the values of the given transform widget.
        
        Returns:
            OpenMaya.MMatrix: matrix for GUI values.
        """
        transform_matrix = OpenMaya.MTransformationMatrix()
        rotation = [
            math.radians(widget.spinboxes['r'][axis].value()) 
            for axis in 'xyz'
        ]
        translation = [widget.spinboxes['t'][axis].value() for axis in 'xyz']
        rotation.append(1)
        transform_matrix.rotateByComponents(
            rotation, 
            OpenMaya.MSpace.kTransform
        )
        
        transform_matrix.setTranslation(
            OpenMaya.MVector(translation), 
            OpenMaya.MSpace.kTransform
        )
        return transform_matrix.asMatrix()
        
    def apply_transform_to_selected(self):
        """Apply transform from gui to selected objects."""
        selection = cmds.ls(selection=True)
        if len(selection) < 1:
            LOGGER.warn("Select at least one (1) object.")
            return

        apply_filter = self.apply_filter_checkbox.isChecked()

        for obj in selection:
            keys = cmds.keyframe(
                obj,
                attribute="translate",
                timeChange=True,
                query=True
            ) or []
            keys.extend(
                cmds.keyframe(
                    obj,
                    attribute="rotate",
                    timeChange=True,
                    query=True
                ) or []
            )

            transform_matrix = self.get_matrix_from_widget(
                self.transform_value_widget
            )
            pivot_matrix = self.get_matrix_from_widget(
                self.pivot_value_widget
            )
            if keys:
                transform_object.apply_transform_to_animated_object(
                    obj,
                    transform_matrix,
                    pivot_matrix,
                    apply_filter
                )
            else:
                transform_object.apply_transform_to_static_object(
                    obj,
                    transform_matrix,
                    pivot_matrix
                )

    def get_transform_from_selected(self):
        """Get transform from selected object."""
        selection = cmds.ls(selection=True)
        if len(selection) != 1:
            LOGGER.warn("Select one (1) object.")
            return
        obj = next(iter(selection), None)
        rotation = cmds.xform(obj, rotation=True, query=True)
        translation = cmds.xform(obj, translation=True, query=True)
        return rotation, translation

    def set_transform_widget_from_selected(self, widget):
        """Set gui widget values to transform of selected object."""
        rotation, translation = self.get_transform_from_selected()
        for i, axis in enumerate('xyz'):
            widget.spinboxes['t'][axis].setValue(
                translation[i]
            )
        for i, axis in enumerate('xyz'):
            widget.spinboxes['r'][axis].setValue(
                rotation[i]
            )


class TransformWidget(QtWidgets.QWidget):
    """Widget for transform values.

    Args:
        parent (QWidget): Parent object of this widget.
    """
    def __init__(self, parent=None):
        super(TransformWidget, self).__init__(parent)

        main_layout = QtWidgets.QGridLayout()

        self.spinboxes = {}
        for i, attr in enumerate('tr'):
            self.spinboxes[attr] = {}
            for j, axis in enumerate('xyz'):
                label = QtWidgets.QLabel(attr + axis)
                main_layout.addWidget(label, i, j*2)
                self.spinboxes[attr][axis] = QtWidgets.QDoubleSpinBox()
                self.spinboxes[attr][axis].setMaximum(1e5)
                self.spinboxes[attr][axis].setMinimum(-1e5)
                self.spinboxes[attr][axis].setValue(0)
                self.spinboxes[attr][axis].setDecimals(4)
                self.spinboxes[attr][axis].setButtonSymbols(
                    QtWidgets.QAbstractSpinBox.NoButtons
                )
                main_layout.addWidget(self.spinboxes[attr][axis], i, j*2+1)

        self.setLayout(main_layout)
