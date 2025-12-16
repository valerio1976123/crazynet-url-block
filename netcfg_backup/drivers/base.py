from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Device


class Driver(ABC):
    @abstractmethod
    def fetch_config(self, device: Device) -> tuple[str, str]:
        """
        Returns (config_text, file_extension_without_dot).
        """
        raise NotImplementedError

