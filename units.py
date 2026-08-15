import json
from pathlib import Path

UNITS_DIR = Path(__file__).resolve().parent / "data" / "units"
LAYERS = ("land", "underground", "sky")

_roster = None


def load_roster(force=False):
    global _roster
    if _roster is None or force:
        roster = {}
        for path in sorted(UNITS_DIR.glob("*.json")):
            with open(path, "r", encoding="utf-8") as f:
                roster.update(json.load(f))
        _roster = roster
    return _roster


def get_unit(unit_type):
    return load_roster().get(unit_type)


def home_layer(unit_type):
    spec = get_unit(unit_type)
    return spec["layers"][0] if spec else None


def can_transition(unit_type):
    spec = get_unit(unit_type)
    return bool(spec) and len(spec["layers"]) > 1


def buildable_in(layer):
    roster = load_roster()
    types = [key for key, spec in roster.items() if layer in spec["layers"]]
    return sorted(types, key=lambda key: roster[key]["cost"])


def can_occupy(unit_type, layer, terrain):
    spec = get_unit(unit_type)
    if spec is None:
        return False
    return layer in spec["layers"] and terrain in spec["terrain"]


def roster_by_layer():
    roster = load_roster()
    grouped = {}
    for layer in LAYERS:
        grouped[layer] = [dict(roster[key], key=key) for key in buildable_in(layer)]
    return grouped
