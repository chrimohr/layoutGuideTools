import json
import os

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
TEMPLATES_FILE = os.path.join(os.path.dirname(__file__), "guide_templates.json")

DEFAULT_TEMPLATES = {
    "10mm margin": {"dynamic": 10},
    "20mm margin": {"dynamic": 20},
}

TEMPLATE_LOAD_ERROR = None


def _log_critical(msg):
    try:
        QgsMessageLog.logMessage(msg, "Layout Guide Tools", level=2)
    except Exception:
        pass


def _validate_template(value):
    if isinstance(value, dict) and "dynamic" in value:
        if "horizontal" in value or "vertical" in value:
            return "dynamic must not be combined with horizontal or vertical"
        try:
            float(value["dynamic"])
            return None
        except Exception:
            return "dynamic must be a number"
    if isinstance(value, dict) and ("horizontal" in value or "vertical" in value):
        if "dynamic" in value:
            return "dynamic must not be combined with horizontal or vertical"
        try:
            positions_by_key = {}
            for key in ("horizontal", "vertical"):
                positions = value.get(key, [])
                if positions is None:
                    positions = []
                if not isinstance(positions, list):
                    return f"{key} must be a list"
                positions_by_key[key] = positions
            count = 0
            for positions in positions_by_key.values():
                for pos in positions:
                    float(pos)
                    count += 1
            if count == 0:
                return "horizontal and vertical must contain at least one position"
            return None
        except Exception:
            return "horizontal and vertical must contain numbers"
    if isinstance(value, list):
        try:
            for item in value:
                orientation, position = item
                if orientation not in ("v", "h"):
                    return "unknown orientation, expected v or h"
                float(position)
            return None
        except Exception:
            return "static guides must be pairs of orientation and position"
    return "unknown template format"


def _is_valid_template(value) -> bool:
    return _validate_template(value) is None


def load_templates(path: str = None) -> dict:
    global TEMPLATE_LOAD_ERROR
    TEMPLATE_LOAD_ERROR = None
    file_path = path or TEMPLATES_FILE
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return dict(DEFAULT_TEMPLATES)
    except Exception as e:
        TEMPLATE_LOAD_ERROR = f"Invalid template file {file_path}: {e}. Using defaults."
        _log_critical(TEMPLATE_LOAD_ERROR)
        return dict(DEFAULT_TEMPLATES)
    if not isinstance(data, dict) or not data:
        TEMPLATE_LOAD_ERROR = f"Invalid template file {file_path}: expected a non-empty object. Using defaults."
        _log_critical(TEMPLATE_LOAD_ERROR)
        return dict(DEFAULT_TEMPLATES)
    valid = {}
    problems = []
    for name, value in data.items():
        problem = _validate_template(value)
        if problem is None:
            valid[name] = value
        else:
            problems.append(f"{name}: {problem}")
    if problems:
        TEMPLATE_LOAD_ERROR = f"Invalid templates in {file_path}: " + "; ".join(problems)
        _log_critical(TEMPLATE_LOAD_ERROR)
    if not valid:
        if TEMPLATE_LOAD_ERROR:
            TEMPLATE_LOAD_ERROR += " Using defaults."
        else:
            TEMPLATE_LOAD_ERROR = f"No valid templates in {file_path}. Using defaults."
        _log_critical(TEMPLATE_LOAD_ERROR)
        return dict(DEFAULT_TEMPLATES)
    return valid


def reload_templates(path: str = None) -> dict:
    GUIDE_TEMPLATES.clear()
    GUIDE_TEMPLATES.update(load_templates(path))
    return GUIDE_TEMPLATES


GUIDE_TEMPLATES = load_templates()


def resolve_template_guides(template_name, page):
    if template_name not in GUIDE_TEMPLATES:
        raise KeyError(f"Unknown template: {template_name}")

    template_data = GUIDE_TEMPLATES[template_name]

    if isinstance(template_data, dict) and "dynamic" in template_data and "horizontal" not in template_data and "vertical" not in template_data:
        margin = float(template_data["dynamic"])
        page_size = page.pageSize()
        width = page_size.width()
        height = page_size.height()
        return [
            ("v", margin),
            ("v", width - margin),
            ("h", margin),
            ("h", height - margin),
        ]
    elif isinstance(template_data, dict) and ("horizontal" in template_data or "vertical" in template_data) and "dynamic" not in template_data:
        guides = []
        for pos in template_data.get("vertical", []) or []:
            guides.append(("v", float(pos)))
        for pos in template_data.get("horizontal", []) or []:
            guides.append(("h", float(pos)))
        if not guides:
            raise ValueError(f"Unknown template format for {template_name}")
        return guides
    elif isinstance(template_data, list):
        return [(orientation, float(position)) for orientation, position in template_data]
    else:
        raise ValueError(f"Unknown template format for {template_name}")


def add_guide_template(designer, template_name) -> bool:
    try:
        layout = designer.view().currentLayout()
        if layout is None:
            return False

        page_collection = layout.pageCollection()
        if page_collection.pageCount() == 0:
            return False

        try:
            current_page_index = designer.view().currentPage()
        except Exception:
            current_page_index = 0

        page = page_collection.page(current_page_index)
        if page is None:
            page = page_collection.page(0)
        if page is None:
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

        return True
    except Exception as e:
        _log_critical(f"Error applying template: {e}")
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
        reload_templates()
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

        return True
    except Exception as e:
        _log_critical(f"Error installing UI: {e}")
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
    except Exception:
        pass


def iter_designer_dialogs(main_window):
    for widget in main_window.findChildren(QWidget):
        try:
            if widget.metaObject().className() == "QgsLayoutDesignerDialog":
                yield widget
        except Exception:
            continue
