import sys
import json
from loguru import logger

def setup_logging(app_env_variable: str = "local"):
    logger.remove()

    if app_env_variable != "local":
        def gcp_formatter(record):
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
            record["extra"]["json_message"] = json.dumps(log_entry)
            return "{extra[json_message]}\n"

        logger.add(sys.stdout, format=gcp_formatter, level="DEBUG")
        logger.info("Loguru configured for custom JSON output to stdout for GCP.")
    else:
        logger.add(sys.stderr, level="DEBUG")
        logger.info("Loguru configured for standard terminal output.")

setup_logging("prod")
logger.info("Test message")



