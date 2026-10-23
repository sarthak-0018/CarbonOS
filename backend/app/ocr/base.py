from dataclasses import dataclass
from typing import Protocol


@dataclass
class OCRLine:
    text: str
    confidence: float | None
    box: list


class OCRProvider(Protocol):
    @property
    def version(self) -> str: ...

    def recognize(self, image_path: str) -> list[OCRLine]: ...
