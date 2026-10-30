"""Check the name match between the projections and the ESPN names (#181). This module writes no file.

core/identity.py and adds/roles.py match a projection name to an ESPN name after name_key().
data/name_overrides.csv gives the ESPN name (espn_name) of a player whose names do not match.
Inputs: the newest projections file, data/rotation_log.csv, data/rosters.csv and data/name_overrides.csv.
A projected player has more than 0 games in the projections.

The check gives 3 lists:
1. Mismatches: a projected player with no ESPN match, and an ESPN name with no projection row and the same last name.
   Put the ESPN name in the espn_name cell of his row in data/name_overrides.csv.
2. No ESPN name: a projected player with no ESPN match and no candidate. He has no game in the log and
   is not on rosters.csv, for example a player with no team.
3. No projection row: an ESPN name that matches no projection row and no projected player. He is not a mismatch.
An ESPN name that matches a projection row with 0 games is not in a list.

Run: python -m fantasyhoops.adds.name_check
"""

from dataclasses import dataclass

import pandas as pd

from fantasyhoops.core.common import DATA, latest_projections, load_config, name_key
from fantasyhoops.core.console import use_utf8_output
from fantasyhoops.core.rotation import LOG

ROSTERS = DATA / "rosters.csv"
OVERRIDES = DATA / "name_overrides.csv"


@dataclass(frozen=True)
class Mismatch:
    """A projected player and an ESPN name with no projection row that has his last name."""

    player_id: str
    name: str  # the projection name
    espn_name: str


@dataclass(frozen=True)
class NameCheck:
    mismatches: list  # Mismatch, sorted by projection name
    no_espn: list  # projection names, sorted
    no_projection: list  # ESPN names, sorted


def _last_name(key):
    return key.split()[-1] if key else ""


def check_names(projections, espn_names, overrides):
    """The 3 lists of the module docstring.

    projections: a frame with the columns player_id, name and games. espn_names: the ESPN names of the log and
    of rosters.csv. overrides: data/name_overrides.csv, read with dtype=str and fillna("").
    """
    fixes = overrides.set_index("player_id").espn_name
    fixes = fixes[fixes != ""]
    ids = projections.player_id.astype(str)
    keys = ids.map(fixes).fillna(projections.name).map(name_key)

    espn = {}  # ESPN name key: the first ESPN name with the key
    for n in espn_names:
        espn.setdefault(name_key(n), n)
    no_row = {k: n for k, n in espn.items() if k not in set(keys)}

    mismatches, no_espn = [], []
    projected = projections.games > 0
    for pid, name, key in zip(ids[projected], projections.name[projected], keys[projected]):
        if key in espn:
            continue
        found = [n for k, n in no_row.items() if _last_name(k) == _last_name(key)]
        mismatches += [Mismatch(pid, name, n) for n in found]
        if not found:
            no_espn.append(name)
    matched = {name_key(m.espn_name) for m in mismatches}
    return NameCheck(
        mismatches=sorted(mismatches, key=lambda m: (m.name, m.espn_name)),
        no_espn=sorted(no_espn),
        no_projection=sorted(n for k, n in no_row.items() if k not in matched),
    )


def read_projections(cfg):
    """The newest projections file with a name column (first name and last name)."""
    df = pd.read_csv(latest_projections(cfg))
    return df.assign(name=df.first_name + " " + df.last_name)


def read_espn_names():
    """The player names of data/rotation_log.csv and data/rosters.csv. A missing file gives no names."""
    names = []
    if LOG.exists():
        names += pd.read_csv(LOG, usecols=["player"]).player.tolist()
    if ROSTERS.exists():
        names += pd.read_csv(ROSTERS).espn_name.tolist()
    return names


def read_overrides():
    return pd.read_csv(OVERRIDES, dtype=str).fillna("")


def report(result):
    """The 3 lists as lines of text, each with its count."""
    lines = [f"Mismatches ({len(result.mismatches)}). Put the ESPN name in espn_name of data/name_overrides.csv:"]
    lines += [f"  {m.name} (player_id {m.player_id}): {m.espn_name}" for m in result.mismatches]
    lines.append(f"Projected players with no ESPN name ({len(result.no_espn)}):")
    lines += [f"  {n}" for n in result.no_espn]
    lines.append(f"ESPN names with no projection row ({len(result.no_projection)}). These are not mismatches:")
    lines += [f"  {n}" for n in result.no_projection]
    return lines


def main():
    result = check_names(read_projections(load_config()), read_espn_names(), read_overrides())
    print("\n".join(report(result)))


if __name__ == "__main__":
    use_utf8_output()
    main()
