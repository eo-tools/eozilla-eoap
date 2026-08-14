$graph:
- class: Workflow
  cwlVersion: v1.2
  label: Compute Prime Numbers within a User-Specified range
  doc: The primes EOAP is a simple process that calculates prime numbers between a lower and an upper bound. By registering the accompanying CWL workflow, the process will be available at `/processes/primes-workflow`.
  id: primes-workflow
  inputs:
    maximum:
      label: Upper bound of range for which to calculate primes
      doc: Some longer explanation of the argument, possibly listing restrictions, assumptions, etc.
      type: int
      default: 100
    minimum:
      label: Upper bound of range for which to calculate primes
      doc: Some longer explanation of the argument, possibly listing restrictions, assumptions, etc.
      type: int
      default: 0
  outputs:
    primes:
      outputSource: primes_node/primes_out
      type:
        items: int
        type: array
  steps:
    primes_node:
      in:
        maximum: maximum
        minimum: minimum
      out:
      - primes_out
      run: '#primes-tool'
- class: CommandLineTool
  label: Sleep Tool
  id: '#primes-tool'
  baseCommand: ['python', '/primes.py']
  inputs:
    maximum:
      inputBinding:
        position: 1
      type: int
    minimum:
      inputBinding:
        position: 0
      type: int
  outputs:
    primes_out:
      outputBinding:
        glob: primes.txt
        loadContents: true
        outputEval: $(JSON.parse(self[0].contents))
      type:
        items: int
        type: array
  requirements:
    DockerRequirement:
      dockerPull: floriankaterndahl/primes-eoap:0.0.1
    InlineJavascriptRequirement: {}
  stdout: primes.txt
$namespaces:
  s: https://schema.org/
cwlVersion: v1.2
s:version: 0.0.2
s:keywords:
- Prime Numbers
- Python
- Sieve of Eratosthenes
