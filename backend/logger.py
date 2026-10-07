import logging
import os

logger = logging.getLogger("dano_flota")

logger.setLevel(logging.INFO)

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "app.log")

file_handler = logging.FileHandler(LOG_FILE)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

