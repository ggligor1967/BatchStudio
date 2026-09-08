"""Optional native file drag-and-drop bootstrap state."""

from dataclasses import dataclass
from importlib import metadata

try:
    from tkinterdnd2 import COPY, DND_FILES, REFUSE_DROP, TkinterDnD
except ModuleNotFoundError as error:
    if error.name != "tkinterdnd2":
        raise
    COPY = "copy"
    DND_FILES = "DND_Files"
    REFUSE_DROP = "refuse_drop"
    TkinterDnD = None


@dataclass
class NativeDndStatus:
    """Record each independently verified layer of optional DnD support."""

    python_package_importable: bool
    python_package_version: str | None = None
    tkdnd_loaded: bool = False
    tkdnd_version: str | None = None
    targets_registered: bool = False
    error: str | None = None


def _installed_tkinterdnd2_version():
    if TkinterDnD is None:
        return None
    try:
        return metadata.version("tkinterdnd2")
    except metadata.PackageNotFoundError:
        return None


def uninitialized_native_dnd_status():
    """Describe import availability without claiming Tcl or target readiness."""
    return NativeDndStatus(
        python_package_importable=TkinterDnD is not None,
        python_package_version=_installed_tkinterdnd2_version(),
    )


def enable_native_file_drop(root, dnd_module=None):
    """Load tkdnd into an existing Tk interpreter without creating another root."""
    module = TkinterDnD if dnd_module is None else dnd_module
    status = uninitialized_native_dnd_status()
    status.python_package_importable = module is not None
    if module is None:
        return status

    try:
        require = getattr(module, "require", None) or getattr(module, "_require")
        require(root)
        provided_version = root.tk.call("package", "provide", "tkdnd")
        if not provided_version:
            raise RuntimeError("tkdnd did not report a loaded package version")
    except Exception as error:
        status.error = f"{type(error).__name__}: {error}"
        return status

    status.tkdnd_loaded = True
    status.tkdnd_version = str(provided_version)
    return status
