$graph:
- class: Workflow
  cwlVersion: v1.2
  label: Cat User Input from File to stdout
  doc: The cat EOAP is a simple process that cat the contents of a user-supplied file to stdout . By registering the accompanying CWL workflow, the process will be available at `/processes/cat-workflow`.
  id: cat-workflow
  inputs:
    file:
      label: File to cat
      doc: some very length description of what this argument does
      type: File
  outputs:
    cat_out:
      outputSource: cat/cat_out
      type:
        type: array
        items: string
  steps:
    cat:
      in:
        file: file
      out:
      - cat_out
      run: '#cat-tool'
- baseCommand:
  - cat
  class: CommandLineTool
  id: '#cat-tool'
  inputs:
    file:
      inputBinding:
        position: 1
      type: File
  label: Cat Tool
  outputs:
    cat_out:
      outputBinding:
        glob: cat.txt
        loadContents: true
        outputEval: $(self[0].contents.split('\n'))
      type:
        type: array
        items: string
  requirements:
    DockerRequirement:
      dockerPull: alpine:3.22
    InlineJavascriptRequirement: {}
  stdout: cat.txt
$namespaces:
  s: https://schema.org/
cwlVersion: v1.2
s:version: 0.0.1
