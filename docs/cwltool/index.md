[`cwltool`](https://cwltool.readthedocs.io/en/latest/) is the reference implementation of the [Common Workflow Language](https://www.commonwl.org/) and is one of the core dependencies of the this project. It's used for

1. validating user-submitted EAOPs encoded in self-contained CWL documents and
1. steering the execution of the derived OGC Processes on the same machine that hosts the server.

For a cleaner integration of the functionality supplied by the `cwltool`, especially with regards to retainment of logs, data stage-in/stage-out and workflow cancellation, certain classes and methods had to be adapted accordingly. Simoultaniously, the `cwltool` module within this project serves as an implementation of the [`Runner`][eozilla_eoap.interfaces.Runner] base class.