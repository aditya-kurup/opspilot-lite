pipeline {
  agent any
  parameters { string(name: 'REQUEST_ID', description: 'Approved request id') }
  stages {
    stage('Verify') { steps { sh 'python -m pytest -q' } }
    stage('Provision') { steps { sh 'python -m app.jenkins_worker --request-id \"$REQUEST_ID\"' } }
  }
}
