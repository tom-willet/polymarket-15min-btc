from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyDecision:
    action: str
    confidence: float
    reason: str


class Strategy(ABC):
    name: str

    @abstractmethod
    def evaluate(self, state: dict) -> StrategyDecision | None:
        raise NotImplementedError
