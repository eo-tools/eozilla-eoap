[![Parent Project](https://img.shields.io/badge/Parent%20Project-Eozilla-blue?logo=github)](https://github.com/eo-tools/eozilla)
[![Pixi](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prefix-dev/pixi/main/assets/badge/v0.json)](https://pixi.sh)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v0.json)](https://github.com/charliermarsh/ruff)
[![License](https://img.shields.io/github/license/eo-tools/eozilla-eoap)](https://github.com/eo-tools/eozilla-eoap)

# Eozilla 🦖 – EOAP

This repository provides a partial implementation of the [OGC API - Processes - Part 2: Deploy, Replace, Undeploy](https://docs.ogc.org/DRAFTS/20-044.html) draft specification and the [OGC Best Practice for Earth Observation Application Package](https://docs.ogc.org/bp/20-089r1.html) by extending various components of [Eozilla](https://github.com/eo-tools/eozilla).

It serves as a testbed to assess the current status of EOAP specification and allows Earth Observation Application Package developers to execute their EOAPs locally with minimal setup required by leveraging a fast lightweight HTTP server implementing OGC API - Processes - Part 1: Core, i.e. wraptile.

## Features

- Dynamic Deployment, Replacement and Undeployment of EOAPs encoded in CWL
- (Partial) static validation of incoming EOAPs against CWL specification and EOAP extensions
- Persistent process registry allowing for process re-discovery after restarting the webserver
- Local EOAP execution using [`cwltool`](https://github.com/common-workflow-language/cwltool)

## Installation

The `eozilla-eoap` package is currently not published to any package registry such as pypi or conda and can only be installed using your favorite environment manager's capabilities to install from remote Github repositories. Alternatively, clone this repository and activate the pixi environment.

```bash
git clone git@github.com:eo-tools/eozilla-eoap.git

cd eozilla-eoap

pixi install
```

## Usage and Documentation

Please refer to the online documentation for a detailed project description, documentation, conformance restrictions and examples.
