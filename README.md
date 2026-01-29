# Automated AI Code Reviewer (py-webhook-svc)

A robust, cloud-native GitHub App backend designed to automate code reviews using advanced AI Agents and LLMs. This service listens to GitHub Pull Request events, triggers AI-powered analysis, and feeds the results back directly into the PR conversation.

## 🚀 Key Features

*   **Automated AI Code Review**: Automatically triggers a code review process upon PR creation (`pull_request.opened`).
*   **GitOps Integrated**: Seamlessly integrates into the developer's Git workflow.
*   **Advanced AI Agent Integration**:
    *   Utilizes **Gemini LLM** and **WebAgent** technologies for deep code analysis.
    *   Capable of invoking multi-layer agent routing for context-aware reviews.
*   **Enterprise-Grade Extensions**:
    *   Integrates with **Jira** and **Confluence** (via MCP Tools) to check code against internal coding standards and business requirements.
    *   Beyond "Common Sense" AI: Validates logic against specific enterprise documentation.
*   **High Performance**: Built with **FastAPI** and **AsyncIO** for high-concurrency event processing.
*   **Cloud Native**: Fully containerized and optimized for **Google Kubernetes Engine (GKE)**.

## 📂 Project Structure

```
py-webhook-svc/
├── server.py                # Entry point: FastAPI app & Webhook routing logic
├── src/
│   ├── main.py              # Application factory (if applicable)
│   ├── configs/             # Configuration management (YAML + Env vars)
│   └── services/
│       ├── gh_service.py    # GitHub API interactions (Gidgethub, JWT Auth)
│       └── code_review_service.py # Orchestrator for calling external AI Agents
├── py-webhook-svc-chart/    # Helm Chart for Kubernetes deployment
├── cloudbuild-helm.yaml     # Google Cloud Build CI/CD configuration
├── Dockerfile               # Container definition
├── k8s/                     # Raw Kubernetes manifests (Gateway, ConfigMaps)
└── docs/                    # Detailed guides and documentation
```

## 🛠️ Architecture

1.  **Event Ingestion**: GitHub sends a `pull_request` webhook event to the service running on GKE.
2.  **Authentication**: The service authenticates as a GitHub App using a Private Key to obtain an Installation Access Token.
3.  **Orchestration**:
    *   `server.py` receives the event and posts a "Welcome" comment immediately.
    *   It then asynchronously triggers `CodeReviewService`.
4.  **AI Analysis**:
    *   `CodeReviewService` sends the PR details to an external **AI Review Agent**.
    *   The Agent (powered by Gemini/LangChain) retrieves code changes, analyzes them, and generates a report.
5.  **Feedback**: The analysis report is posted back to the GitHub PR as a comment.

## ☁️ Deployment

This project uses a fully automated **CI/CD pipeline** based on **Google Cloud Build** and **Helm**.

### Prerequisites

*   Google Cloud Platform (GCP) Project
*   GKE Cluster (Standard or Autopilot)
*   Artifact Registry (Docker)
*   GitHub App configured with:
    *   Webhook URL pointing to this service.
    *   Permissions: `Pull requests` (Read & Write).
    *   Secret Key.

### CI/CD Pipeline (`cloudbuild-helm.yaml`)

The pipeline performs the following steps automatically on every push to the main branch:

1.  **Calculate New Tag**: Automatically increments the semantic version (patch level) based on existing tags in Artifact Registry.
2.  **Build Image**: Builds the Docker image.
3.  **Push Image**: Pushes the image to Google Artifact Registry (GAR).
4.  **Deploy to GKE**: Uses **Helm** to upgrade the release on the GKE cluster with the new image tag.

### Manual Deployment (Helm)

You can also deploy manually using Helm:

```bash
# Configure local kubectl context
gcloud container clusters get-credentials CLUSTER_NAME --region REGION

# Install/Upgrade Chart
helm upgrade --install py-webhook-svc ./py-webhook-svc-chart \
  --set image.tag=latest \
  --namespace default
```

## ⚙️ Configuration

The service requires the following environment variables (configured via `py-webhook-svc-chart/values.yaml` or Kubernetes Secrets):

| Variable | Description |
| :--- | :--- |
| `GITHUB_APP_ID` | The ID of your GitHub App. |
| `GITHUB_WEBHOOK_SECRET` | Secret key for verifying Webhook signatures. |
| `GITHUB_PRIVATE_KEY_PATH` | Path to the mounted Private Key file. |
| `GITHUB_API_BASE_URL` | (Optional) For GitHub Enterprise, e.g., `https://github.company.com/api/v3`. |

## 📚 Documentation

Detailed guides can be found in the `docs/` directory:

*   [From Zero to GitHub App](docs/FROM_ZERO_TO_GITHUB_APP.md): Complete tutorial on building this app.
*   [GKE Helm Deployment](docs/GKE_HELM_DEPLOYMENT_GUIDE.md): Deployment specifics.
*   [GitHub Webhook Guide](docs/GITHUB_WEBHOOK_GUIDE.md): Understanding the webhook mechanism.
