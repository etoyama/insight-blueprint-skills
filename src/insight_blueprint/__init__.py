"""insight-blueprint: embedded validation library + lineage for the skills plugin."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("insight-blueprint-lineage")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
