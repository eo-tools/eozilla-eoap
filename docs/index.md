# Eozilla's Sample Implementation for DRU and EOAPs

Earth Observation Application Package are a special encoding of processes using [CWL](https://www.commonwl.org/) in order to allow portable and reproducable execution of software that, possibly, processes earth observational data. At the time of writing, software support for their development and execution is limited and while implementation exist (e.g. [`zoo-project`](https://zoo-project.org/)), there's a lack of easy-to use services enabling EOAP execution.

Eozilla's EOAP extension is meant to serve as a local test bed for developing Earth Observation Application Packages and test them in an environment that comes close to a real service platform. While no specification (OGC API - Processes - Part 1: Core, OGC API - Processes - Part 2: DRU, OGC Best Practice for Earth Observation Application Package) is implemented in its entirety, the resulting service is complete enough to serve above-mentioned purpose.

The main benefits of using this project for testing your EOAPs are:

- `eozilla-eoap` uses few dependencies and the Pixi project manager, thus it's easy to install and getting started. See the [Service](./service/index.md) documentation for instructions.
- Execution in a "service-like" environment that resembles a real service platform more closely compared to manual execution with CWL runners like `cwltool`.
- Integration with the [`cuiman`](https://eo-tools.github.io/eozilla/cuiman/) API client allows more ergonomic interaction with the service compared to execution of raw cURL commands form the command line. Additionally, the webserver provides an in-browser interface through swagger.
- Partial validation of the supplied EOAP according to the requirements posed by the OGC. See the [Restrictions](./restrictions.md) page for an overview of what requirements are checked and which are not.
- To facilitate easy testing, local STAC Items, STAC ItemCollections and STAC Catalogs are accepted as input by supplying the service with a file-URL (`file://...`). This requires that the file pointed to is accessible by the service and that all `href` entries are absolute file paths.

## OGC API - Processes - Part 2: Deploy, Replace, Undeploy

The "OGC API - Processes - Part 2: Deploy, Replace, Undeploy" draft specification defines the behaviour and operations necessary for a server to accept new OGC Processes, replace existing ones and remove them. These operations are made available by allowing new HTTP operations compared to the core specification as well as adding a new endpoint, the overview below is copied from the [online version](https://docs.ogc.org/DRAFTS/20-044.html) of the draft.

| **Resource endpoint**          | **HTTP method** |        |         |          |
|--------------------------------|-----------------|--------|---------|----------|
|                                | _GET_           | _POST_ | _PUT_   | _DELETE_ |
| /processes                     | n/a             | deploy | n/a     | n/a      |
| /processes/{processID}         | n/a             | n/a    | replace | undeploy |
| /processes/{processID}/package | package         | n/a    | n/a     | n/a      |

The draft specification defines three conformance classes for deploying and replacing processes (OGC Application Package, Docker, CWL) that are not mandatory to support by a conforming implementation. As such, only CWL documents are accepted by this Eozilla implementation with the caveat of not supporting multi-part HTTP requests that would allow a client to submit multiple related CWL documents in a single request. Instead, only so-called packed CWL documents are supported; these are stand-alone documents where all workflow and tool definitions are inlined. For a detailed overview of other restrictions, see the [Restrictions](restrictions.md) page.

## OGC Best Practice for Earth Observation Application Package

The best practice guideline concretises the "OGC API - Processes - Part 2: Deploy, Replace, Undeploy" draft specification. It defines requirements that the [application](https://docs.ogc.org/bp/20-089r1.html#toc18) (a piece of software that does some computation), the [application package](https://docs.ogc.org/bp/20-089r1.html#toc24) (the bundle or encoding of the application that adds metadata as well) and the [platform](https://docs.ogc.org/bp/20-089r1.html#toc34) (service that accepts EOAPs, execution requests and manages process execution from the point of the user). In addition, interfaces of how data should be made available to an application package and to the user are specified. The entire document can be found [online](https://docs.ogc.org/bp/20-089r1.html).

To decouple the platform and the application unit, best practices stemming e.g. from cloud processing and scientific workflow management are applied such as containerization and platform-agnostic descriptions of execution units in the form of the Common Workflow Language. Additionally, data discovery both for input and output is mandated to be handled by leveraging the STAC specification for earth observation data.

In the context of EOAPs, the platform is responsible for DRU operations including validation of newly deployed processes and mapping interfaces between the various components, data stage-in (making data available for a process), data stage-out (making results available to the user after successful execution) and dispatching process execution to some processing back-end.
