cwlVersion: v1.2
$namespaces:
  s: 'https://schema.org/'
s:version: 0.0.1
schemas:
  - http://schema.org/version/9.0/schemaorg-current-http.rdf
$graph:
- class: Workflow
  cwlVersion: v1.2
  label: EOAP Testing STAC Input
  doc: This EOAP is to be used in conformance testing for the conformance class "Platform Staged Inputs"
  id: platform-stac-in
  inputs:
    stac:
      label: STAC Object(s) to stage in
      doc: Do not change this URL as the container image below holds the reference STAC Catalog
      type: Directory
      default:
        class: Directory
        path: "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_10TFK_20210713_0_L2A"
  outputs:
    return_value:
      type: int
      outputSource: check_stac_stage_in/exit_code
  steps:
    check_stac_stage_in:
      run: '#check-stac-catalog'
      in:
        stac: stac
      out:
        - exit_code
- class: CommandLineTool
  label: Generate a STAC Output Catalog
  id: '#check-stac-catalog'
  baseCommand: 'diff'
  arguments:
    - '-r'
    - '/reference-stac'
  inputs:
    stac:
      label: The staged-in STAC Catalog
      type: Directory
      inputBinding:
        position: 1
  outputs:
    exit_code:
      type: int
      outputBinding:
        outputEval: $(runtime.exitCode)
  requirements:
    DockerRequirement:
      dockerPull: floriankaterndahl/stac-in-image:latest
