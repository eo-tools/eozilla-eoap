!!! warning "Job Dismissal is Synchronous"

    The service allows cancellation of processes before they finish via the dismiss endpoint. The only point where an application unaware of such context-clues can be interrupted is before a new job step. Long running steps may delay the dismissal of running process indefinitively. In combination with the circumstance that cancelled processes are awaited for, the user may experience severe delays after requesting cancellation of a process.

The service sub-module provides the actual DRU implementation as well as means to validate incoming Earth Observation Application Packages.

To start a local service instance, activate the Pixi environment and run `wraptile run -- eozilla_eoap.main:service`. The command line interface of `wraptile` is documented [here](https://eo-tools.github.io/eozilla/wraptile/).