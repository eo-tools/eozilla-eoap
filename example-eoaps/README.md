# Example Earth Observation Application Packages (EOAPs)

This directory contains resources necessary to deploy processes conforming to the requirements described in the [](), though the examples themselves do not consume or produce Earth Observation data.

## Sleep EOAP

> [!NOTE]
> This example was copied and slightly adapted from eozilla's local test service implementation and can be found [under this URL](https://github.com/eo-tools/eozilla/blob/main/wraptile/src/wraptile/services/local/testing.py).

The sleep EOAP is a simple process that calls a Python function that sleeps for a given amount of time. By registering the accompanying [CWL workflow](./sleep/sleep-workflow.cwl), the process will be available at `/processes/sleep-workflow`.

## Pimes EOAP

> [!NOTE]
> This example was copied and slightly adapted from eozilla's local test service implementation and can be found [under this URL](https://github.com/eo-tools/eozilla/blob/main/wraptile/src/wraptile/services/local/testing.py).

The primes EOAP is a simple process that calculates prime numbers between a lower and an upper bound. By registering the accompanying [CWL workflow](./primes/primes-workflow.cwl), the process will be available at `/processes/primes-workflow`.

## Echo EOAP

The echo EOAP is a simple process that simply echos the user's input to a files and returns it. By registering the accompanying [CWL workflow](./echo/echo-workflow.cwl), the process will be available at `/processes/echo-workflow`.

## Cat EOAP

> [!IMPORTANT]
> As the file's content is loaded directly, the maximum allowed size is 65536 bytes. The workflow will error out without a specific reason supplied to the user.

The cat EOAP is a simple process that cat the contents of a user-supplied file to stdout. By registering the accompanying CWL workflow, the process will be available at `/processes/cat-workflow`.