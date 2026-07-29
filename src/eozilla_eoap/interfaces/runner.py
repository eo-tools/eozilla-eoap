from abc import ABC, abstractmethod
from typing import Dict


class Runner(ABC):
    persistent_output_directory: str
    """Path to location where artifacts
    generated during execution are presistently stored."""

    @abstractmethod
    def run(self, job_id: str, *args, **kwargs) -> Dict:
        """Submit a job to the CWL backend"""

    @abstractmethod
    def cleanup_job(self, job_id: str, *args, **kwargs) -> None:
        # TODO: Is it really the responsibility of the runner to clean up resources?
        #       That shouldn't really be it's concern, no? However, I currently do not
        #       have a better idea on where to place this part. Registry is also not
        #       adequate. The job??!
        """Remove persistent job artifacts

        When the CWL backend/executor/runner allows the stage-out of data, it must(?) also
        implement some form of cleanup to remove those artifacts.

        Args:
            job_id (str): Job whose artifacts are to be removed
        """
