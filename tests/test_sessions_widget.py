import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSIONS_WIDGET_PATH = REPO_ROOT / "src" / "astrofiler" / "ui" / "sessions_widget.py"


def _load_sessions_widget_module(master_manager):
    module_name = "astrofiler.ui.sessions_widget"

    for name in [
        module_name,
        "astrofiler",
        "astrofiler.ui",
        "astrofiler.core",
        "astrofiler.core.utils",
        "astrofiler.core.master_manager",
        "astrofiler.models",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtWidgets",
        "PySide6.QtGui",
    ]:
        sys.modules.pop(name, None)

    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Qt = types.SimpleNamespace(
        transparent=0,
        Antialiasing=0,
        WindowModal=0,
        UserRole=0,
        CustomContextMenu=0,
        QPoint=lambda x, y: (x, y),
    )
    qtcore.QSize = _Dummy
    qtcore.QUrl = _Dummy

    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    for name in [
        "QWidget",
        "QVBoxLayout",
        "QHBoxLayout",
        "QPushButton",
        "QTreeWidget",
        "QTreeWidgetItem",
        "QAbstractItemView",
        "QMenu",
        "QProgressDialog",
        "QApplication",
        "QMessageBox",
        "QFileDialog",
        "QLabel",
        "QProgressBar",
    ]:
        setattr(qtwidgets, name, _Dummy)

    qtgui = types.ModuleType("PySide6.QtGui")
    for name in ["QFont", "QDesktopServices", "QIcon", "QPixmap", "QPainter", "QColor", "QBrush"]:
        setattr(qtgui, name, _Dummy)

    pyside6 = types.ModuleType("PySide6")
    pyside6.QtCore = qtcore
    pyside6.QtWidgets = qtwidgets
    pyside6.QtGui = qtgui

    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = qtcore
    sys.modules["PySide6.QtWidgets"] = qtwidgets
    sys.modules["PySide6.QtGui"] = qtgui

    astrofiler_package = types.ModuleType("astrofiler")
    astrofiler_package.__path__ = [str(SESSIONS_WIDGET_PATH.parents[2])]
    sys.modules["astrofiler"] = astrofiler_package

    ui_package = types.ModuleType("astrofiler.ui")
    ui_package.__path__ = [str(SESSIONS_WIDGET_PATH.parent)]
    sys.modules["astrofiler.ui"] = ui_package

    core_module = types.ModuleType("astrofiler.core")
    core_module.fitsProcessing = object()
    sys.modules["astrofiler.core"] = core_module

    utils_module = types.ModuleType("astrofiler.core.utils")
    utils_module.session_to_calibration_criteria = lambda _session: {"key": "value"}
    sys.modules["astrofiler.core.utils"] = utils_module

    mm_module = types.ModuleType("astrofiler.core.master_manager")
    mm_module.get_master_manager = lambda: master_manager
    sys.modules["astrofiler.core.master_manager"] = mm_module

    models_module = types.ModuleType("astrofiler.models")
    models_module.fitsFile = object()
    models_module.fitsSession = object()
    models_module.Masters = object()
    sys.modules["astrofiler.models"] = models_module

    spec = importlib.util.spec_from_file_location(module_name, SESSIONS_WIDGET_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    sys.modules[module_name] = module
    return module


def test_build_resources_status_flatdark_uses_master_manager_without_name_error():
    class _MasterManager:
        def __init__(self):
            self.calls = 0

        def find_matching_master(self, session_data, cal_type):
            self.calls += 1
            assert session_data == {"key": "value"}
            assert cal_type == "flatdark"
            return None

    master_manager = _MasterManager()
    module = _load_sessions_widget_module(master_manager)

    widget = module.SessionsWidget.__new__(module.SessionsWidget)
    widget._master_types_by_source_session_id = {}
    widget._matched_master_types_by_session_id = {}

    session = types.SimpleNamespace(
        fitsSessionObjectName="FlatDark",
        fitsSessionId="session-1",
    )

    result = widget._build_resources_status(session)

    assert result == {"text": "", "tooltip": "", "percentage": 0}
    assert master_manager.calls == 1
