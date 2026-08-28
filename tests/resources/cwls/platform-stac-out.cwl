cwlVersion: v1.2
$namespaces:
  s: 'https://schema.org/'
s:version: 0.0.1
schemas:
  - http://schema.org/version/9.0/schemaorg-current-http.rdf
$graph:
- class: Workflow
  cwlVersion: v1.2
  label: EOAP Testing STAC Output
  doc: This EOAP is to be used in conformance testing for the conformance class "Platform Staged Output"
  id: platform-stac-out
  inputs:
    nonsense:
      label: Placeholder Argument
      doc: This argument does nothing.
      type: string
      default: "placeholder"
  outputs:
    stac_output:
      type: Directory
      outputSource: copy_stac_catalog/stac_output
  steps:
    copy_stac_catalog:
      run: '#generate-stac-catalog'
      in:
        nonsense: nonsense
      out:
        - stac_output
- class: CommandLineTool
  label: Generate a STAC Output Catalog
  id: '#generate-stac-catalog'
  baseCommand: [ 'cp', '-r', '/example-stac', '.' ]
  inputs:
    nonsense:
      type: string
  outputs:
    stac_output:
      type: Directory
      outputBinding:
        glob: 'example-stac'
  requirements:
    DockerRequirement:
      dockerPull: quay.io/bcdev/stac-out-image:latest
