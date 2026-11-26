from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FilePath,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)
from typing_extensions import Self


class RuntimeContextConfiguration(BaseModel):
    """Set a restricted set of runtime options for `cwltool`"""

    model_config = ConfigDict(serialize_by_alias=True)

    ### Container runtime parameters
    user_space_docker_command: FilePath | None = Field(
        None,
        description="Path to udocker, if user space Docker engine should be used.",
        serialization_alias="user_space_docker_cmd",
    )

    force_docker_pull: bool = Field(False, description="Always pull Docker image.")

    rm_container: bool = Field(
        True, description="Remove container after job step finished."
    )

    singularity: bool = Field(False, description="Use Singularity.")

    podman: bool = Field(False, description="Use Podman.")

    ### Output checksum computation
    compute_checksum: bool = Field(
        True, description="Compute checksum of output files."
    )

    ### Verbosity
    debug: bool = Field(False, description="Log on debug level.")

    @model_serializer(mode="wrap")
    def serialize_model(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict:
        data = handler(self)

        for key in ("user_space_docker_command", "user_space_docker_cmd"):
            if key in data and data[key] is not None:
                data[key] = str(data[key])

        return data

    @model_validator(mode="after")
    def check_exclusive_container_runtime(self) -> Self:
        if self.singularity and self.podman:
            raise ValueError(
                "Can't specify singularity and podman runtimes simultaneously."
            )
        return self
