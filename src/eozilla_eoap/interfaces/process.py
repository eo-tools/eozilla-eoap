from abc import ABC, abstractclassmethod, abstractmethod


class Process(ABC):
    @abstractclassmethod
    def create(cls, *args, **kwargs) -> "Process":
        """Create a New In-Memory Representation of a Process

        Returns:
            Process: An instance of the implemented process.
        """
