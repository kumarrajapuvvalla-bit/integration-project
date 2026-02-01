# Integration Pipeline Demo

This project demonstrates how to integrate multiple DevOps tools within
a single **Jenkins** pipeline.  It includes:

* **SonarQube analysis** to assess code quality and enforce
  standards via a quality gate.
* **Slack notifications** to keep the team informed of build
  successes or failures.
* A skeleton build/test stage that you can adapt for your own
  application.

By combining static analysis and collaboration tools, the pipeline
exemplifies best practices in modern continuous delivery workflows.

## Jenkins Pipeline

The `Jenkinsfile` defines a declarative pipeline with the following
stages:

1. **Checkout** – retrieves the source code from the Git repository.
2. **Build** – placeholder for compiling or packaging your
   application.
3. **Test** – placeholder for executing unit or integration tests.
4. **SonarQube Analysis** – runs `sonar-scanner` within the context of
   a configured SonarQube server.  The project key is supplied via
   environment variables.
5. **Quality Gate** – waits for the SonarQube quality gate result
   (success, warning, or failed) and aborts the pipeline if it fails.

After the pipeline completes, notifications are sent via Slack using a
simple shell script.  The script takes the message and the webhook
URL as arguments and posts a JSON payload to Slack.  Slack webhook
URLs should be stored securely in Jenkins as credentials.

### Prerequisites

To run this pipeline you will need:

* A **Jenkins instance** with the following plugins installed:
  * Pipeline
  * Slack Notification
  * SonarQube Scanner for Jenkins
* A **SonarQube server** reachable from Jenkins.  Define a server in
  Jenkins configuration and set the name in the `SONARQUBE_SERVER`
  environment variable.
* A **Slack Incoming Webhook** configured in your workspace.  Store
  the webhook URL as a secret text credential in Jenkins (for example,
  `slack-webhook-url`).
* The `sonar-scanner` CLI installed on your Jenkins agents or use the
  built‑in scanner provided by the SonarQube plugin.

### slack_notify.sh

The script `scripts/slack_notify.sh` sends a message to Slack.  It
requires two parameters: the message text and the webhook URL.  The
pipeline calls this script in the `post` section for both success and
failure cases.

Make sure the script is executable:

```bash
chmod +x scripts/slack_notify.sh
```

### SonarQube Configuration

The `sonar-project.properties` file is provided as a starting point.
Replace `YOUR_TOKEN` with a valid user token or configure
authentication via the Jenkins plugin.  You can also set
`sonar.host.url` to point at your SonarQube instance.

### Extending This Project

This integration pipeline can be extended in many ways:

* Add more stages such as **security scanning** (for example,
  dependency‑check or Trivy) to detect vulnerabilities.
* Send notifications to other channels (Microsoft Teams, email) or
  integrate with ticketing systems (Jira, ServiceNow).
* Use **GitHub Actions** or **GitLab CI** to implement a similar
  workflow outside Jenkins.
* Parameterise the pipeline to support multiple environments and
  promote builds from staging to production.

By implementing these integrations you demonstrate your ability to
automate quality gates and improve collaboration across teams.
