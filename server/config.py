import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Server / Host configuration
HOSTNAME = os.environ.get("HOSTNAME")
if not HOSTNAME:
    raise RuntimeError('You must set "HOSTNAME" in your .env file.')

# DID for this service; defaults to did:web if not provided
SERVICE_DID = os.environ.get("SERVICE_DID") or f"did:web:{HOSTNAME}"

# Logging configuration
from server.logger import logger
FLASK_RUN_FROM_CLI = os.environ.get("FLASK_RUN_FROM_CLI")
if FLASK_RUN_FROM_CLI:
    logger.setLevel(logging.DEBUG)

# Optional global flags
def _get_bool_env_var(value: str) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "t", "yes", "y"}

IGNORE_ARCHIVED_POSTS = _get_bool_env_var(os.environ.get("IGNORE_ARCHIVED_POSTS"))
IGNORE_REPLY_POSTS = _get_bool_env_var(os.environ.get("IGNORE_REPLY_POSTS"))
