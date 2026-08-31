from abc import ABC, abstractmethod
from collections.abc import Mapping

from .process import Process


class Registry(Mapping[str, Process], ABC):
    """Registry Base Class to Manage Processes.

    The registry is responsible for the creation, reading, updating
    and deletion (CRUD) of processes that are exposed to clients
    connected to an OGC API - Processes compliant server.

    The registered processes may be ephemeral by being stored in-memory
    only or persistent by means of serialization and de-serialization.
    In case an implementation chooses to store processes persistently,
    it must offer a means to restore previously added processes on
    startup of the OGC API - Processes compliant server.
    """

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
    def create(self, *args, **kwargs) -> Process:
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
    def read(self, id: str, *args, **kwargs) -> Process:
        """Return a single registered process.

        Raises:
            KeyError: The process does not exist in the registry.

        Returns:
            Process: Internal representation of the process.m
        """

    @abstractmethod
    def read_all(self) -> Mapping[str, Process]:
        """Get a dictionary containing all registered processes.

        The dictonary must use process identifiers as presented to
        the user as the keys and a process description as the
        corresponding values.

        Returns:
            Dict[str, Process]: Mapping of process identifier to process description.
        """

    @abstractmethod
    def update(self, id: str, *args, **kwargs) -> Process:
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
    def delete(self, id: str, *args, **kwargs) -> None:
        """Delete a process from the registry.

        Raises:
            KeyError: The process to be deleted does not exist
                in the registry.
        """
