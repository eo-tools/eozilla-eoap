$graph:
- class: Workflow
  cwlVersion: v1.2
  label: Sleep for a User-Specified Duration
  doc: The sleep EOAP is a simple process that calls a Python function that sleeps for a given amount of time. By registering the accompanying CWL workflow, the process will be available at `/processes/sleep-workflow`.
  id: sleep-workflow
  inputs:
    duration:
      label: Seconds to sleep
      doc: The `duration` argument specifies, in number of seconds, the duration to sleep. Fractional seconds are permitted.
      type: float
      default: 10.0
    fail:
      label: Fail on purpose
      doc: When specified, the process will fail after half the sleep duration has passed.
      type:
        type: enum
        symbols:
          - "true"
          - "false"
      default: "false"
  outputs:
    sleep:
      outputSource: sleep_node/sleep_out
      type: float
  steps:
    sleep_node:
      in:
        duration: duration
        fail: fail
      out:
      - sleep_out
      run: '#sleep-tool'
- class: CommandLineTool
  label: Sleep Tool
  id: '#sleep-tool'
  baseCommand: ['python', '/sleep.py']
  inputs:
    duration:
      inputBinding:
        position: 1
      type: float
    fail:
      inputBinding:
        position: 2
      type:
        type: enum
        symbols:
          - "true"
          - "false"
  outputs:
    sleep_out:
      outputBinding:
        glob: sleep.txt
        loadContents: true
        outputEval: $(parseFloat(self[0].contents.trim()))
      type: float
  requirements:
    DockerRequirement:
      dockerPull: quay.io/bcdev/sleep-eoap:0.0.2
    InlineJavascriptRequirement: {}
  stdout: sleep.txt
$namespaces:
  s: https://schema.org/
cwlVersion: v1.2
s:version: 0.0.2
