import importlib.util
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
TELESCOPE_PATH = REPO_ROOT / "src" / "astrofiler" / "services" / "telescope.py"


def load_telescope_module():
    module_name = "astrofiler.services.telescope"

    for name in [
        module_name,
        "astrofiler.services",
        "astrofiler.models",
        "astrofiler.core",
        "astrofiler.core.utils",
        "numpy",
        "astropy",
        "astropy.io",
        "astropy.io.fits",
    ]:
        sys.modules.pop(name, None)

    sys.modules.setdefault("numpy", types.ModuleType("numpy"))

    astropy_module = types.ModuleType("astropy")
    astropy_io_module = types.ModuleType("astropy.io")
    astropy_fits_module = types.ModuleType("astropy.io.fits")
    astropy_io_module.fits = astropy_fits_module
    astropy_module.io = astropy_io_module
    sys.modules["astropy"] = astropy_module
    sys.modules["astropy.io"] = astropy_io_module
    sys.modules["astropy.io.fits"] = astropy_fits_module

    models_module = types.ModuleType("astrofiler.models")
    models_module.fitsSession = object()
    models_module.fitsFile = object()
    sys.modules["astrofiler.models"] = models_module

    core_module = types.ModuleType("astrofiler.core")
    core_module.get_master_calibration_path = lambda *args, **kwargs: ""
    sys.modules["astrofiler.core"] = core_module

    utils_module = types.ModuleType("astrofiler.core.utils")
    utils_module.fits_image_data = lambda *args, **kwargs: None
    sys.modules["astrofiler.core.utils"] = utils_module

    services_package = types.ModuleType("astrofiler.services")
    services_package.__path__ = [str(TELESCOPE_PATH.parent)]
    sys.modules["astrofiler.services"] = services_package

    spec = importlib.util.spec_from_file_location(module_name, TELESCOPE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    sys.modules[module_name] = module
    return module


def test_celestron_origin_defaults_use_anonymous_ftp():
    module = load_telescope_module()

    config = module.SmartTelescopeManager().supported_telescopes["Celestron Origin"]

    assert config["default_hostname"] == "192.168.1.208"
    assert config["default_username"] is None
    assert config["default_password"] is None
    assert config["protocol"] == "ftp"
    assert config["fits_path"] == "RawData"


def test_is_target_device_accepts_celestron_mdns_variants():
    module = load_telescope_module()
    manager = module.SmartTelescopeManager()

    assert manager.is_target_device("origin.local", "Celestron Origin") is True
    assert manager.is_target_device("Celestron-Origin", "Celestron Origin") is True
    assert manager.is_target_device("Celestron-Origin.local", "Celestron Origin") is True
    assert manager.is_target_device("origin-telescope.local", "Celestron Origin") is True
    assert manager.is_target_device("celestronnexstar.local", "Celestron Origin") is False
    assert manager.is_target_device("original.local", "Celestron Origin") is False
    assert manager.is_target_device("astrofiler.local", "Celestron Origin") is False


def test_find_telescope_uses_ftp_for_origin_without_smb(monkeypatch):
    module = load_telescope_module()
    module.SMB_AVAILABLE = False
    manager = module.SmartTelescopeManager()

    def fail_if_smb_checked(_ip):
        pytest.fail("SMB should not be checked")

    monkeypatch.setattr(module.socket, "gethostbyname", lambda host: "192.168.1.208")
    monkeypatch.setattr(manager, "check_ftp_port", lambda ip: True)
    monkeypatch.setattr(manager, "check_smb_port", fail_if_smb_checked)

    ip, error = manager.find_telescope("Celestron Origin", hostname="origin.local")

    assert (ip, error) == ("192.168.1.208", None)


def test_find_telescope_accepts_origin_ip_hostname(monkeypatch):
    module = load_telescope_module()
    module.SMB_AVAILABLE = False
    manager = module.SmartTelescopeManager()

    monkeypatch.setattr(module.socket, "gethostbyname", lambda host: host)
    monkeypatch.setattr(manager, "check_ftp_port", lambda ip: True)

    ip, error = manager.find_telescope("Celestron Origin", hostname="192.168.1.208")

    assert (ip, error) == ("192.168.1.208", None)


def test_find_telescope_blocks_smb_device_when_smb_unavailable():
    module = load_telescope_module()
    module.SMB_AVAILABLE = False
    manager = module.SmartTelescopeManager()

    ip, error = manager.find_telescope("SeeStar", hostname="seestar.local")

    assert ip is None
    assert error == "SMB protocol not available. Install pysmb package."
