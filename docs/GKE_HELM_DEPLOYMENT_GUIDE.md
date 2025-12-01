# GKE 部署指南：从 `kubectl` 到 Helm Chart 的演进

本文档旨在通过 `py-webhook-svc` 项目的实际案例，详细介绍在 Google Kubernetes Engine (GKE) 上进行部署的两种主要方法：传统的 `kubectl` 部署和现代的 Helm Chart 部署。我们将对比这两种方法的优劣，并深入讲解最终完善的 Helm Chart 配置。

## 1. 两种部署方式的对比

### 1.1. 传统方式：`kubectl` + 脚本

在项目初期，我们使用了 `cloudbuild-gke.yaml`，它代表了传统的 `kubectl` 部署方式。

**核心思想**:
维护一组静态的 Kubernetes YAML 文件（如 `k8s/deployment.yaml`），在 CI/CD 流水线中通过脚本（如 `sed`）动态地修改这些文件中的特定值（如镜像标签），然后使用 `kubectl apply -f` 将它们应用到集群。

**示例 (`cloudbuild-gke.yaml` 的一个步骤):**
```yaml
- id: "Deploy to GKE"
  name: "gcr.io/cloud-builders/gcloud"
  entrypoint: "bash"
  args:
    - "-c"
    - |
      set -x
      # 动态修改 deployment.yaml 中的镜像标签
      sed -i "s|image:.*|image: ...:$$NEW_TAG|g" k8s/deployment.yaml
      # 应用所有静态 YAML 文件
      kubectl apply -f k8s/
```

**优点**:
*   **直观**: 对于初学者来说，直接编写和应用 YAML 文件非常容易理解。
*   **简单**: 对于小型项目，这种方法足够快速和有效。

**缺点**:
*   **脆弱**: 强依赖于 `sed` 等脚本，如果 YAML 的格式或缩进发生变化，脚本可能会失败。
*   **难以管理**: 缺乏版本控制、回滚和依赖管理。所有配置都散落在各个 YAML 文件中。
*   **重复性高**: 不同的环境（开发、生产）需要复制和维护多套几乎相同的 YAML 文件。

### 1.2. 现代方式：Helm Chart

经过我们的重构，我们采用了 `cloudbuild-helm.yaml`，它代表了现代的 Helm Chart 部署方式。

**核心思想**:
将 Kubernetes 的配置**模板化**。配置的**结构**（如 `deployment.yaml` 中的字段）和**值**（如副本数量、镜像标签）分离开来。`values.yaml` 文件定义了所有可配置的值，而 `helm` 命令在部署时将这些值动态地渲染到模板中，生成最终的 Kubernetes 清单。

**示例 (`cloudbuild-helm.yaml` 的一个步骤):**
```yaml
- id: "Deploy to GKE"
  name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
  entrypoint: "bash"
  args:
    - "-c"
    - |
      set -ex
      # 下载并解压 Helm
      HELM_VERSION=v3.15.2
      curl -sSL https://get.helm.sh/helm-$${HELM_VERSION}-linux-amd64.tar.gz -o helm.tar.gz
      tar -zxvf helm.tar.gz

      # 通过 --set 参数在运行时覆盖 values.yaml 中的值
      ./linux-amd64/helm upgrade --install py-webhook-svc ./py-webhook-svc-chart \
        --set image.tag=$$NEW_TAG \
        --namespace default
```

**优点**:
*   **高度可重用 (最重要的优点)**: 您可以将 Kubernetes 的配置（`templates`）视为一个可以重复使用的**函数或类**。通过为同一个 Chart 提供不同的 `values.yaml` 文件（**输入参数**），您可以轻松地部署无数个不同的服务或环境，而无需复制和粘贴任何 YAML 代码。这极大地提高了效率和一致性。
*   **可配置**: 所有的变量都集中在 `values.yaml` 中，清晰明了。
*   **版本化与回滚**: Helm 将每次部署作为一个 "Release"，可以轻松地查看历史版本并一键回滚到任何一个旧版本。
*   **依赖管理**: Helm 可以管理 Chart 之间的依赖关系（例如，您的应用依赖于一个数据库 Chart）。

**缺点**:
*   **学习曲线**: Helm 的模板语法和概念（如 `include`, `define`, 内置对象等）需要一定的学习成本。

## 2. Helm Chart 基本使用步骤

如果您是第一次接触 Helm，以下是在本地环境中使用它的基本步骤。

### 2.1. 安装 Helm

Helm 是一个单一的二进制文件，安装非常简单。

**在 macOS (使用 Homebrew):**
```bash
brew install helm
```

**在 Linux:**
```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh
```

**在 Windows (使用 Chocolatey):**
```bash
choco install kubernetes-helm
```

安装完成后，运行 `helm version` 来确认安装成功。

### 2.2. 常用 Helm 命令

*   **`helm lint ./[chart-目录]`**:
    *   检查您的 Chart 是否有语法错误或不符合最佳实践。这是在部署前非常有用的一个命令。
    *   示例: `helm lint ./py-webhook-svc-chart`

*   **`helm install [release-名称] ./[chart-目录]`**:
    *   在 Kubernetes 集群中安装一个新的 Chart。一个 "Release" 是 Chart 的一个部署实例。
    *   示例: `helm install my-app ./py-webhook-svc-chart`

*   **`helm upgrade [release-名称] ./[chart-目录]`**:
    *   升级一个已存在的 Release。
    *   示例: `helm upgrade my-app ./py-webhook-svc-chart`

*   **`helm upgrade --install [release-名称] ./[chart-目录]`**:
    *   这是一个非常有用的组合命令：如果名为 `[release-名称]` 的 Release 已经存在，就升级它；如果不存在，就安装它。我们的 Cloud Build 流水线使用的就是这个命令。

*   **`helm list`**:
    *   列出所有已部署的 Release。

*   **`helm uninstall [release-名称]`**:
    *   从集群中卸载一个 Release，并删除由它创建的所有资源。
    *   示例: `helm uninstall my-app`

*   **`helm template ./[chart-目录]`**:
    *   在**本地**渲染模板，并将生成的 YAML 清单打印到控制台，而**不**实际部署到集群。这对于在部署前调试和检查最终的配置非常有用。
    *   示例: `helm template ./py-webhook-svc-chart`

## 3. `py-webhook-svc` 项目的最终 Helm 配置解析

经过我们漫长而严谨的排错和重构，最终的 Helm Chart 配置体现了高度的灵活性、一致性和最佳实践。

### 3.1. `values.yaml` - 配置中心

这是我们所有可配置参数的“控制面板”。

```yaml
# ...
image:
  repository: europe-west2-docker.pkg.dev/jason-hsbc/my-docker-repo/py-webhook-svc
  pullPolicy: IfNotPresent
  tag: "0.0.38" # 这个值总会被 Cloud Build 的 --set 参数覆盖

sidecar:
  image: "europe-west2-docker.pkg.dev/jason-hsbc/my-docker-repo/fluentd-bigquery:1.0.1"
  pullPolicy: Always

# ...

service:
  appName: py-webhook-svc # 关键参数，用于统一 Service 和 Pod 的 app 标签
  name: clusterip-py-webhook-svc # 关键参数，用于匹配现有的 HTTPRoute
  type: ClusterIP
  port: 8000

# ...

livenessProbe:
  httpGet:
    path: /webhook/ # 关键修复，匹配 FastAPI 的 root_path
    port: http
readinessProbe:
  httpGet:
    path: /webhook/ # 关键修复，确保 Pod 能被正确标记为 Ready
    port: http
```

**关键设计**:
*   **`service.appName`**: 我们提炼出了这个核心参数，用于驱动所有资源的 `app` 标签，确保了 `Service` 的 `selector` 和 `Deployment` 的 `template.metadata.labels` 永远保持一致。
*   **`service.name`**: 我们通过这个参数，让 Helm 创建的 `Service` 能够精确地匹配 `HTTPRoute` 所需的后端服务名称，而无需修改现有的网络配置。
*   **探针路径**: 我们修正了健康检查的路径，这是确保滚动更新成功和流量被正确路由的关键。

### 3.2. `deployment.yaml` - 应用部署模板

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-{{ .Chart.Name }}
  labels:
    app: {{ .Values.service.appName }} # 使用 values.yaml 中的值
    # ... 其他标准 Helm 标签
spec:
  # ...
  selector:
    matchLabels:
      app: {{ .Values.service.appName }} # 确保 selector 与 Pod 标签匹配
      app.kubernetes.io/instance: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app: {{ .Values.service.appName }} # 确保 Pod 标签正确
        app.kubernetes.io/instance: {{ .Release.Name }}
    spec:
      # Pod 默认使用其所在节点的 GSA，因为我们没有配置 Workload Identity
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          # ...
        - name: sidecar-fluentd
          image: "{{ .Values.sidecar.image }}" # 使用简化的 sidecar 镜像参数
          # ...
```

**关键设计**:
*   **参数化的标签和选择器**: 所有的 `app` 标签都指向了 `.Values.service.appName`，彻底解决了我们遇到的核心问题。
*   **简化的 Sidecar 配置**: 我们将 `sidecar` 的镜像配置合并为一个参数，使 `values.yaml` 更简洁。
*   **移除 `serviceAccountName`**: 我们最终确认 Pod 继承节点的 GSA，因此移除了不必要的 KSA 配置，使部署更简洁。

### 3.3. `service.yaml` - 服务暴露模板

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.service.name }} # 使用 values.yaml 中的值来匹配 HTTPRoute
  labels:
    app: {{ .Values.service.appName }} # 确保标签与 selector 一致
    # ...
spec:
  # ...
  selector:
    app: {{ .Values.service.appName }} # 确保 selector 与 Pod 标签一致
    app.kubernetes.io/instance: {{ .Release.Name }}
```

**关键设计**:
*   **参数化的名称**: `Service` 的名称由 `.Values.service.name` 控制，使其能够与外部依赖（如 `HTTPRoute`）解耦。
*   **一致的选择器**: `selector` 与 `deployment.yaml` 中的 Pod 标签完全一致，保证了 `Service` 能够正确地发现和路由流量到我们的应用 Pod。

## 4. 如何重用此 Helm Chart

**这是 Helm 相比传统 `kubectl` 方式最强大的优势所在。** 我们的 `py-webhook-svc-chart` 现在是一个标准化的、可重用的部署模板。您可以用它来部署任意数量的新 Web 服务，而唯一需要做的就是为每个新服务提供一个不同的 `values.yaml` 文件。

假设您有一个新的服务，名为 `my-new-app`。

1.  **复制并重命名 `values.yaml`**:
    *   在您的代码库中，将 `py-webhook-svc-chart/values.yaml` 复制一份，命名为 `my-new-app-values.yaml`（或者放在一个专门的配置目录中）。

2.  **修改 `my-new-app-values.yaml`**:
    *   **`image.repository`**: 将其值更改为新应用的 Docker 镜像仓库地址。
    *   **`service.appName`**: 将其值更改为 `my-new-app`。这将自动更新所有资源的 `app` 标签和 `ConfigMap` 的名称。
    *   **`service.name`**: 将其值更改为 `HTTPRoute` 为这个新应用配置的 `Service` 名称（例如 `clusterip-my-new-app-svc`）。
    *   **`sidecar.image`**: 如果新应用有不同的 sidecar，请更新此值。
    *   **`livenessProbe` / `readinessProbe`**: 根据新应用的健康检查端点更新 `path`。
    *   根据需要调整 `replicaCount`, `resources` 等其他参数。

3.  **部署新应用**:
    *   在您的 CI/CD 流水线中（例如，一个新的 Cloud Build 文件），使用以下命令来部署新应用：
        ```bash
        helm upgrade --install my-new-app ./py-webhook-svc-chart \
          -f path/to/my-new-app-values.yaml \
          --set image.tag=[新应用的镜像标签]
        ```
    *   `-f path/to/my-new-app-values.yaml` 会告诉 Helm 使用我们为新应用定制的 `values` 文件。
    *   `--install my-new-app` 会创建一个名为 `my-new-app` 的新 Helm Release。

通过这种方式，您可以使用**同一个** Helm Chart (`py-webhook-svc-chart`) 来管理多个不同的微服务，只需为每个服务维护一个独立的 `values` 文件即可，这极大地提高了部署的效率和一致性。

## 5. 结论

从 `kubectl` + `sed` 迁移到 Helm Chart 是一个巨大的进步。虽然我们在这个过程中遇到了各种各样的问题（从构建器环境，到 GKE 的网络行为，再到最根本的 Kubernetes 标签选择器机制），但最终的结果是一个**健壮、可配置、可重用且易于理解**的部署方案。

这次漫长的排错之旅，不仅修复了部署，更重要的是，它让我们对 GKE、Kubernetes 和 Helm 的协同工作原理有了极其深刻的理解。
