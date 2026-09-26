import json
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QApplication,
    QWidget,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
)
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsLayoutGuide,
    QgsLayoutMeasurement,
    QgsMessageLog,
)

try:
    from qgis.gui import QgsCollapsibleGroupBoxBasic
except Exception:
    QgsCollapsibleGroupBoxBasic = None

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
    except (RuntimeError, AttributeError, TypeError):
        return None


def _validate_template(value):
    if isinstance(value, dict) and "dynamic" in value:
        if "horizontal" in value or "vertical" in value:
            return "dynamic must not be combined with horizontal or vertical"
        try:
            float(value["dynamic"])
            return None
        except (ValueError, TypeError):
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
        except (ValueError, TypeError):
            return "horizontal and vertical must contain numbers"
    if isinstance(value, list):
        try:
            for item in value:
                orientation, position = item
                if orientation not in ("v", "h"):
                    return "unknown orientation, expected v or h"
                float(position)
            return None
        except (ValueError, TypeError):
            return "static guides must be pairs of orientation and position"
    return "unknown template format"


def _is_valid_template(value) -> bool:
    return _validate_template(value) is None


def _resolve_user_path():
    try:
        base = QgsApplication.qgisSettingsDirPath()
    except (RuntimeError, AttributeError, TypeError):
        return None
    if not base:
        return None
    return os.path.join(base, "layout_guide_tools", "guide_templates.json")


def _seed_user_templates(user_path):
    try:
        if os.path.exists(user_path):
            return True
        os.makedirs(os.path.dirname(user_path), exist_ok=True)
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as src:
                shipped = src.read()
            json.loads(shipped)
        except (OSError, ValueError):
            shipped = json.dumps(DEFAULT_TEMPLATES, indent=2)
        with open(user_path, "w", encoding="utf-8") as dst:
            dst.write(shipped)
        return True
    except (OSError, ValueError) as e:
        _log_critical(f"Could not create user template file {user_path}: {e}")
        return False


def _read_template_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not data:
        raise ValueError("expected a non-empty object")
    valid = {}
    problems = []
    for name, value in data.items():
        problem = _validate_template(value)
        if problem is None:
            valid[name] = value
        else:
            problems.append(f"{name}: {problem}")
    return valid, problems


def load_templates(path: str = None) -> dict:
    global TEMPLATE_LOAD_ERROR
    TEMPLATE_LOAD_ERROR = None
    if path:
        candidates = [path]
    else:
        user_path = _resolve_user_path()
        if user_path is not None:
            _seed_user_templates(user_path)
            candidates = [user_path, TEMPLATES_FILE]
        else:
            candidates = [TEMPLATES_FILE]
    for file_path in candidates:
        try:
            valid, problems = _read_template_file(file_path)
        except FileNotFoundError:
            valid = None
        except (OSError, ValueError) as e:
            TEMPLATE_LOAD_ERROR = f"Invalid template file {file_path}: {e}. Using defaults."
            _log_critical(TEMPLATE_LOAD_ERROR)
            valid = None
        if valid is None:
            continue
        if problems:
            TEMPLATE_LOAD_ERROR = f"Invalid templates in {file_path}: " + "; ".join(problems)
            _log_critical(TEMPLATE_LOAD_ERROR)
        if valid:
            return valid
    if TEMPLATE_LOAD_ERROR:
        TEMPLATE_LOAD_ERROR += " Using defaults."
    else:
        TEMPLATE_LOAD_ERROR = "No valid templates found. Using defaults."
    _log_critical(TEMPLATE_LOAD_ERROR)
    return dict(DEFAULT_TEMPLATES)


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
        except (RuntimeError, AttributeError, TypeError):
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
    except (RuntimeError, AttributeError, TypeError, ValueError, KeyError) as e:
        _log_critical(f"Error applying template: {e}")
        return False


def _widget_class_name(widget):
    try:
        return widget.metaObject().className()
    except (RuntimeError, AttributeError):
        return ""


def find_guide_widget(parent) -> QWidget | None:
    if parent is None:
        return None
    for widget in parent.findChildren(QWidget):
        if _widget_class_name(widget) == "QgsLayoutGuideWidget":
            return widget
    return None


def _insert_at_row(content_layout, container, target_row) -> bool:
    try:
        get_pos = getattr(content_layout, "getItemPosition", None)
        take = getattr(content_layout, "takeAt", None)
        if get_pos is None or take is None:
            return False
        count = content_layout.count()
        if count <= 0:
            return False
        entries = []
        for i in range(count):
            item = content_layout.itemAt(i)
            row, column, row_span, column_span = get_pos(i)
            entries.append((item, row, column, row_span, column_span))
        for _ in range(count):
            take(0)
        for item, row, column, row_span, column_span in entries:
            shifted = row + 1 if row >= target_row else row
            widget = item.widget()
            try:
                sub = item.layout()
            except (RuntimeError, AttributeError, TypeError):
                sub = None
            if widget is not None:
                content_layout.addWidget(widget, shifted, column, row_span, column_span)
            elif sub is not None:
                content_layout.addLayout(sub, shifted, column, row_span, column_span)
            else:
                try:
                    content_layout.addItem(item, shifted, column, row_span, column_span)
                except (RuntimeError, AttributeError, TypeError) as e:
                    _log_critical(f"Error restoring layout item: {e}")
        try:
            span = content_layout.columnCount()
        except (RuntimeError, AttributeError, TypeError):
            span = 1
        if not isinstance(span, int) or span < 1:
            span = 1
        content_layout.addWidget(container, target_row, 0, 1, span)
        return True
    except (RuntimeError, AttributeError, TypeError):
        return False


def _place_in_native_container(guide_widget, container) -> bool:
    try:
        scroll_area = None
        for child in guide_widget.findChildren(QWidget):
            if _widget_class_name(child) == "QgsScrollArea":
                scroll_area = child
                break
        if scroll_area is None:
            return False
        content = scroll_area.widget()
        if content is None:
            return False
        content_layout = content.layout()
        if content_layout is None:
            return False
        if _insert_at_row(content_layout, container, 1):
            return True
        add = getattr(content_layout, "addWidget", None)
        if add is None:
            return False
        try:
            add(container)
        except (RuntimeError, AttributeError, TypeError):
            return False
        return True
    except (RuntimeError, AttributeError, TypeError):
        return False


def install_guide_template_ui(designer) -> bool:
    try:
        reload_templates()
        window = designer.window()
        guide_widget = find_guide_widget(window)
        if guide_widget is None:
            return False

        if guide_widget.findChild(QWidget, TEMPLATE_WIDGET_OBJECT_NAME):
            return True

        if QgsCollapsibleGroupBoxBasic is not None:
            container = QgsCollapsibleGroupBoxBasic(guide_widget)
            container.setTitle("Guide Templates")
        else:
            container = QWidget(guide_widget)
        container.setObjectName(TEMPLATE_WIDGET_OBJECT_NAME)

        row = QHBoxLayout(container)

        combo = QComboBox(container)
        combo.setObjectName("guideTemplateCombo")
        combo.addItems(list(GUIDE_TEMPLATES.keys()))
        user_path = _resolve_user_path()
        if user_path is not None:
            combo.setToolTip(f"Templates can be customized in {user_path}.")
        else:
            combo.setToolTip("Templates can be customized in guide_templates.json.")

        button = QPushButton("Add", container)
        button.setObjectName("guideTemplateAddButton")

        row.addWidget(combo, 1)
        row.addWidget(button)

        if not _place_in_native_container(guide_widget, container):
            main_layout = guide_widget.layout()
            if main_layout is not None and hasattr(main_layout, "insertWidget"):
                main_layout.insertWidget(1, container)
            else:
                new_layout = QVBoxLayout(guide_widget)
                guide_widget.setLayout(new_layout)
                new_layout.insertWidget(1, container)

        button.clicked.connect(lambda _checked=False, d=designer, c=combo: add_guide_template(d, c.currentText()))

        return True
    except (RuntimeError, AttributeError, TypeError, ValueError, KeyError) as e:
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
            try:
                owner = container.parentWidget()
                owner_layout = owner.layout() if owner is not None else None
            except (RuntimeError, AttributeError, TypeError):
                owner_layout = None
            if owner_layout is not None:
                try:
                    owner_layout.removeWidget(container)
                except (RuntimeError, AttributeError, TypeError) as e:
                    _log_critical(f"Error detaching guide template UI: {e}")
            container.deleteLater()
    except (RuntimeError, AttributeError, TypeError) as e:
        _log_critical(f"Error removing guide template UI: {e}")
        return None


def _top_level_roots(main_window):
    try:
        app = QApplication.instance()
        roots = list(app.topLevelWidgets()) if app is not None else []
    except (RuntimeError, AttributeError, TypeError):
        roots = []
    if main_window is not None:
        if all(root is not main_window for root in roots):
            roots.append(main_window)
    return roots


def _child_widgets(root):
    try:
        return root.findChildren(QWidget)
    except (RuntimeError, AttributeError, TypeError):
        return []


def iter_designer_dialogs(main_window):
    seen = set()
    for root in _top_level_roots(main_window):
        if root is None:
            continue
        if _widget_class_name(root) == "QgsLayoutDesignerDialog":
            ident = id(root)
            if ident not in seen:
                seen.add(ident)
                yield root
        for widget in _child_widgets(root):
            if _widget_class_name(widget) == "QgsLayoutDesignerDialog":
                ident = id(widget)
                if ident not in seen:
                    seen.add(ident)
                    yield widget
