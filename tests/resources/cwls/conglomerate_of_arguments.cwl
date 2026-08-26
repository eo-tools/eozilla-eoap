cwlVersion: v1.2
$namespaces:
  s: 'https://schema.org/'
's:version': 0.0.1
schemas:
  - 'http://schema.org/version/9.0/schemaorg-current-http.rdf'
$graph:
  - class: Workflow
    cwlVersion: v1.2
    label: EOAP Testing Type Mapping
    doc: >-
      This EOAP is to be used in conformance testing for the conformance class
      "Platform". This EOAP is not intended to be executed!
    id: platform
    inputs:
      boolean_input:
        label: Placeholder label for the input
        doc: Placeholder doc-string for the input
        type: boolean
      int_input:
        label: Placeholder label for the input
        doc: Placeholder doc-string for the input
        type: int
      long_input:
        label: Placeholder label for the input
        doc: Placeholder doc-string for the input
        type: long
      float_input:
        label: Placeholder label for the input
        doc: Placeholder doc-string for the input
        type: float
      double_input:
        label: Placeholder label for the input
        doc: Placeholder doc-string for the input
        type: double
      string_input:
        label: Placeholder label for the input
        doc: Placeholder doc-string for the input
        type: string
      enum_input:
        label: Placeholder label for the input
        doc: Placeholder doc-string for the input
        type:
          type: enum
          symbols:
            - option 1
            - option 2
      file_input:
        label: Placeholder label for the input
        doc: Placeholder doc-string for the input
        type: File
      directory_input:
        label: Placeholder label for the input
        doc: Placeholder doc-string for the input
        type: Directory
      optional_int_input:
        label: Placeholder label for the input
        doc: Placeholder doc-string for the input
        type: int?
      array_enum_input:
        label: Placeholder label for the input
        doc: Placeholder doc-string for the input
        type:
          type: array
          items:
            type: enum
            symbols:
              - option 1
              - option 2
    outputs:
      boolean_output:
        label: Placeholder label for the output
        doc: Placeholder doc-string for the output
        type: boolean
      int_output:
        label: Placeholder label for the output
        doc: Placeholder doc-string for the output
        type: int
      long_output:
        label: Placeholder label for the output
        doc: Placeholder doc-string for the output
        type: long
      float_output:
        label: Placeholder label for the output
        doc: Placeholder doc-string for the output
        type: float
      double_output:
        label: Placeholder label for the output
        doc: Placeholder doc-string for the output
        type: double
      string_output:
        label: Placeholder label for the output
        doc: Placeholder doc-string for the output
        type: string
      enum_output:
        label: Placeholder label for the output
        doc: Placeholder doc-string for the output
        type:
          type: enum
          symbols:
            - option 1
            - option 2
      file_output:
        label: Placeholder label for the output
        doc: Placeholder doc-string for the output
        type: File
      directory_output:
        label: Placeholder label for the output
        doc: Placeholder doc-string for the output
        type: Directory
      optional_int_output:
        label: Placeholder label for the output
        doc: Placeholder doc-string for the output
        type: int?
      array_enum_output:
        label: Placeholder label for the output
        doc: Placeholder doc-string for the output
        type:
          type: array
          items:
            type: enum
            symbols:
              - option 1
              - option 2
    steps:
      step_1:
        run: '#argument_sink'
        in:
          nonsense: string_input
        out:
          - nonsense_out
  - class: CommandLineTool
    label: Argument sink
    id: '#argument_sink'
    baseCommand:
      - stat
      - /bin/stat
    inputs:
      nonsense:
        type: string
    outputs:
      nonsense_out:
        type: int
        outputBinding:
          outputEval: $(runtime.exitCode)
    requirements:
      DockerRequirement:
        dockerPull: 'alpine:latest'
