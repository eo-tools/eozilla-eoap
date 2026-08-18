from abc import ABC, abstractmethod

from gavicore.models import ProcessDescription
from pydantic import BaseModel


class Process(ABC):
    @classmethod
    @abstractmethod
    def create(cls, *args, **kwargs) -> "Process":
        """Create a New In-Memory Representation of a Process

        Returns:
            Process: An instance of the implemented process.
        """

    @property
    @abstractmethod
    def model_class(self) -> type[BaseModel]: ...

    @property
    @abstractmethod
    def description(self) -> ProcessDescription: ...
