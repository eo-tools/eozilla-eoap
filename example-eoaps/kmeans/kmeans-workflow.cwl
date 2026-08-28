cwlVersion: v1.2
$namespaces:
  s: 'https://schema.org/'
s:version: 0.0.1
schemas:
  - http://schema.org/version/9.0/schemaorg-current-http.rdf
$graph:
- class: Workflow
  cwlVersion: v1.2
  label: Unsupervised classification of Sentinel-2 Scenes using k-means
  doc: This EOAP implements a workflow that computes an unsupervised classification using k-means clustering algorithm for Sentinel-2 imagery, distinct for each input image. It's intended to represent a somewhat "realistic" multi-step workflow. By registering the accompanying CWL document, the workflow is made available under `/processes/kmeans-workflow`.
  id: kmeans-workflow
  requirements:
    ScatterFeatureRequirement: {}
    MultipleInputFeatureRequirement: {}
  inputs:
    stac_url:
      label: Input STAC URL
      doc: URL Pointing to a STAC Feature Collection. Input was only tested with https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/ based items. Other STAC catalogs may have slightly different formats that break scripts used.
      type: Directory
    band_selection:
      label: Band selection to use
      doc: List of band names (used in STAC catalog as common name) to extract/"manifest"
      type: string[]
      default:
        - blue
        - green
        - red
        - nir
    number_of_clusters:
      label: Number of clusters
      doc: Number of clusters to use while running unsupervised k-means clustering
      type: int
      default: 3
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
  steps:
    raster_stack_node:
      run: '#stack-raster-bands'
      in:
        local_stac_catalog: stac_url
        band_selection: band_selection
      out:
        - stack_rasters_out
    kmeans_node:
      run: '#clustering'
      in:
        input_stack: raster_stack_node/stack_rasters_out
        number_of_clusters: number_of_clusters
      scatter: input_stack
      out:
        - clustering_out
    preview_generation_node:
      run: '#generate-jpeg-preview'
      in:
        cluster_result: kmeans_node/clustering_out
      out:
        - preview_out
      scatter: cluster_result
    metadata_json_node:
      run: '#gdalinfo-json-output'
      in:
        cluster_result: kmeans_node/clustering_out
      out:
        - metadata_out
      scatter: cluster_result
    statistics_extraction_node:
      run: '#jq-extract-stats'
      in:
        metadata_json: metadata_json_node/metadata_out
      out:
        - stats_out
      scatter: metadata_json
    generate_output_stac_catalog:
      run: '#generate-stac-catalog'
      in:
        files: kmeans_node/clustering_out
      out:
        - stac_output
- class: CommandLineTool
  label: Query STAC Catalog
  id: '#stac-query'
  baseCommand: [ 'Rscript', '--vanilla', '/scripts/00-query-catalog.r' ]
  inputs:
    stac_url:
      type: Directory
      inputBinding:
        position: 0
    stac_collection:
      type: string
      inputBinding:
        position: 1
    bbox:
      type: string
      inputBinding:
        position: 2
    datetime:
      type: string
      inputBinding:
        position: 3
  outputs:
    stac_query_out:
      outputBinding:
        glob: local_query_results.json
      type: File
  requirements:
    DockerRequirement:
      dockerPull: quay.io/bcdev/kmeans-workflow:0.0.1
    NetworkAccess:
      networkAccess: true
- class: CommandLineTool
  label: Stack Raster Bands
  id: '#stack-raster-bands'
  baseCommand: [ 'Rscript', '--vanilla', '/scripts/01-combine-assets.r' ]
  inputs:
    local_stac_catalog:
      type: Directory
      inputBinding:
        position: 0
    band_selection:
      type: string[]
      inputBinding:
        position: 1
        itemSeparator: ','
  outputs:
    stack_rasters_out:
      outputBinding:
        glob: '*.gtiff'
      type: File[]
  requirements:
    DockerRequirement:
      dockerPull: quay.io/bcdev/kmeans-workflow:0.0.1
    NetworkAccess:
      networkAccess: true
- class: CommandLineTool
  label: K-Means Clustering
  id: '#clustering'
  baseCommand: [ 'Rscript', '--vanilla', '/scripts/02-kmeans.r' ]
  inputs:
    input_stack:
      type: File
      inputBinding:
        position: 0
    number_of_clusters:
      type: int
      inputBinding:
        position: 1
  outputs:
    clustering_out:
      outputBinding:
        glob: '*_clustered.gtiff'
      type: File
  requirements:
    DockerRequirement:
      dockerPull: quay.io/bcdev/kmeans-workflow:0.0.1
- class: CommandLineTool
  label: JPEG Preview Generation
  id: '#generate-jpeg-preview'
  baseCommand: [ 'Rscript', '--vanilla', '/scripts/03-mapping.r' ]
  inputs:
    cluster_result:
      type: File
      inputBinding:
        position: 0
  outputs:
    preview_out:
      outputBinding:
        glob: '*preview.jpeg'
      type: File
  requirements:
    DockerRequirement:
      dockerPull: quay.io/bcdev/kmeans-workflow:0.0.1
- class: CommandLineTool
  label: Generate a STAC Output Catalog
  id: '#generate-stac-catalog'
  baseCommand: [ 'python', '/scripts/output-generator.py' ]
  inputs:
    files:
      type: File[]
      inputBinding:
        position: 0
        prefix: '--inputs'
  outputs:
    stac_output:
      type: Directory
      outputBinding:
        glob: 'stac-catalog'
  requirements:
    DockerRequirement:
      dockerPull: quay.io/bcdev/kmeans-workflow:0.0.1
- class: CommandLineTool
  label: JSON Metadata Extraction
  id: '#gdalinfo-json-output'
  baseCommand: [ 'gdalinfo' ]
  arguments: [ '-json', '-stats' ]
  inputs:
    cluster_result:
      type: File
      inputBinding:
        position: 0
  outputs:
    metadata_out: stdout
  requirements:
    DockerRequirement:
      dockerPull: ghcr.io/osgeo/gdal:ubuntu-small-3.13.3-amd64
- class: CommandLineTool
  label: Extract Statistics from Metadata
  id: '#jq-extract-stats'
  baseCommand: [ "jq" ]
  arguments: ['.bands[] | .metadata | ."" | {("stats"): .}']
  inputs:
    metadata_json:
      type: File
      inputBinding:
        position: 1
  outputs:
    stats_out:
      outputBinding:
        glob: stdout.txt
        loadContents: true
        outputEval: $(self[0].contents.split('\n'))
      type: string[]
  stdout: stdout.txt
  requirements:
    InlineJavascriptRequirement: {}
    DockerRequirement:
      dockerPull: quay.io/bcdev/kmeans-workflow:0.0.1

