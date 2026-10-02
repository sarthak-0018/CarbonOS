from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


@dataclass(frozen=True)
class ProfileFact:
    key: str
    value: Any
    source: str
    confidence: float | None
    added_on: date
    confirmed: bool = False


class MemoryService(Protocol):
    """Profile memory boundary; implementations persist and return user-visible facts."""

    def list_facts(self, user_id: str) -> list[ProfileFact]: ...

    def propose_fact(self, user_id: str, fact: ProfileFact) -> str: ...
