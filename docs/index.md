# Eozilla's Sample Implementation for DRU and EOAPs

## OGC API - Processes - Part 2: Deploy, Replace, Undeploy

The "OGC API - Processes - Part 2: Deploy, Replace, Undeploy" draft specification defines the behavior and operations necessary for a server to accept new OGC Processes, replace exisiting ones and remove them. These operations are made available by allowing new HTTP operations compared to the core specification as well as adding a new endpoint, the overview below is copied from the [online version](https://docs.ogc.org/DRAFTS/20-044.html) of the draft.

| **Resource endpoint**          | **HTTP method** |        |         |          |
|--------------------------------|-----------------|--------|---------|----------|
|                                | _GET_           | _POST_ | _PUT_   | _DELETE_ |
| /processes                     | n/a             | deploy | n/a     | n/a      |
| /processes/{processID}         | n/a             | n/a    | replace | undeploy |
| /processes/{processID}/package | package         | n/a    | n/a     | n/a      |

The draft specification defines three conformance classes for deploying and replacing processes (OGC Application Package, Docker, CWL) that are not mandatory to support by a conforming implementation. As such, only CWL documents are accepted by this Eozilla implementation with the caveat of not supporting multi-part HTTP requests that would allow a client to submit multiple related CWL documents in a single rqeuest. Instead, only so-called packed CWL documents are supported; these are standalone documents where all workflow and tool definitions are inlined. For a detailed overview of other restrictions, see the [Restrictions](/restrictions) page.

## OGC Best Practice for Earth Observation Application Package

The best practice guideline concretises the "OGC API - Processes - Part 2: Deploy, Replace, Undeploy" draft specification. It defines requirements that the [application](https://docs.ogc.org/bp/20-089r1.html#toc18) (a piece of software that does some compuation), the [application package](https://docs.ogc.org/bp/20-089r1.html#toc24) (the bundle or encoding of the application that adds metadata as well) and the [platform](https://docs.ogc.org/bp/20-089r1.html#toc34) (service that accepts EOAPs, execution requests and manages process execution from the point of the user). In addition, interfaces of how data should be made available to an application package and to the user are specified. The entire document can be found [online](https://docs.ogc.org/bp/20-089r1.html).

To decouple the platform and the application unit, best practices stemming e.g. from cloud processing and scientific workflow management are applied such as containerization and platform-agnostic descriptions of execution units in the form of the Common Workflow Language. Additionally, data discovery both for input and output is mandated to be handled by levarging the STAC specification for earth observation data.

In the context of EOAPs, the platform is repsonsible for DRU operations including validation of newly deployed processes and mapping interfaces between the various components, data stage-in (making data available for a process), data stage-out (making results available to the user after successful execution) and dispatching process execution to some processing backend.
