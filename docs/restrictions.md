## Deploy, Replace, Undeploy Conformance Gaps

The draft specification for deployment, replacement and undeployment of application packages is not implemented in its entirety. The follwoing requirements and permissions are not implemented:

- Permission `per/ogcapppkg/other-execution-units` which states that other encodings than those defined in the draft specification can be accepted by a server.
- Requirement `req/ogcapppkg/body` which states that for deploy and replace operations, the supported encoding must be `application/ogcappkg+json`. This is the case only when the requirement class "OGC Application Package" is implemented as the single requirement/conformance class.
- All requirements that allow direct deployment of docker images are neglected (`req/docker/*`).
- Deployment and replacement of CWL-based processes by reference or value using the OGC Application Package schema is not allowed (`req/cwl/execution-unit-by-ref` and `req/cwl/execution-unit-by-val`).
- Deployment and replacemend of CWL-based processes as multi-part HTTP operations are not allowed.

## Best Practice for EOAP Conformance Gaps

Upon deployment or replacement, the registry performs some validation checks on the user-supplied CWL/EOAP. However, not all requirements defined by the "OGC Best Practice for Earth Observation Application Package" document can be asserted statically. Among those are:

- Requirement `req/app/cmd-line` which states, that an application must be a non-interactive command line tool.
- Requirement `req/app/container` which states, that all libraries, binaries, executables and configuration files necessary for process invocation must be bundled in a container image.
- Requirement `req/app/stac-input` which states, that if an application processes earth observation data, it must take a directory as input where a self-contained STAC Catalog is stored.
- Requirement `req/app/stac-out` which states, that earth observation data output must be made explicit by using STAC Catalogs.
- Recommodation `rec/app/stac-out-metadata` which states, that a minimum of spatial and temporal metadata must be present in the output STAC Catalog.
- Requirement `req/app-pck-stage-in/clt-stac` which states, that command line tools processing earth observation data should have the corresponding input type set to be "Directory".
- Requirement `req/app-pck-stage-in/wf-stac` which states, that workflow inputs describing earth observation data should have the corresponding input type set to be "Directory".
- Requirement `req/app-pck-stage-out/output-stac` which states, that command line tool output representing earth observation data should have the corresponding output type set to be "Directory".

Furthermore, the follwoing rqeuirements and recommodations are not checked during deployment or replacement of an EOAP, even though it may be possible:

- Requirement `req/app/registry` which states, that the specified container image must be available in a container registry.
- Recommodation `rec/app-pck/fan-out` which states, that when a fan-out step is used, the `ScatterFeatureRequirement` should be set on the top-level workflow with the appropriate `scatterMethod` being set in the workflow step definition.

When these are violated by a supplied EOAP, possible errors are only observable during runtime.

Requirements mandating the existence of certain keys are interpreted to mean that the corresponding value should contain valid data. E.g. the requirement `req/app-pck/clt` mandates, that every instance of CWL's CommandLineTool class must contain the elements id, baseCommand, inputs, requirements and DockerRequirement. While CWL allows to specify an empty array for the baseCommand field, which is treated equivalenty to not specifying it, this and other comparable requirements are interpreted to mean "this field must have a non-empty value" instead of "this field must be present in the text representation of the EOAP"[^key_check]. This results in the considerable restriction of not being able to supply docker images with an `ENTRYPOINT`.

[^key_check]: The rationale being that otherwise, requiring the field to be present seems unreasonable when the field's can denote the absence of said field.

### Stage-In of Earth Observation Data

During deployment or replacement of a process using an EOAP, parameters representing earth observation input data must be supplied using the CWL type "Directory".

These parameters are converted to parameters of type "string" for OGC's input description and is expected that the user supplies a URL pointing to a STAC Item or STAC Itemcollection. The input is made available to the process by creating a STAC Catalog containing the supplied items in a directory with a STAC Catalog named "catalog.json". Since the best practice document allows implementations to not download the STAC Assets themselves[^stac_staging] but only make the STAC "representation" locally available, the application package itself must still be able to

1. Parse STAC Catalogs
1. Download data pointed to by asset's "href" fields in case of remote files.

Supplying entire STAC Catalogs from the get-go is not allowed.

Conversely, while at a minimum discouraged by the best practice guidelines, the current implementation does not try to assign meaning to parameters of type "File" which makes it possible to supply URLs pointing to earth observation data which would then be downloaded directly.

[^stac_staging]: The best practice document is not entirely clear on this. While the first sentence of `req/plt-stage-in/stac-stage` reads like all files (including the assets) must be downloaded, it's also stated that "[t]he platform may adpot a strategy to download and stage-in the files defined in the STAC assets[...]" which in turn sound like the download of assets is optional.
