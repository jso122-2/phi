"""
Symbol extractors — one per language/file-type.

Each extractor accepts a file path and returns a list of SymbolNode objects.
The FilesystemCrawler dispatches to the right extractor based on file suffix.

Public surface:
    from data.extractors import (
        PythonExtractor,
        JSExtractor,
        MarkdownExtractor,
        ConfigExtractor,
    )
"""

from .python_extractor import PythonExtractor
from .js_extractor import JSExtractor
from .markdown_extractor import MarkdownExtractor
from .config_extractor import ConfigExtractor
from .txt_extractor import TxtExtractor

__all__ = [
    "PythonExtractor",
    "JSExtractor",
    "MarkdownExtractor",
    "ConfigExtractor",
    "TxtExtractor",
]
