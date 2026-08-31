import json


def load_config(path):
    f = open(path)  # BUG: resource_leak - never closed
    data = json.load(f)
    return data


def load_config_safe(path):
    with open(path) as f:  # safe - should NOT be flagged
        return json.load(f)


def load_config_manual_close(path):
    f = open(path)  # safe - explicitly closed below, should NOT be flagged
    data = json.load(f)
    f.close()
    return data


def parse_int(value):
    try:
        return int(value)
    except ValueError:
        pass  # BUG: swallowed_exception


def parse_int_safe(value):
    try:
        return int(value)
    except ValueError as e:
        print(f"bad value: {e}")  # safe - should NOT be flagged
        return None


def add_item(item, items=[]):  # BUG: mutable_default
    items.append(item)
    return items


def add_item_safe(item, items=None):  # safe - should NOT be flagged
    if items is None:
        items = []
    items.append(item)
    return items
