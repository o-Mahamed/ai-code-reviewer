import json


def load_config(path):
    with open(path) as f:
        return json.load(f)


def parse_value(raw):
    try:
        return int(raw)
    except ValueError as e:
        print(f"bad value: {e}")
        return None


def optional_dep():
    try:
        import ujson
    except ImportError:
        ujson = None
    return ujson
