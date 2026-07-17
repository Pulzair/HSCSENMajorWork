import json
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
IMPROVEMENTS_DIR = Path(__file__).resolve().parent / "data" / "improvements"

_catalogue = None


# ═══════════════════════════════════════════════════════════════════════════
# LOADING
# ═══════════════════════════════════════════════════════════════════════════
# FR13 wants "improving cells within borders and the central district". The city
# is the central district (placed at spawn), everything else a player builds on
# their own tiles is one of these. Config files again so NF09 holds.
def load_catalogue(force=False):
    global _catalogue
    if _catalogue is None or force:
        catalogue = {}
        for path in sorted(IMPROVEMENTS_DIR.glob("*.json")):
            with open(path, "r", encoding="utf-8") as f:
                catalogue.update(json.load(f))
        _catalogue = catalogue
    return _catalogue


def get(improvement):
    return load_catalogue().get(improvement)


# ═══════════════════════════════════════════════════════════════════════════
# RULES
# ═══════════════════════════════════════════════════════════════════════════
def can_build_on(improvement, layer, terrain):
    spec = get(improvement)
    if spec is None:
        return False
    return layer in spec["layers"] and terrain in spec["terrain"]


# Improvements valid on this kind of tile, cheapest first.
def options_for(layer, terrain):
    catalogue = load_catalogue()
    keys = [k for k in catalogue if can_build_on(k, layer, terrain)]
    return sorted(keys, key=lambda k: catalogue[k]["cost"])


def allows_production(improvement):
    spec = get(improvement)
    return bool(spec) and spec.get("allows_production", False)  # barracks basically


def catalogue_by_layer(layers):
    catalogue = load_catalogue()
    grouped = {}
    for layer in layers:
        grouped[layer] = [
            dict(catalogue[key], key=key)
            for key in sorted(catalogue, key=lambda k: catalogue[k]["cost"])
            if layer in catalogue[key]["layers"]
        ]
    return grouped
