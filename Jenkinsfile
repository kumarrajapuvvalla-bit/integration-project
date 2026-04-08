pipeline {
    agent any

    environment {
        // ── Identity ─────────────────────────────────────────────
        APP_NAME            = 'flight-ingest'
        IMAGE_REPO          = "ghcr.io/kumarrajapuvvalla-bit/${APP_NAME}"
        IMAGE_TAG           = "${env.GIT_COMMIT?.take(8) ?: 'dev'}"
        HELM_RELEASE        = "${APP_NAME}-${env.BRANCH_NAME?.replaceAll('/', '-') ?: 'main'}"
        HELM_NAMESPACE      = 'integrations'

        // ── Credentials (stored in Jenkins) ──────────────────────
        SONARQUBE_SERVER    = 'SonarQubeServer'
        SONAR_PROJECT_KEY   = 'integration-project'
        SLACK_WEBHOOK_URL   = credentials('slack-webhook-url')
        GHCR_TOKEN          = credentials('ghcr-token')
        KUBECONFIG_CRED     = credentials('kubeconfig-staging')
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 45, unit: 'MINUTES')
        disableConcurrentBuilds()
        ansiColor('xterm')
    }

    stages {
        // ── Stage 1: Checkout ─────────────────────────────────────
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_COMMIT_MSG = sh(script: 'git log -1 --pretty=%B', returnStdout: true).trim()
                    env.GIT_AUTHOR    = sh(script: 'git log -1 --pretty=%an', returnStdout: true).trim()
                }
                echo "\u2705 Checked out: ${env.GIT_COMMIT} by ${env.GIT_AUTHOR}"
            }
        }

        // ── Stage 2: Parallel Lint ────────────────────────────────
        stage('Lint') {
            parallel {
                stage('Python lint') {
                    steps {
                        dir('services/flight-ingest') {
                            sh '''
                                pip install --quiet ruff bandit
                                ruff check . --select E,F,W --ignore E501
                                bandit -r app/ -ll -q
                            '''
                        }
                    }
                }
                stage('Rust lint') {
                    steps {
                        dir('tools/log-parser') {
                            sh 'cargo fmt --check && cargo clippy -- -D warnings'
                        }
                    }
                }
                stage('Helm lint') {
                    steps {
                        dir('helm/flight-ingest') {
                            sh 'helm lint .'
                        }
                    }
                }
            }
        }

        // ── Stage 3: Parallel Build ───────────────────────────────
        stage('Build') {
            parallel {
                stage('Python build') {
                    steps {
                        dir('services/flight-ingest') {
                            sh '''
                                pip install --quiet -r requirements.txt
                                python -m compileall app/
                            '''
                        }
                    }
                }
                stage('Rust build') {
                    steps {
                        dir('tools/log-parser') {
                            sh 'cargo build --release'
                        }
                    }
                }
            }
        }

        // ── Stage 4: Parallel Test ────────────────────────────────
        stage('Test') {
            parallel {
                stage('Python unit tests') {
                    steps {
                        dir('services/flight-ingest') {
                            sh '''
                                pip install --quiet pytest pytest-cov httpx
                                pytest tests/unit/ -v --tb=short \
                                    --cov=app --cov-report=xml:coverage.xml \
                                    --junitxml=test-results.xml
                            '''
                        }
                    }
                    post {
                        always {
                            junit 'services/flight-ingest/test-results.xml'
                            cobertura coberturaReportFile: 'services/flight-ingest/coverage.xml'
                        }
                    }
                }
                stage('Rust tests') {
                    steps {
                        dir('tools/log-parser') {
                            sh 'cargo test --all -- --nocapture'
                        }
                    }
                }
            }
        }

        // ── Stage 5: SonarQube Analysis ───────────────────────────
        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv(SONARQUBE_SERVER) {
                    sh """
                        sonar-scanner \
                            -Dsonar.projectKey=${SONAR_PROJECT_KEY} \
                            -Dsonar.sources=services/flight-ingest/app,tools/log-parser/src \
                            -Dsonar.python.coverage.reportPaths=services/flight-ingest/coverage.xml \
                            -Dsonar.exclusions=**/tests/**,**/__pycache__/**
                    """
                }
            }
        }

        // ── Stage 6: Quality Gate ─────────────────────────────────
        stage('Quality Gate') {
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        // ── Stage 7: Security Scanning ────────────────────────────
        stage('Security Scan') {
            parallel {
                stage('OWASP Dependency Check') {
                    steps {
                        dir('services/flight-ingest') {
                            sh '''
                                pip install --quiet safety
                                safety check -r requirements.txt --json > safety-report.json || true
                                cat safety-report.json
                            '''
                        }
                    }
                }
                stage('Trivy FS Scan') {
                    steps {
                        sh '''
                            ./scripts/trivy-scan.sh fs . \
                                --exit-code 1 \
                                --severity HIGH,CRITICAL \
                                --format table
                        '''
                    }
                }
                stage('Cargo Audit') {
                    steps {
                        dir('tools/log-parser') {
                            sh 'cargo audit'
                        }
                    }
                }
            }
        }

        // ── Stage 8: Docker Build & Push ──────────────────────────
        stage('Docker') {
            when {
                anyOf {
                    branch 'main'
                    branch 'release/*'
                    tag '*'
                }
            }
            steps {
                script {
                    sh "echo ${GHCR_TOKEN} | docker login ghcr.io -u kumarrajapuvvalla-bit --password-stdin"
                    sh """
                        docker build \
                            --build-arg GIT_COMMIT=${env.GIT_COMMIT} \
                            --build-arg BUILD_DATE=\$(date -u +%Y-%m-%dT%H:%M:%SZ) \
                            -t ${IMAGE_REPO}:${IMAGE_TAG} \
                            -t ${IMAGE_REPO}:latest \
                            -f services/flight-ingest/Dockerfile \
                            services/flight-ingest/
                    """
                    sh "docker push ${IMAGE_REPO}:${IMAGE_TAG}"
                    sh "docker push ${IMAGE_REPO}:latest"

                    // Trivy image scan after push
                    sh """
                        ./scripts/trivy-scan.sh image ${IMAGE_REPO}:${IMAGE_TAG} \
                            --exit-code 1 \
                            --severity CRITICAL
                    """
                }
            }
        }

        // ── Stage 9: Helm Deploy (staging) ────────────────────────
        stage('Deploy → Staging') {
            when { branch 'main' }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-staging', variable: 'KUBECONFIG')]) {
                    sh """
                        helm upgrade --install ${HELM_RELEASE} helm/flight-ingest \
                            --namespace ${HELM_NAMESPACE} \
                            --create-namespace \
                            --set image.repository=${IMAGE_REPO} \
                            --set image.tag=${IMAGE_TAG} \
                            --set replicaCount=2 \
                            --wait --timeout 5m
                    """
                    sh "./scripts/health-check.sh ${APP_NAME} ${HELM_NAMESPACE}"
                }
            }
        }

        // ── Stage 10: Deploy → Production (manual gate) ───────────
        stage('Deploy → Production') {
            when { tag '*' }
            input {
                message "Deploy ${IMAGE_TAG} to Production?"
                ok 'Yes, deploy'
                submitter 'ops-team,senior-engineers'
            }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-prod', variable: 'KUBECONFIG')]) {
                    sh """
                        helm upgrade --install ${APP_NAME} helm/flight-ingest \
                            --namespace ${HELM_NAMESPACE}-prod \
                            --create-namespace \
                            --set image.repository=${IMAGE_REPO} \
                            --set image.tag=${IMAGE_TAG} \
                            --set replicaCount=3 \
                            --set resources.requests.memory=256Mi \
                            --set resources.limits.memory=512Mi \
                            --wait --timeout 10m
                    """
                    sh "./scripts/health-check.sh ${APP_NAME} ${HELM_NAMESPACE}-prod"
                }
            }
        }
    }

    post {
        success {
            script {
                def msg = ":white_check_mark: *${env.JOB_NAME} #${env.BUILD_NUMBER}* passed\n" +
                          "> Branch: `${env.BRANCH_NAME}` | Commit: `${env.GIT_COMMIT?.take(8)}`\n" +
                          "> Author: ${env.GIT_AUTHOR}\n" +
                          "> <${env.BUILD_URL}|View Build>"
                sh "./scripts/slack_notify.sh '${msg}' '${SLACK_WEBHOOK_URL}'"
            }
        }
        failure {
            script {
                def msg = ":x: *${env.JOB_NAME} #${env.BUILD_NUMBER}* FAILED\n" +
                          "> Branch: `${env.BRANCH_NAME}` | Commit: `${env.GIT_COMMIT?.take(8)}`\n" +
                          "> Author: ${env.GIT_AUTHOR}\n" +
                          "> <${env.BUILD_URL}|View Build>"
                sh "./scripts/slack_notify.sh '${msg}' '${SLACK_WEBHOOK_URL}'"
            }
        }
        always {
            cleanWs()
        }
    }
}
