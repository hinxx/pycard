"""pycard smart-card wallet application."""

from importlib.metadata import PackageNotFoundError, version


def get_version() -> str:
    try:
        return version("pycard")
    except PackageNotFoundError:
        return "0.1.6-dev"


__version__ = get_version()
