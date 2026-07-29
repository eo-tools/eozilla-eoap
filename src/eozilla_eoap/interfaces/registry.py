from abc import ABC, abstractmethod
from typing import Any, Dict


class Registry(ABC):
    @abstractmethod
    def configure(self, *args, **kwargs) -> None:
        """Configure and setup a registry.

        This method should be implemented in a way that allows
        for calling it multiple times on the same method without
        overwriting the existing configuration. I.e., it must test
        whether the registry was already initialized and if so,
        leave it unchanged.

        Raises:
            RuntimeError: Configuration of the registry failed.
                Implementations may choose to ignore possible
                failures and fail catastrophically.
        """

    @abstractmethod
    def insert(self, *args, **kwargs) -> Any:
        """Add a new process to the registry.

        Raises:
            RuntimeError: The process to be created does
                already exist and is immutable.
            KeyError: The process to be created does
                alreay exist in the registry.

        Returns:
            Any: Internal representation of a the newly
              created process.
        """

    @abstractmethod
    def update(self, *args, **kwargs) -> Any:
        """Replace a process in the registry.

        Raises:
            KeyError: The process to be replaced does not exist
                in the registry. Implementations may choose to
                ignore this case and quitely insert a new process
                and never raise this error.

        Returns:
            Any: Internal representation of a the newly
                created process.
        """

    @abstractmethod
    def delete(self, *args, **kwargs) -> None:
        """Delete a process from the registry.

        Raises:
            KeyError: The process to be deleted does not exist
                in the registry.
        """

    @abstractmethod
    def get_all(self, *args, **kwargs) -> Dict[str, Any]:
        """Get a dictionary containing all registered processes.

        The dictonary must use process identifiers as presented to
        the user as the keys and a process description as the
        corresponding values.

        Returns:
            Dict[str, Any]: Mapping of process identifier to process description.
        """
