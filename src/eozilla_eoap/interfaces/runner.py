from abc import ABC, abstractmethod
from typing import Dict


class Runner(ABC):
    @abstractmethod
    def run(self, job_id: str, *args, **kwargs) -> Dict:
        """Submit a job to the CWL backend"""
