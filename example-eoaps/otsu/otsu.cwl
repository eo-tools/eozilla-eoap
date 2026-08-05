cwlVersion: v1.0
$namespaces:
  s: https://schema.org/
s:version: 1.0.0
schemas:
  - http://schema.org/version/9.0/schemaorg-current-http.rdf
$graph:
  - class: Workflow
    id: otsu-workflow
    label: Water bodies detection based on NDWI and the otsu threshold
    doc: Water bodies detection based on NDWI and otsu threshold applied to a single Sentinel-2 COG STAC item
    requirements: []
    inputs:
      aoi:
        label: area of interest
        doc: area of interest as a bounding box
        type: string
      epsg:
        label: EPSG code
        doc: EPSG code
        type: string
        default: "EPSG:4326"
      bands:
        label: bands used for the NDWI
        doc: bands used for the NDWI
        type: string[]
        default: ["green", "nir"]
      item:
        doc: Reference to a STAC item
        label: STAC item reference
        type: Directory
    outputs:
      - id: stac_catalog
        outputSource:
          - node_detect/stac-catalog
        type: Directory
    steps:
      node_detect:
        run: "#detect-water-body"
        in:
          item: item
          aoi: aoi
          epsg: epsg
          band: bands
        out:
          - stac-catalog
  - class: CommandLineTool
    id: detect-water-body
    requirements:
      InlineJavascriptRequirement: {}
      EnvVarRequirement:
        envDef:
          PYTHONPATH: /app
      ResourceRequirement:
        coresMax: 1
        ramMax: 512
    hints:
      DockerRequirement:
        dockerPull: ghcr.io/eoap/quickwin/detect-water-body@sha256:2c2c8749126bb8bc5cdc67347590232c51d2d4e8a82fae5b1a4fc47793648ff0
    baseCommand: ["python", "-m", "app"]
    arguments: []
    inputs:
      item:
        type: Directory
        inputBinding:
          prefix: --input-item
      aoi:
        type: string
        inputBinding:
          prefix: --aoi
      epsg:
        type: string
        inputBinding:
          prefix: --epsg
      band:
        type:
          - type: array
            items: string
            inputBinding:
              prefix: '--band'
    outputs:
      stac-catalog:
        outputBinding:
          glob: .
        type: Directory
s:codeRepository:
  URL: https://github.com/eoap/quickwin.git
s:author:
  - class: s:Person
    s.name: Jane Doe
    s.email: jane.doe@acme.earth
    s.affiliation: ACME
