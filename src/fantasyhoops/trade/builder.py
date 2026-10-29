"""The rules of a custom trade (#152), for example 2-for-1. It writes no file. The design is in docs/trade/README.md.

The trade page computes a custom trade in the browser with trade/trade_builder.js. This module has the same rules in
Python, and tests/trade/test_parity.py shows that both give the same results.

1. The players that a team gives (and the players that it drops) leave its kept set. The players that it gets take
   their spots, the highest value first. The kept set is not ranked again (Decision comment of 2026-10-28 on #150).
2. When you get more players than you give, you pick your drops. When you give more, the spot stays empty.
3. When the partner gets more players than he gives, he drops his lowest value players that are not on IL. The
   players that he gets in the trade are not dropped. A player with no value is the lowest.
4. Your value change is sum(get) - sum(give) - sum(your drops). An open spot adds 0. A player with no value adds 0.
"""

from dataclasses import dataclass

from fantasyhoops.trade.suggest import in_band, kept_set, week_starts

IN, BELOW, ABOVE = "in", "below", "above"  # the band verdict of a trade with equal counts


@dataclass(frozen=True)
class Side:
    """The result of one team. before, after: the team starts of each playoff week. dv: the value change.

    drops: the players that the team drops. open: the open roster spots after the trade.
    """

    before: tuple
    after: tuple
    dv: float
    drops: tuple = ()
    open: int = 0


@dataclass(frozen=True)
class Trade:
    """A custom trade. mine: your Side. partner: the Side of the partner, an estimate (no IL slots).

    band: IN, BELOW or ABOVE for a trade with equal counts, else "".
    """

    mine: Side
    partner: Side
    band: str = ""


def _value(p):
    return p.value or 0.0


def by_value(players):
    """The players by value, highest first. A player with no value goes last. Equal values keep their order."""
    return sorted(players, key=lambda p: (p.value is None, -(p.value or 0.0)))


def kept_after(kept, out, incoming):
    """The kept set after a trade: each player of out leaves it, and the incoming players take the freed spots.

    The highest value incoming player takes the first freed spot. A freed spot with no incoming player stays empty.
    The incoming players with no freed spot are not in the kept set.
    """
    queue = by_value(incoming)
    after = []
    for p in kept:
        if p not in out:
            after.append(p)
        elif queue:
            after.append(queue.pop(0))
    return after


def partner_drops(team, out, n):
    """The n players that a partner drops: his lowest value players that he keeps and that are not on IL.

    team: his players before the trade. out: the players that he gives. A player with no value is the lowest.
    """
    if n <= 0:
        return ()
    left = [p for p in team if p not in out and not p.on_il]
    return tuple(sorted(left, key=lambda p: (p.value is not None, p.value or 0.0))[:n])


def band_verdict(give, get, band):
    """IN, BELOW or ABOVE: the value sum of get against the value band of the value sum of give."""
    g, r = sum(_value(p) for p in give), sum(_value(p) for p in get)
    if in_band(g, r, band):
        return IN
    return BELOW if r < g else ABOVE


def check(mine, give, get, drops, settings):
    """Raise ValueError if the trade breaks a rule of the builder."""
    if not give or not get:
        raise ValueError("A trade needs 1 or more players to give and 1 or more players to get.")
    if any(settings.is_untouchable(p) for p in list(give) + list(drops)):
        raise ValueError("A trade cannot give or drop an untouchable player.")
    if len(drops) != max(0, len(get) - len(give)):
        raise ValueError(f"Pick {max(0, len(get) - len(give))} drops: you get {len(get)} and give {len(give)}.")
    if any(p not in mine or p in give for p in drops):
        raise ValueError("A drop must be one of your players that you keep.")


def custom_trade(mine, team, give, get, drops, days, slots, weeks, settings):
    """The Trade of giving the players give and getting the players get, with your drops.

    mine: your TradePlayers. team: the TradePlayers of the partner. days, slots, weeks: as in suggest.suggest().
    """
    give, get, drops = tuple(give), tuple(get), tuple(drops)
    check(mine, give, get, drops, settings)
    kept = kept_set(mine, settings)
    before = week_starts(kept, days, slots, weeks)
    after = week_starts(kept_after(kept, give + drops, get), days, slots, weeks)
    dv = sum(map(_value, get)) - sum(map(_value, give)) - sum(map(_value, drops))
    me = Side(before, after, dv, drops, max(0, len(give) - len(get)))

    theirs = partner_drops(team, get, len(give) - len(get))
    pkept = kept_set(team, settings)
    pbefore = week_starts(pkept, days, slots, weeks)
    pafter = week_starts(kept_after(pkept, get + theirs, give), days, slots, weeks)
    pdv = sum(map(_value, give)) - sum(map(_value, get)) - sum(map(_value, theirs))
    partner = Side(pbefore, pafter, pdv, theirs, max(0, len(get) - len(give)))
    verdict = band_verdict(give, get, settings.band) if len(give) == len(get) else ""
    return Trade(me, partner, verdict)
