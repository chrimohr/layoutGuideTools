from qgis.PyQt.QtCore import QLocale, QTranslator, QCoreApplication
from qgis.core import QgsSettings, Qgis
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

import os.path

from .guide_templates import (
    install_guide_template_ui,
    remove_guide_template_ui,
    iter_designer_dialogs,
)
from . import guide_templates


class layoutGuides:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        locale = QgsSettings().value('locale/userLocale', QLocale().name())[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            '{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&Layout Guide Tools')
        self.first_start = None
        self._template_error_shown = None

    def tr(self, message):
        return QCoreApplication.translate('layoutGuides', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr(u'Layout Guide Tools'),
            callback=self.run,
            add_to_toolbar=False,
            parent=self.iface.mainWindow())

        try:
            self.iface.layoutDesignerOpened.disconnect(self.on_layout_designer_opened)
        except Exception:
            pass
        self.iface.layoutDesignerOpened.connect(self.on_layout_designer_opened)

        self.install_on_existing_designers()

        self.first_start = True

    def unload(self):
        try:
            self.iface.layoutDesignerOpened.disconnect(self.on_layout_designer_opened)
        except Exception:
            pass

        try:
            main_window = self.iface.mainWindow()
            if main_window is not None:
                for designer in iter_designer_dialogs(main_window):
                    remove_guide_template_ui(designer)
        except Exception:
            pass

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Layout Guide Tools'),
                action)
            self.iface.removeToolBarIcon(action)

    def _report_template_error(self, parent=None):
        try:
            error = guide_templates.TEMPLATE_LOAD_ERROR
        except Exception:
            return
        if not error or error == self._template_error_shown:
            return
        self._template_error_shown = error
        try:
            self.iface.messageBar().pushMessage(
                self.tr(u'Layout Guide Tools'),
                error,
                level=Qgis.MessageLevel.Critical,
                duration=0,
            )
        except Exception:
            pass
        try:
            if parent is None:
                parent = self.iface.mainWindow()
            QMessageBox.critical(
                parent,
                self.tr(u'Layout Guide Tools'),
                error,
            )
        except Exception:
            pass

    def on_layout_designer_opened(self, designer):
        install_guide_template_ui(designer)
        try:
            parent = designer.window()
        except Exception:
            parent = None
        self._report_template_error(parent)

    def install_on_existing_designers(self):
        try:
            main_window = self.iface.mainWindow()
            if main_window is None:
                return
            for designer in iter_designer_dialogs(main_window):
                install_guide_template_ui(designer)
        except Exception:
            pass
        self._report_template_error()

    def run(self):
        self.install_on_existing_designers()

        has_designer = False
        try:
            main_window = self.iface.mainWindow()
            if main_window is not None:
                has_designer = any(
                    True for _ in iter_designer_dialogs(main_window)
                )
        except Exception:
            pass

        if has_designer:
            self.iface.messageBar().pushMessage(
                self.tr(u'Layout Guide Tools'),
                self.tr(u'Guide templates are available in the Layout Designer Guides panel.'),
                level=Qgis.MessageLevel.Info,
                duration=5,
            )
        else:
            try:
                self.iface.messageBar().pushMessage(
                    self.tr(u'Layout Guide Tools'),
                    self.tr(u'Open a print layout, then use the template selector in the Guides panel.'),
                    level=Qgis.MessageLevel.Info,
                    duration=8,
                )
            except Exception:
                pass
            QMessageBox.information(
                self.iface.mainWindow(),
                self.tr(u'Layout Guide Tools'),
                self.tr(
                    u'Open a print layout (Project > New Print Layout).\n'
                    u'The guide template selector appears in the Guides panel.\n'
                    u'Templates can be customized in guide_templates.json inside the plugin folder.'
                ),
            )
