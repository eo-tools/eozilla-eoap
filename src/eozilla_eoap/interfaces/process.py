from abc import ABC, abstractmethod

from gavicore.models import ProcessDescription
from pydantic import BaseModel


class Process(ABC):
    """Process Base Class.

    The Process base class describes the interfaces that must be
    implemented by Process implementations. It is constrained to
    a minimal subset of interfaces and properties to, theoretically,
    allow vastly different processes to implement this base class.
    """
    
    @classmethod
    @abstractmethod
    def create(cls, *args, **kwargs) -> "Process":
        """Create a New In-Memory Representation of a Process.

        Returns:
            Process: An instance of the implemented process.
        """

    @property
    @abstractmethod
    def model_class(self) -> type[BaseModel]:
        """Process-Implementation Agnostic Input Description.

        Returns:
            type[BaseModel]: Pydantic Input Model of a Process
        """

    @property
    @abstractmethod
    def description(self) -> ProcessDescription:
        """Describe a Process in OGC-Compliant Manner.

        Returns:
            ProcessDescription: A ProcessDescription model instance.
        """
