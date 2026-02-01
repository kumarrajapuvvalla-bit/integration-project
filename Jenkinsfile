pipeline {
    agent any
    environment {
        SONARQUBE_SERVER = 'SonarQubeServer'
        SONAR_PROJECT_KEY = 'integration-project'
        SLACK_WEBHOOK_URL = credentials('slack-webhook-url')
    }
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        stage('Build') {
            steps {
                sh 'echo Building the project...'
                // Insert your build commands here
            }
        }
        stage('Test') {
            steps {
                sh 'echo Running tests...'
                // Insert test commands
            }
        }
        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv(SONARQUBE_SERVER) {
                    sh "sonar-scanner -Dsonar.projectKey=${SONAR_PROJECT_KEY}"
                }
            }
        }
        stage('Quality Gate') {
            steps {
                timeout(time: 1, unit: 'HOURS') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }
    }
    post {
        success {
            script {
                sh "./scripts/slack_notify.sh \"Build successful: ${env.JOB_NAME} #${env.BUILD_NUMBER}\" ${SLACK_WEBHOOK_URL}"
            }
        }
        failure {
            script {
                sh "./scripts/slack_notify.sh \"Build failed: ${env.JOB_NAME} #${env.BUILD_NUMBER}\" ${SLACK_WEBHOOK_URL}"
            }
        }
    }
}
