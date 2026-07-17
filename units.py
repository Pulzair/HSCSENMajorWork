import json
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
UNITS_DIR = Path(__file__).resolve().parent / "data" / "units"
LAYERS = ("land", "underground", "sky")

_roster = None  # filled in on first read, then reused


# ═══════════════════════════════════════════════════════════════════════════
# LOADING
# ═══════════════════════════════════════════════════════════════════════════
# Unit types live in data/units/*.json so adding one needs no code and no
# schema change (NF09). Stats get copied onto the Unit row when it's built,
# because health drops as it takes hits but the config stays the template.
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


# ═══════════════════════════════════════════════════════════════════════════
# RULES
# ═══════════════════════════════════════════════════════════════════════════
# "layers" in the config is ordered on purpose: [0] is where the unit gets
# built, anything after that is a layer it can cross into at a transition point
def home_layer(unit_type):
    spec = get_unit(unit_type)
    return spec["layers"][0] if spec else None


def can_transition(unit_type):
    spec = get_unit(unit_type)
    return bool(spec) and len(spec["layers"]) > 1


# Unit types that can be built on a layer, cheapest first.
def buildable_in(layer):
    roster = load_roster()
    types = [key for key, spec in roster.items() if spec["layers"][0] == layer]
    return sorted(types, key=lambda key: roster[key]["cost"])


def can_occupy(unit_type, layer, terrain):
    spec = get_unit(unit_type)
    if spec is None:
        return False
    return layer in spec["layers"] and terrain in spec["terrain"]


# Whole roster grouped by home layer, for the codex page.
def roster_by_layer():
    roster = load_roster()
    grouped = {}
    for layer in LAYERS:
        grouped[layer] = [dict(roster[key], key=key) for key in buildable_in(layer)]
    return grouped
