This page outlines planned future additions and changes to `eozilla-eoap`.

### General Project Improvements

Next to the *content-related* plans layed out below, there exist more general changes to the project/repository structure that should be addressed:

- Enable Github pages online documentation
- Adopt templates for bug reports, feature requests and pull requests from the core Eozilla repository
- Adopt change log, i.e. a `CHANGES.md` file to track development progress
- Adopt versioning scheme and subsequently enable package building and publishing on PyPi and Conda
- Possibly add Github Actions workflows for CI and CD

### Harmonization with the core Eozilla Repository

During development it became clear that some core classes have incompatible method signatures, store arguments in representations not applicable to this project or are missing/have a surplus of methods. This resulted in some code *duplication* between the [core Eozilla](https://github.com/eo-tools/eozilla) project and the EOAP extension: 

- The `Job` class accepts an additional artifact manager, responsible for for stage-in and stage-out among other things; at the same time, argument extraction and execution assuming Python functions was removed; the diff between both implementations is small but key places such as the object's constructor and the `create` method were adapted. Additionally, a so-called *runner* is expected as an argument who is responsible for the actual job execution. The interface only offers a single method (`run`) and was introduced to hide implementation specific configurations.
- The `EoapProcess` class is responsible for the conversion from CWL to OGC and/or pydantic data classes in this repository and from Python's function signatures to OGC and/or pydantic data classes in the core repository. As such, the respective modules vastly differ; importantly though, the actual *process* classes do not have many ...
- The `Registry` class here is only responsible for CRUD operations and self-configuration and adapts generic naming for its operations, e.g. `read` instead of `get_workflow` or `read_all` instead of `workflows`. In contrast, core Eozilla's `ProcessRegistry` class is intended to be used to chain Python functions in order to build up a DAG.
- Note that the `ArtifactManager` is not comparable to the `artifacts.py` module; they seem to serve different purposes.
- Since the service implementation is already based on the abstract base classes `ServiceBase` and `DruService`, no further work should be necessary.

In hope of easing the consolidation between this repository and the core Eozilla project, some **interfaces have been drafted and used as the basis for the concrete class implementations**; they can be found in the [interfaces](../src/eozilla_eoap/interfaces/) sub-module. Close examination of them is a mandatory step before they can be pulled into the main project.

### Straighten Shortcuts Out

In its current state, the EOAP extension of Eozilla is not meant to be run in a production environment. Thus, little work was put into **configuring CWL's runtime behavior** and exposing the configuration to whoever manages the service implementation; the latter currently requires direct manipulation of the `CwlToolRunner` class. Building on cwltool's Python API does not allow the user to swap out the the CWL implementation via a simple option, this would require additional implementations of the `Runner` interface instead and may be outside the scope of this project. Some runtime could be opened to the user such as:

- Setting a maximum level of parallelism for a given process execution
- Setting cwltool's verbosity level, even though the respective logs are not accessible by the client
- Configuration of the container image runtime, e.g. whether Docker, Singularity or Podman is used
- Enabling/Disabling checksum calculation of output files

**Input data management** both for *simple* remote files and STAC objects is rather rudimentary: Single files are can only be accessed through the FTP or HTTP protocol while EO input referenced by an URI must be accessible on the local file system or via HTTP (a limitation of the underlying pystac library). Passing STAC entities inline is not implemented; while the OGC Best Practice document seems to indicate that this is allowed, public EOAP examples specify arguments using URLs. Enabling the artifact manager to support both might prove helpful nonetheless.

Regarding **publication of process execution results**, the most important assumption is, that the client, the service and the persistent output location are all located on the same machine; the direct impact is that returned URIs do not contain a host fragment. In a production environment, this assumption does not hold anymore and files referenced in both the `JobResults` and possibly returned STAC Catalogs should be accessible via the internet. How this could be achieved has not been decided: The artifact manager could hand off managing these artifacts completely to a (web) server and rewrite URLs where necessary; alternatively, the artifact manager could hold on to the references of the published files to delete them on dismissal of job results which suggests the service must have write access to wherever results are uploaded/placed (preferred solution); lastly, a web server could be pointed to the artifact directory and the artifact manager rewrites the URLs which would require very little code changes and is similar to the previous suggestion, differing only in how close data stage out and access to these data are coupled. These developments may also make a separation between the input and output data manager necessary; this would also be closer to how the OGC describes the data flow management.

While not strictly related to the data management, the conversion from CWL to OGC schemas of `Directory` arguments for both process inputs and outputs is not final. They depend on the design decision, **how STAC entities are accepted/published**, i.e. are inline STAC definitions allowed or not. Currently, only references to STAC Items/ItemCollections/Catalogs (input) or STAC Catalogs (output) are used. Re-evaluating this decision, making sure to cross-check with OGC's Best Practice document, OGC's API specifications and already existing implementations, is necessary as well as making sure the correct schema definitions, i.e. pydantic data models, are used.

`File` outputs never have their content type set, even when the user specifies it using the `format` field of the `CommandLineTool` block that produced said output. Specifying the format in the workflow output, which is the only part parsed according to the best practice document, does not suffice to pass on the MIME type as cwltool passes on the value set at the *data root*. The user either needs to fill the `format` field in the CLI tool block or its value needs to be taken from the process description, assuming the correct value is specified (if at all).

User interactions with the service that trigger **process registry operations neither follow ACID semantics nor any form of access management**. Thus, race conditions can influence CRUD operations when multiple users are connected to same service instance and users have write access to all deployed process definitions. Using existing database implementations in the process registry and integrating user access management capabilities are planned additions.

### Closing Conformance Gaps

The OGC API - Processes - Part 1: Core specification lists various client-server interactions regarding process execution mode, output transmission modes and response type. Not all possible modes must be supported but the service should advertise its capabilities correctly and format outputs according to the design decisions made (see table 12 in above-mentioned specification); whether the **service communicates the design decisions** accordingly must be re-checked. Additionally, the client is allowed to **request a subset of output parameters**; Eozilla's EOAP extension disregards these requests and always returns all outputs. Filtering the `JobResults` after a process execution should be implemented. Forwarding the selection to cwltool is probably not possible, thus the artifact manager possibly needs extension to remove unwanted results after successful process execution.

Furthermore, the **service does not report its correct capabilities**. The corresponding OGC requirements (stemming from all OGC documents) must be checked and the list of conformance classes updated accordingly.

The OGC API - Processes - Part 2: Deploy, Replace, Undeploy draft specification describes three encodings for dynamic processes: OGC Application Package (similar to CWL documents, but already following OGC Processes's schemas), Docker-encapsulated process descriptions and the CWL encoding. **Supporting OGC Application Packages and Docker fragments is outside the scope of this extension.** The EOAP extension mandates so-called "packed CWL" documents, i.e. the entire workflow definition is self-contained and does not reference external files. The draft specification describes the service to also accept remote CWL files pointed to by an URL, inline JSON and multi-part HTTP requests to send multi-file process definitions. All of them generally seem like worthwhile additions; supporting them would not weaken the requirement that inputs must be packed CWL documents.

The OGC Best Practice Document for EOAPs states a number of requirements directed at the application and application package that were deemed to not be statically testable upon deployment. **Re-evaluating the selection of ignored requirements** could improve the user experience, given that additional checks are implemented; searching for (very) recent community projects that try to solve similar problems may prove helpful.
