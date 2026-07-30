from abc import ABC, abstractmethod


class RegistryBackend(ABC):
    @abstractmethod
    def connect(): ...
