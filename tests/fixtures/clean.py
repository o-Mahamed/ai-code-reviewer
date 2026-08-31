import json
import logging

logger = logging.getLogger(__name__)


def load_config(path):
    with open(path) as f:
        return json.load(f)


def parse_int(value):
    try:
        return int(value)
    except ValueError as e:
        logger.warning("failed to parse int: %s", e)
        return None


def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
