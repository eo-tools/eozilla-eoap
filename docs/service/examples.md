# Example Earth Observation Application Packages (EOAPs)

!!! important
    The files referenced when deploying processes reference those in the `example-eoaps` directory located at the root of this repository ([https://github.com/eo-tools/eozilla-eoap](https://github.com/eo-tools/eozilla-eoap)). Alternatiely, you can follow the hyperlinks referencing the CWL workflows below.

## Sleep EOAP

!!! note 
    This example was copied and slightly adapted from eozilla's local test service implementation and can be found [under this URL](https://github.com/eo-tools/eozilla/blob/main/wraptile/src/wraptile/services/local/testing.py).

The sleep EOAP is a simple process that calls a Python function that sleeps for a given amount of time. By registering the accompanying [CWL workflow](https://raw.githubusercontent.com/eo-tools/eozilla-eoap/refs/heads/main/example-eoaps/sleep/sleep-workflow.cwl), the process will be available at `/processes/sleep-workflow`.

### Deploy and Execute Example

The process can be deployed from the command line with the following command, assuming the server is listenting on `127.0.0.1:8008`.

```console
curl -X 'POST' \
    'http://127.0.0.1:8008/processes' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/cwl+yaml' \
    --data-binary @sleep/sleep-workflow.cwl
```

The process can be executed as follows

```console
curl -X 'POST' \
    'http://127.0.0.1:8008/processes/sleep-workflow/execution' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    --data '{
    "inputs": {
        "duration": 30
    }
}'
```

## Pimes EOAP

!!! note
    This example was copied and slightly adapted from eozilla's local test service implementation and can be found [under this URL](https://github.com/eo-tools/eozilla/blob/main/wraptile/src/wraptile/services/local/testing.py).

The primes EOAP is a simple process that calculates prime numbers between a lower and an upper bound. By registering the accompanying [CWL workflow](https://raw.githubusercontent.com/eo-tools/eozilla-eoap/refs/heads/main/example-eoaps/primes/primes-workflow.cwl), the process will be available at `/processes/primes-workflow`.

### Deploy and Execute Example

The process can be deployed from the command line with the following command, assuming the server is listenting on `127.0.0.1:8008`.

```console
curl -X 'POST' \
    'http://127.0.0.1:8008/processes' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/cwl+yaml' \
    --data-binary @primes/primes-workflow.cwl
```

The process can be executed as follows

```console
curl -X 'POST' \
    'http://127.0.0.1:8008/processes/primes-workflow/execution' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    --data '{
    "inputs": {
        "minimum": 0,
        "maximum": 150
    }
}'
```

## Echo EOAP

The echo EOAP is a simple process that simply echos the user's input to a files and returns it. By registering the accompanying [CWL workflow](https://raw.githubusercontent.com/eo-tools/eozilla-eoap/refs/heads/main/example-eoaps/echo/echo-workflow.cwl), the process will be available at `/processes/echo-workflow`.

### Deploy and Execute Example

The process can be deployed from the command line with the following command, assuming the server is listenting on `127.0.0.1:8008`.

```console
curl -X 'POST' \
    'http://127.0.0.1:8008/processes' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/cwl+yaml' \
    --data-binary @echo/echo-workflow.cwl
```

The process can be executed as follows

```console
curl -X 'POST' \
    'http://127.0.0.1:8008/processes/echo-workflow/execution' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    --data '{
    "inputs": {
        "message": "This is a wonderful test message!"
    }
}'
```

## Cat EOAP

!!! important
    As the file's content is loaded directly, the maximum allowed size is 65536 bytes. The workflow will error out without a specific reason supplied to the user.

The cat EOAP is a simple process that cat the contents of a user-supplied file to stdout. By registering the accompanying [CWL workflow](https://raw.githubusercontent.com/eo-tools/eozilla-eoap/refs/heads/main/example-eoaps/cat/cat-workflow.cwl), the process will be available at `/processes/cat-workflow`.

### Deploy and Execute Example

The process can be deployed from the command line with the following command, assuming the server is listenting on `127.0.0.1:8008`.

```console
curl -X 'POST' \
    'http://127.0.0.1:8008/processes' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/cwl+yaml' \
    --data-binary @cat/cat-workflow.cwl
```

The process can be executed as follows

```console
curl -X 'POST' \
    'http://127.0.0.1:8008/processes/cat-workflow/execution' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    --data '{
    "inputs": {
        "file": "https://raw.githubusercontent.com/eo-tools/eozilla-eoap/refs/heads/main/README.md"
    }
}'
```

## OTSU EOAP

!!! note 
    The workflow definition is licensed under the [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Changes compared to the original source include re-definition of input parameters denoting STAC catalogs to be of type `Directory` as well as changing the version key from `softwareVersion` to `version`.

The water bodies/OTSU workflow is process that generates a water mask by using the OTSU thresholding image processing technique. The EOAP is based on the workflow provided in the Quickwin Github repository (https://github.com/eoap/quickwin), see also their accompanying documentation at https://eoap.github.io/quickwin/. By registering the accompanying CWL workflow, the process will be available at `/processes/otsu-workflow`.

### Deploy and Execute Example

The process can be deployed from the command line with the following command, assuming the server is listenting on `127.0.0.1:8008`.

```console
curl -X 'POST' \
    'http://127.0.0.1:8008/processes' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/cwl+yaml' \
    --data-binary @otsu/otsu-workflow.cwl
```

The process can be executed as follows

```console
curl -X 'POST' \
    'http://127.0.0.1:8008/processes/otsu-workflow/execution' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    --data '{
    "inputs": {
        "item": "https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2B_10TFK_20210713_0_L2A",
        "aoi": "-121.399,39.834,-120.74,40.472",
        "epsg": "EPSG:4326"
    }
}'
```

## K-Means Clustering EOAP

This workflow takes a STAC item or STAC item collection as input, creates multi-band stacks according to the specified `band_list` argument, creates k-means clustering results independently and renders previews of the results as well as some non-sensical statistics summary. It's main goal is not to implement a sophisticated or novel processing but rather illustrate how multi-step EOAP may be defined (and to that extent test process cancellation). Note, that the server implementation present only interacts with the entrypoint apart from validating presence of some fields.

By registering the accompanying [CWL workflow](https://raw.githubusercontent.com/eo-tools/eozilla-eoap/refs/heads/main/example-eoaps/kmeans/kmeans-workflow.cwl), the process will be available at `/processes/kmeans-workflow`.

### Deploy and Execute Example

The process can be deployed from the command line with the following command, assuming the server is listenting on `127.0.0.1:8008`.

```console
curl -X 'POST' \
    'http://127.0.0.1:8008/processes' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/cwl+yaml' \
    --data-binary @kmeans/kmeans-workflow.cwl
```

The process can be executed as follows (dismissing optional arguments)

```console
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
