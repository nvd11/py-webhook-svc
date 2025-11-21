# 指南：如何在 GKE 中实现最佳的日志记录实践

本文档以`py-webhook-svc`服务为例，详细说明了如何配置一个 Python 应用程序，以确保其在 Google Kubernetes Engine (GKE) 上的日志能够被正确地捕获，并在 Google Cloud Logging 中显示正确的严重性级别（如 `DEBUG`, `INFO`, `WARNING`, `ERROR`）。

## 1. 问题背景：为何我的 `DEBUG` 日志会显示为 `INFO`？

在 GKE 中，集成的 Cloud Logging 代理会自动捕获容器的标准输出（`stdout`）和标准错误（`stderr`）。其默认行为是：
-   所有写入 **`stdout`** 的日志，其严重性（`severity`）被标记为 **`INFO`**。
-   所有写入 **`stderr`** 的日志，其严重性（`severity`）被标记为 **`ERROR`**。

如果您只是简单地将日志打印到控制台，Cloud Logging 无法识别纯文本中的 "DEBUG" 或 "WARNING" 字样，因此会使用默认的 `INFO` 级别。

## 2. 解决方案：采用与 GCP 兼容的结构化日志

最佳解决方案是让应用程序输出 **JSON 格式的结构化日志** 到 **`stdout`**，并且这个 JSON 中包含一个 Google Cloud Logging **能够识别**的严重性字段。

当 Cloud Logging 接收到 JSON 格式的日志时，它会自动解析该 JSON，并专门寻找一个**顶层的、名为 `severity` 的字段**，用它的值来正确地设置日志条目的严重性。

## 3. 在`py-webhook-svc`中的实现 (`loguru`)

我们使用 `loguru` 库来实现结构化日志，因为它非常灵活。

### 步骤1：安装`loguru`
确保`loguru`已添加到您的`requirements.txt`中：
```
loguru
```

### 步骤2：配置`loguru`输出与 GCP 兼容的 JSON

在我们的项目`py-webhook-svc`中，我们在`src/configs/config.py`文件中对日志进行了统一配置。核心配置如下：

```python
# src/configs/config.py

import sys
from loguru import logger

# 移除所有默认的处理器
logger.remove()

# 定义一个自定义的格式化函数
# 这个函数会创建一个包含 "severity" 键的字典，这正是 Cloud Logging 所需要的
def gcp_formatter(record):
    return {
        "severity": record["level"].name,
        "message": record["message"],
        "timestamp": record["time"].isoformat(),
        "file": record["file"].path,
        "line": record["line"],
        "function": record["function"],
    }

# 添加一个新的处理器 (sink)
# 1. sys.stdout: 指定输出目标为标准输出。
# 2. format=gcp_formatter: 使用我们自定义的格式化函数。
# 3. serialize=True: 告诉 loguru 将格式化函数返回的字典序列化为 JSON 字符串。
# 4. level="DEBUG": 设置此处理器的过滤阈值，确保 DEBUG 及以上所有级别的日志都会被处理。
logger.add(sys.stdout, format=gcp_formatter, level="DEBUG", serialize=True)

logger.info("日志系统已配置为输出与 GCP 兼容的 JSON 到 stdout")
```

### 工作原理

当您在代码中调用`logger.debug("Root endpoint accessed!")`时：
1.  `loguru` 调用 `gcp_formatter` 函数，生成一个 Python 字典：
    ```python
    {
        "severity": "DEBUG",
        "message": "Root endpoint accessed!",
        ...
    }
    ```
2.  `loguru` 将这个字典序列化为 JSON 字符串，并打印到 `stdout`。
3.  GKE 的日志代理捕获 `stdout` 的内容，并将其发送到 Cloud Logging。
4.  Cloud Logging 服务识别出这是一个 JSON 载荷，自动解析它，并使用顶层 `severity` 字段的值 (`"DEBUG"`) 来设置该日志条目的 `severity`。

## 4. GKE 配置注意事项

- **无需额外代理**: 只要您的 GKE 集群启用了与 Cloud Logging 的集成（默认开启），您**不需要**为这个功能部署任何额外的日志代理或 sidecar（如 Fluentd）。我们在这个项目中已经完全移除了 `fluentd` sidecar，实现了更轻量、更云原生的部署。

## 5. 验证

1.  将您的服务部署到 GKE。
2.  在 GCP 控制台中，导航到 **日志浏览器 (Logs Explorer)**。
3.  使用查询过滤器来查找您的服务日志，例如：
    ```
    resource.type="k8s_container"
    resource.labels.cluster_name="my-cluster2"
    resource.labels.container_name="py-webhook-svc-chart"
    severity="DEBUG"
    ```
4.  观察日志条目。您会看到 `logger.debug()` 产生的日志其`severity`为`DEBUG`，`logger.info()`产生的日志其`severity`为`INFO`，并且日志的`jsonPayload`字段包含了我们自定义的 JSON 结构。

通过以上配置，您就可以确保 GKE 服务的日志在 Cloud Logging 中得到准确、可靠的记录。
