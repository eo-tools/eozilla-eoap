The service sub-module provides the actual DRU implementation as well as means to validate incoming Earth Observation Application Packages.

To start a local service instance, activate the Pixi environment and run `wraptile run -- eozilla_eoap.main:service`. The command line interface of `wraptile` is documented [here](https://eo-tools.github.io/eozilla/wraptile/).

## Example Usage Scenario Walkthrough

The following section illustrates how a user can interact with a running server instance. Configuration parametery may easily be changed by adapting the module named above which is copied verbatim here for clarity. The EOAPs referenced are detailed in the [Example EOAPs](examples) section.

```python
from pathlib import Path

from eozilla_eoap.cwltool.runner import CwlToolRunner
from eozilla_eoap.procolike.local_eoap_registry import LocalEaopRegistry
from eozilla_eoap.service import LocalEoapService

SERVICE_BASE_DIR: Path = Path().cwd().absolute()

service = LocalEoapService(
    title="Eozilla DRU API Server",
    description="Local DRU server implementing the OGC API - Processes Part 2.0 Draft standard, adhering to the EOAP BP guide",
    process_registry=LocalEaopRegistry(
        Path(SERVICE_BASE_DIR, "eoap-service", "registry")
    ),
    cwl_runner=CwlToolRunner(),
    persitency_directory=Path(SERVICE_BASE_DIR, "eoap-service", "runs"),
)
```

### Process Query

Initially, the server does not provide any processes.

```bash title="process list request"
curl -X 'GET' \
  'http://127.0.0.1:8008/processes' \
  -H 'accept: application/json'
```

```json title="process list response"
{
  "processes": [],
  "links": [
    {
      "href": "http://127.0.0.1:8008/processes",
      "rel": "self",
      "type": "application/json",
      "hreflang": "en",
      "title": "get_processes"
    }
  ]
}
```

### Process Deployment

A new process can be deployed with a POST request to the `/processes` endpoint and is returned by the server when querying the `/processes` again.

```bash title="process deployment request"
curl -X 'POST' \
    'http://127.0.0.1:8008/processes' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/cwl+yaml' \
    --data-binary @kmeans/kmeans-workflow.cwl
```

```json title="process deployment response"
{
  "id": "kmeans-workflow",
  "version": "0.0.1",
  "mutable": true,
  "links": [
    {
      "href": "http://127.0.0.1:8008/processes",
      "rel": "self",
      "type": "application/json",
      "hreflang": "en",
      "title": "deploy_process"
    }
  ]
}
```

```bash title="process list request with process"
curl -X 'GET' \
  'http://127.0.0.1:8008/processes' \
  -H 'accept: application/json'
```

```json title="process list response with process"
{
  "processes": [
    {
      "title": "Unsupervised classification of Sentinel-2 Scenes using k-means",
      "description": "This EOAP implements a workflow that computes an unsupervised classification using k-means clustering algorithm for Sentinel-2 imagery, distinct for each input image. It's intended to represent a somewhat \"realistic\" multi-step workflow. By registering the accompanying CWL document, the workflow is made available under `/processes/kmeans-workflow`.",
      "id": "kmeans-workflow",
      "version": "0.0.1",
      "mutable": true
    }
  ],
  "links": [
    {
      "href": "http://127.0.0.1:8008/processes",
      "rel": "self",
      "type": "application/json",
      "hreflang": "en",
      "title": "get_processes"
    }
  ]
}
```

### Process Description

The formal description of such a mutable process such as the one deployed can be queried by sending a GET request to the `/processes/{processId}/package` endpoint. This can be useful e.g. to see the possible/mandatory process argument descriptions. Note that the respone is truncated here since the OGC Application Package format includes the EOAP definition itself as well.

```bash title="process description request"
curl -X 'GET' \
  'http://127.0.0.1:8008/processes/kmeans-workflow/package' \
  -H 'accept: application/ogcapppkg+json'
```

```json title="process description response"
{
  "processDescription": {
    "process": {
      "title": "Unsupervised classification of Sentinel-2 Scenes using k-means",
      "description": "This EOAP implements a workflow that computes an unsupervised classification using k-means clustering algorithm for Sentinel-2 imagery, distinct for each input image. It's intended to represent a somewhat \"realistic\" multi-step workflow. By registering the accompanying CWL document, the workflow is made available under `/processes/kmeans-workflow`.",
      "id": "kmeans-workflow",
      "version": "0.0.1",
      "mutable": true,
      "inputs": {
        "stac_url": {
          "title": "Input STAC URL",
          "description": "URL Pointing to a STAC Feature Collection. Input was only tested with https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/ based items. Other STAC catalogs may have slightly different formats that break scripts used.",
          "minOccurs": 1,
          "maxOccurs": 1,
          "schema": {
            "type": "string",
            "nullable": false,
            "format": "url"
          }
        },
        "band_selection": {
          "title": "Band selection to use",
          "description": "List of band names (used in STAC catalog as common name) to extract/\"manifest\"",
          "minOccurs": 0,
          "maxOccurs": "unbounded",
          "schema": {
            "type": "array",
            "default": [
              "blue",
              "green",
              "red",
              "nir"
            ],
            "nullable": true,
            "items": {
              "type": "string",
              "nullable": false
            },
            "minItems": 1
          }
        },
        "number_of_clusters": {
          "title": "Number of clusters",
          "description": "Number of clusters to use while running unsupervised k-means clustering",
          "minOccurs": 0,
          "maxOccurs": 1,
          "schema": {
            "type": "integer",
            "default": 3,
            "nullable": true
          }
        }
      },
      "outputs": {
        "classification_results": {
          "schema": {
            "type": "string",
            "nullable": false,
            "format": "url"
          }
        },
        "classification_previews": {
          "schema": {
            "type": "array",
            "nullable": false,
            "items": {
              "type": "string",
              "nullable": false,
              "format": "url"
            },
            "minItems": 1
          }
        },
        "stats_overview": {
          "schema": {
            "type": "array",
            "nullable": false,
            "items": {
              "type": "array",
              "nullable": false,
              "items": {
                "type": "string",
                "nullable": false
              },
              "minItems": 1
            },
            "minItems": 1
          }
        }
      }
    }
  },
  "executionUnit": {...}
}
```

### Process Execution

To execute a particular process, a POST request must be made to the `/processes/{processId}/execute` endpoint with the process arguments encoded as JSON sent in the body.

```bash title="process execution request"
curl -X 'POST' \
    'http://127.0.0.1:8008/processes/kmeans-workflow/execution' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    --data '{
    "inputs": {
        "stac_url": "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_10TFK_20210713_0_L2A"
    }
}'
```

```json title="process execution response"
{
  "jobID": "bd60bada-9528-4526-acbf-ca3732558b55",
  "processID": "kmeans-workflow",
  "status": "running",
  "created": "2026-08-26T06:57:03.341134Z",
  "started": "2026-08-26T06:57:03.341744Z"
}
```

### Job Information

Information about jobs during and after execution can be queried with a request to the `/jobs/{jobId}` endpoint

```bash title="job information request"
curl -X 'GET' \
    'http://127.0.0.1:8008/jobs/bd60bada-9528-4526-acbf-ca3732558b55' \
    -H 'accept: application/json'
```

```json title="job information response"
{
  "jobID": "bd60bada-9528-4526-acbf-ca3732558b55",
  "processID": "kmeans-workflow",
  "status": "running",
  "created": "2026-08-26T06:57:03.341134Z",
  "started": "2026-08-26T06:57:03.341744Z"
}
```

### Job Dismissal

Job dismissal can be used both to interrupt a running process and to remove job outputs, depending on the state of the job is in at the time of the dismissal request.

!!! warning "Job Dismissal is Synchronous"

    The service allows cancellation of processes before they finish via the dismiss endpoint. The only point where an application unaware of such context-clues can be interrupted is before a new job step. Long running steps may delay the dismissal of running process indefinitively. In combination with the circumstance that cancelled processes are awaited for, the user may experience severe delays after requesting cancellation of a process.

```bash title="job dismissal request"
curl -X 'DELETE' \
    'http://127.0.0.1:8008/jobs/bd60bada-9528-4526-acbf-ca3732558b55' \
    -H 'accept: application/json'
```

```json title="job dismissal response"
{
  "jobID": "bd60bada-9528-4526-acbf-ca3732558b55",
  "processID": "kmeans-workflow",
  "status": "dismissed",
  "created": "2026-08-26T06:57:03.341134Z",
  "started": "2026-08-26T06:57:03.341744Z",
  "finished": "2026-08-26T07:06:22.697123Z"
}
```

### Job Results

After successfull execution while the job is not dismissed and the server not restarted, the process output according to the original EOAP definition can be accessed with a request to `/jobs/{jobId}/results`.

```bash title="job results request"
curl -X 'GET' \
    'http://127.0.0.1:8008/jobs/00f2228c-30f2-4069-b1ff-462721524947/results' \
    -H 'accept: application/json'
```

```json title="job results response"
{
  "classification_previews": [
    "file:///home/user/eozilla-eoap/eoap-service/runs/00f2228c-30f2-4069-b1ff-462721524947/out/S2B_10TFK_20210713_0_L2A_clustered_preview.jpeg"
  ],
  "classification_results": "/home/user/eozilla-eoap/eoap-service/runs/00f2228c-30f2-4069-b1ff-462721524947/out/stac-catalog/catalog.json",
  "stats_overview": [
    [
      "{",
      "  \"stats\": {",
      "    \"STATISTICS_MINIMUM\": \"1\",",
      "    \"STATISTICS_MAXIMUM\": \"3\",",
      "    \"STATISTICS_MEAN\": \"-9999\",",
      "    \"STATISTICS_STDDEV\": \"-9999\"",
      "  }",
      "}",
      ""
    ]
  ]
}
```

```yaml title="Corresponding Workflow Output Definition"
outputs:
    classification_results:
        type: Directory
        outputSource: generate_output_stac_catalog/stac_output
    classification_previews:
        type: File[]
        outputSource: preview_generation_node/preview_out
    stats_overview:
        type:
        type: array
        items:
            type: array
            items: string
        outputSource: statistics_extraction_node/stats_out
```