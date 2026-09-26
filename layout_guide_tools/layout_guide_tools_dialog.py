import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(
        os.path.dirname(__file__),
        'layout_guide_tools_dialog_base.ui'),
    from_imports=True,
    import_from='layout_guide_tools')


class layoutGuidesDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(layoutGuidesDialog, self).__init__(parent)
        self.setupUi(self)
