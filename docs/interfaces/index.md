# Interfaces

The [OGC API - Processes - Part 1: Core](https://docs.ogc.org/is/18-062r2/18-062r2.html) and [ OGC API - Processes - Part 2: Deploy, Replace, Undeploy](https://docs.ogc.org/DRAFTS/20-044.html) documents describe rather generic operations for remote execution of processes working with Earth Observation data and their dynamic creation, replacement and deletion.

While the [OGC Best Practice for Earth Observation Application Package](https://docs.ogc.org/bp/20-089r1.html) restricts some of these, both the existing standard and its drafted extension remain rather unconstrained. Where possible, generic base classes are used to describe what operations need to occur but hide their concrete implementation in hope of easing later changes and/or extensions.
