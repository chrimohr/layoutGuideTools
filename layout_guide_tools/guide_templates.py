from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QWidget,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)
from qgis.core import (
    Qgis,
    QgsLayoutGuide,
    QgsLayoutMeasurement,
    QgsMessageLog,
)

TEMPLATE_WIDGET_OBJECT_NAME = "guideTemplateWidget"

GUIDE_TEMPLATES = {
    "10 mm": {"dynamic": 10},
    "20 mm": {"dynamic": 20},
    "A4 Custom": [("v", 10), ("v", 212), ("v", 212.3), ("v", 287), ("h", 10), ("h", 200.3)],
    "A3 Custom": [("v", 10), ("v", 335), ("v", 335.3), ("v", 410), ("h", 10), ("h", 287)],
}


def _log(level: str, msg: str):
    try:
        QgsMessageLog.logMessage(f"[GUIDE-TOOL] {msg}", "Layout Guide Tools", level=0)
    except Exception:
        pass
    print(f"[GUIDE-TOOL] {level}: {msg}")


def resolve_template_guides(template_name, page):
    if template_name not in GUIDE_TEMPLATES:
        raise KeyError(f"Unknown template: {template_name}")

    template_data = GUIDE_TEMPLATES[template_name]

    if isinstance(template_data, dict) and "dynamic" in template_data:
        margin = float(template_data["dynamic"])
        page_size = page.pageSize()
        width = page_size.width()
        height = page_size.height()
        _log("DEBUG", f"Dynamic calculation ({margin}mm): page {width:.2f}x{height:.2f}mm")
        return [
            ("v", margin),
            ("v", width - margin),
            ("h", margin),
            ("h", height - margin),
        ]
    elif isinstance(template_data, list):
        return list(template_data)
    else:
        raise ValueError(f"Unknown template format for {template_name}")


def add_guide_template(designer, template_name) -> bool:
    try:
        layout = designer.view().currentLayout()
        if layout is None:
            _log("ERROR", "No active layout found.")
            return False

        page_collection = layout.pageCollection()
        if page_collection.pageCount() == 0:
            _log("ERROR", "Layout has no pages.")
            return False

        try:
            current_page_index = designer.view().currentPage()
        except Exception:
            current_page_index = 0

        page = page_collection.page(current_page_index)
        if page is None:
            page = page_collection.page(0)
        if page is None:
            _log("ERROR", "Could not determine a layout page.")
            return False

        final_guides = resolve_template_guides(template_name, page)
        guides = layout.guides()

        layout.undoStack().beginMacro(f"Guide template: {template_name}")
        try:
            for orientation, position in final_guides:
                qt_orientation = Qt.Vertical if orientation == "v" else Qt.Horizontal
                guide = QgsLayoutGuide(
                    qt_orientation,
                    QgsLayoutMeasurement(float(position), Qgis.LayoutUnit.Millimeters),
                    page,
                )
                guides.addGuide(guide)
        finally:
            layout.undoStack().endMacro()

        _log("INFO", f"Template '{template_name}' applied.")
        return True
    except Exception as e:
        _log("EXCEPTION", f"Error applying template: {e}")
        return False


def find_guide_widget(parent) -> QWidget | None:
    for widget in parent.findChildren(QWidget):
        try:
            if widget.metaObject().className() == "QgsLayoutGuideWidget":
                return widget
        except Exception:
            continue
    return None


def install_guide_template_ui(designer) -> bool:
    try:
        window = designer.window()
        guide_widget = find_guide_widget(window)
        if guide_widget is None:
            return False

        if guide_widget.findChild(QWidget, TEMPLATE_WIDGET_OBJECT_NAME):
            return True

        container = QWidget(guide_widget)
        container.setObjectName(TEMPLATE_WIDGET_OBJECT_NAME)
        container.setMaximumHeight(40)

        row = QHBoxLayout(container)
        row.setContentsMargins(5, 0, 5, 0)
        row.setSpacing(5)

        label = QLabel("Template:", container)
        combo = QComboBox(container)
        combo.setObjectName("guideTemplateCombo")
        combo.setMinimumWidth(180)
        combo.addItems(list(GUIDE_TEMPLATES.keys()))

        button = QPushButton("Add", container)
        button.setObjectName("guideTemplateAddButton")
        button.setFixedWidth(80)

        row.addWidget(label)
        row.addWidget(combo, 1)
        row.addWidget(button)

        main_layout = guide_widget.layout()
        if main_layout is not None and hasattr(main_layout, "insertWidget"):
            main_layout.insertWidget(1, container)
        else:
            new_layout = QVBoxLayout(guide_widget)
            guide_widget.setLayout(new_layout)
            new_layout.insertWidget(1, container)

        button.clicked.connect(lambda _checked=False, d=designer, c=combo: add_guide_template(d, c.currentText()))

        _log("INFO", "Template UI installed.")
        return True
    except Exception as e:
        _log("EXCEPTION", f"Error installing UI: {e}")
        return False


def remove_guide_template_ui(designer) -> None:
    try:
        window = designer.window()
        guide_widget = find_guide_widget(window)
        if guide_widget is None:
            return
        container = guide_widget.findChild(QWidget, TEMPLATE_WIDGET_OBJECT_NAME)
        if container is not None:
            parent_layout = guide_widget.layout()
            if parent_layout is not None:
                parent_layout.removeWidget(container)
            container.deleteLater()
    except Exception as e:
        _log("EXCEPTION", f"Error removing UI: {e}")


def iter_designer_dialogs(main_window):
    for widget in main_window.findChildren(QWidget):
        try:
            if widget.metaObject().className() == "QgsLayoutDesignerDialog":
                yield widget
        except Exception:
            continue
