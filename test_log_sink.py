import sys
import json
from loguru import logger

def setup_logging_sink(app_env_variable: str = "local"):
    logger.remove()

    if app_env_variable != "local":
        def gcp_sink(message):
            record = message.record
            log_entry = {
                "severity": record["level"].name,
                "message": record["message"],
                "timestamp": record["time"].isoformat(),
                "logging.googleapis.com/sourceLocation": {
                    "file": record["file"].path,
                    "line": record["line"],
                    "function": record["function"],
                },
            }
            print(json.dumps(log_entry))

        logger.add(gcp_sink, level="DEBUG")
        logger.info("Loguru configured for custom JSON output to stdout for GCP (sink).")
    else:
        logger.add(sys.stderr, level="DEBUG")
        logger.info("Loguru configured for standard terminal output.")

setup_logging_sink("prod")
logger.info("Test sink message")

