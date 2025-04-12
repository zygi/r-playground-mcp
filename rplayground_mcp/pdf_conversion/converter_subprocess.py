# import importlib.util
# if importlib.util.find_spec("marker") is None:
#     CONVERTER_AVAILABLE = False
# else:
#     # reexport the PdfConverter class
#     from marker.converters.pdf import PdfConverter
#     CONVERTER_AVAILABLE = True

#     __all__ = ["PdfConverter", "CONVERTER_AVAILABLE"]

import abc
from pathlib import Path
from typing import TypedDict

class ConversionResult(TypedDict):
    text: str
    images: dict[int, str]  # page_idx -> base64 encoded PNG
    
class MarkerConverter(abc.ABC):
    @abc.abstractmethod
    def start(self) -> None: ...

    @abc.abstractmethod
    async def wait_for_startup(self, timeout: float | None = None) -> bool: ...

    @abc.abstractmethod
    async def convert(self, pdf_path: Path, timeout: float = 300.0) -> ConversionResult: ...

    @abc.abstractmethod
    async def async_shutdown(self, timeout: float = 5.0) -> None: ...