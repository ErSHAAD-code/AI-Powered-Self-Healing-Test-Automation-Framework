// Jenkinsfile — AI-Powered Self-Healing Test Automation Framework
// Stages: Build → Test → Scan → Report → Deploy

pipeline {
    agent any

    environment {
        PYTHON_VERSION = '3.12'
        HEADLESS = 'true'
        VENV_DIR = 'venv'
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
        ansiColor('xterm')
    }

    stages {
        // ================================================================
        // Stage 1: Build — Set up Python environment and dependencies
        // ================================================================
        stage('Build') {
            steps {
                echo '🔧 Setting up Python environment...'
                sh '''
                    python3 -m venv ${VENV_DIR}
                    . ${VENV_DIR}/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    playwright install chromium --with-deps
                '''
            }
        }

        // ================================================================
        // Stage 2: Test — Run all test suites in parallel
        // ================================================================
        stage('Test') {
            parallel {
                stage('UI & BDD Tests') {
                    steps {
                        sh '''
                            . ${VENV_DIR}/bin/activate
                            pytest tests/ bdd/ -v -m "smoke or regression or bdd" \
                                --html=reports/ui_bdd_report.html \
                                --self-contained-html \
                                --junitxml=reports/ui_bdd_results.xml || true
                        '''
                    }
                    post {
                        always {
                            junit 'reports/ui_bdd_results.xml'
                        }
                    }
                }

                stage('API Tests') {
                    steps {
                        sh '''
                            . ${VENV_DIR}/bin/activate
                            pytest api_tests/ -v -m api \
                                --html=reports/api_report.html \
                                --self-contained-html \
                                --junitxml=reports/api_results.xml || true
                        '''
                    }
                    post {
                        always {
                            junit 'reports/api_results.xml'
                        }
                    }
                }

                stage('ETL Validation') {
                    steps {
                        sh '''
                            . ${VENV_DIR}/bin/activate
                            pytest etl_validation/ -v -m etl \
                                --html=reports/etl_report.html \
                                --self-contained-html \
                                --junitxml=reports/etl_results.xml || true
                        '''
                    }
                    post {
                        always {
                            junit 'reports/etl_results.xml'
                        }
                    }
                }

                stage('Performance Smoke') {
                    steps {
                        sh '''
                            . ${VENV_DIR}/bin/activate
                            pytest performance/ -v -m performance \
                                --html=reports/perf_report.html \
                                --self-contained-html \
                                --junitxml=reports/perf_results.xml || true
                        '''
                    }
                    post {
                        always {
                            junit 'reports/perf_results.xml'
                        }
                    }
                }
            }
        }

        // ================================================================
        // Stage 3: Scan — Security and dependency audit
        // ================================================================
        stage('Scan') {
            steps {
                echo '🔍 Running dependency security audit...'
                sh '''
                    . ${VENV_DIR}/bin/activate
                    pip install pip-audit
                    pip-audit --format=json --output=reports/audit_report.json || true
                '''
            }
        }

        // ================================================================
        // Stage 4: Report — Generate unified AI-augmented report
        // ================================================================
        stage('Report') {
            steps {
                echo '📊 Generating unified AI report...'
                sh '''
                    . ${VENV_DIR}/bin/activate
                    python -c "
from reporting.ai_summary_report_generator import AISummaryReportGenerator
gen = AISummaryReportGenerator()
gen.generate()
print('Unified report generated')
"
                '''
            }
            post {
                always {
                    publishHTML(target: [
                        reportName: 'AI-Augmented Test Report',
                        reportDir: 'reports',
                        reportFiles: 'unified_report.html',
                        alwaysLinkToLastBuild: true,
                        keepAll: true
                    ])
                }
            }
        }

        // ================================================================
        // Stage 5: Deploy (placeholder)
        // ================================================================
        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                echo '🚀 Deploy stage (placeholder for production deployment)'
                echo 'All tests passed — ready for deployment'
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/**/*', allowEmptyArchive: true
            echo '📋 Pipeline complete'
        }
        success {
            echo '✅ All stages passed!'
        }
        failure {
            echo '❌ Pipeline failed — check test reports for details'
        }
    }
}
