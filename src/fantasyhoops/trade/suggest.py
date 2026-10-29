"""The scorer of the 1-for-1 trade suggestions (#150). It writes no file. The design is in docs/trade/README.md.

The playoff starts of a team count its kept set: the top [trade] kept players by value. The untouchable players
([trade] untouchable) and the IL players are always in it. In a trade, the player you get takes the spot of the
player you give in the kept set. The run does not rank the kept set again after the trade (Decision comment on #150).
The starts use the Roster page rules: core/roster.py lineup_fit() on the playoff days of roster_page.playoff_days().
A pair is a suggestion if the value of the player you get is in the value band of the player you give, and the trade
raises your total playoff starts by 1 or more. The suggestions give only the players of the [trade] offer list (#170). An
empty list offers each player who is not untouchable. The rank: the gain in total starts, then the gain of your weakest
week, then your value change.
"""

from collections import Counter
from dataclasses import dataclass

from fantasyhoops.core import roster as roster_page
from fantasyhoops.core.common import name_key

EDGE = 1e-9  # a value on an edge of the value band is in the band, also with a rounding error of the float math
PRE = "pre"  # the mark of a value that is the preseason pg_value, because the player has no blended value


def player_value(blended, pg):
    """(value, mark) of a player: the blended value with no mark, else the preseason pg_value with the mark PRE.
    (None, "") if he has neither."""
    if blended is not None:
        return blended, ""
    if pg is not None:
        return pg, PRE
    return None, ""


@dataclass(frozen=True)
class TradePlayer:
    """One player on your team or on the team of a partner.

    name, team, positions, slot, status, rank, rests_b2b: as in roster_page.RosterPlayer. slot is "" for a player of a
    partner team, because the rostered list does not show the roster slots.
    value: the blended value per game, or the preseason pg_value if he has no blended value (mark "pre").
    None if he has neither. pg: the preseason pg_value, or None. team_id, team_name: his fantasy team.
    """

    name: str
    team: str
    positions: tuple
    slot: str = ""
    status: str = ""
    value: float | None = None
    mark: str = ""
    pg: float | None = None
    rank: int | None = None
    rests_b2b: bool = False
    team_id: int | None = None
    team_name: str = ""

    @property
    def on_il(self):
        return self.slot.startswith("IL")

    def roster_player(self):
        """The roster_page.RosterPlayer of the player, for lineup_fit()."""
        return roster_page.RosterPlayer(
            name=self.name,
            team=self.team,
            positions=tuple(self.positions),
            slot=self.slot,
            status=self.status,
            rank=self.rank,
            rests_b2b=self.rests_b2b,
        )


@dataclass(frozen=True)
class TradeSettings:
    """The [trade] section of config.toml. untouchable: a frozenset of name keys (common.name_key()).

    offer: the names of the [trade] offer list, in the config order (#170). An empty tuple offers each player who
    is not untouchable.
    """

    untouchable: frozenset
    band: tuple
    kept: int
    per_player: int
    rows: int
    offer: tuple = ()

    @classmethod
    def from_config(cls, cfg):
        t = cfg["trade"]
        return cls(
            untouchable=frozenset(name_key(n) for n in t["untouchable"]),
            band=tuple(t["value_band"]),
            kept=int(t["kept"]),
            per_player=int(t["per_player"]),
            rows=int(t["rows"]),
            offer=tuple(t.get("offer", ())),
        )

    def is_untouchable(self, player):
        return name_key(player.name) in self.untouchable

    def is_offered(self, player):
        """True if the suggestions can give the player: he is not untouchable, and the offer list is empty or has him."""
        if self.is_untouchable(player):
            return False
        return not self.offer or self.listed(player)

    def listed(self, player):
        """True if the player is on the offer list, by common.name_key()."""
        return name_key(player.name) in {name_key(n) for n in self.offer}

    def not_on_roster(self, mine):
        """The names of the offer list that are not on your roster (mine: your TradePlayers), in the config order."""
        have = {name_key(p.name) for p in mine}
        return [n for n in self.offer if name_key(n) not in have]


@dataclass(frozen=True)
class Suggestion:
    """One 1-for-1 trade. before, after: your team starts of each playoff week. gain: the change of the total.

    min_gain: min(after) - min(before). dv: your value change (get - give). partner_dv: the value change of the
    partner (give - get). partner_before, partner_after: the team starts of the partner in each week, an estimate,
    because the rostered list does not show the IL slots of the partner.
    """

    give: TradePlayer
    get: TradePlayer
    before: tuple
    after: tuple
    gain: int
    min_gain: int
    dv: float
    partner_dv: float
    partner_before: tuple = ()
    partner_after: tuple = ()


@dataclass(frozen=True)
class Suggestions:
    """The result of suggest(). base: your team starts of each week now. kept: your kept set now.

    rows: the Suggestions to show, best first. pairs: the 1-for-1 pairs. in_band: the pairs in the value band.
    gains: the pairs in the band with a gain of 1 start or more.
    offered: the names of your players that the suggestions can give, in the roster order (#170).
    missed: (name, reason) of each player on the [trade] offer list with no row. Empty if the offer list is empty.
    """

    base: tuple
    kept: list
    rows: list
    pairs: int
    in_band: int
    gains: int
    offered: tuple = ()
    missed: tuple = ()


def kept_set(players, settings):
    """The kept set of a team: the untouchable and IL players, then the highest values, settings.kept in all.

    A player with no value comes after all players with a value. The result keeps the order of players.
    """
    always = [p for p in players if settings.is_untouchable(p) or p.on_il]
    rest = sorted(
        (p for p in players if p not in always),
        key=lambda p: (p.value is None, -(p.value or 0.0)),
    )
    chosen = always + rest[: max(0, settings.kept - len(always))]
    return [p for p in players if p in chosen]


def swap(kept, give, get):
    """The kept set after a trade: get takes the spot of give. If give is not in the kept set, it does not change."""
    return [get if p == give else p for p in kept]


def week_starts(players, days, slots, weeks):
    """The team starts of players in each week of weeks, with the Roster page rules (roster_page.lineup_fit())."""
    fit = roster_page.lineup_fit([p.roster_player() for p in players], days, slots)
    return tuple(fit.team_week(w)[0] for w in weeks)


def in_band(give, get, band):
    """True if the value get is in the value band of the value give: give - (1 - band[0]) x |give| to
    give + (band[1] - 1) x |give|. The band works for values below 0 too."""
    low = give - (1 - band[0]) * abs(give)
    high = give + (band[1] - 1) * abs(give)
    return low - EDGE <= get <= high + EDGE


def rank_key(s):
    """The rank of a Suggestion: the gain, then the gain of the weakest week, then your value change."""
    return (-s.gain, -s.min_gain, -s.dv, s.give.name, s.get.name)


def limit(rows, per_player, total):
    """The first rows, at most per_player rows for each player you give and total rows in all."""
    out, per = [], Counter()
    for s in rows:
        if per[s.give.name] >= per_player:
            continue
        per[s.give.name] += 1
        out.append(s)
        if len(out) == total:
            break
    return out


def suggest(mine, others, days, slots, weeks, settings):
    """Score each 1-for-1 pair of your players and the players of the other teams. Give Suggestions.

    mine: your TradePlayers. others: the TradePlayers of the other teams (each with team_id). days: the playoff
    days (roster_page.playoff_days()). slots: [league] slots. weeks: the names of the playoff weeks.
    A pair with no value on either side is not a suggestion. The suggestions give only the offered players
    (settings.is_offered()). The untouchable players are never in a trade.
    """
    kept = kept_set(mine, settings)
    base = week_starts(kept, days, slots, weeks)
    pairs = scored = 0
    found = []
    band_hits, gain_hits = Counter(), Counter()
    for give in mine:
        if not settings.is_offered(give):
            continue
        for get in others:
            pairs += 1
            if give.value is None or get.value is None or not in_band(give.value, get.value, settings.band):
                continue
            scored += 1
            band_hits[give.name] += 1
            if give not in kept:
                continue  # get takes the spot of give, which is not in the kept set: no change of the starts
            after = week_starts(swap(kept, give, get), days, slots, weeks)
            gain = sum(after) - sum(base)
            if gain < 1:
                continue
            gain_hits[give.name] += 1
            found.append(
                Suggestion(
                    give, get, base, after, gain, min(after) - min(base), get.value - give.value, give.value - get.value
                )
            )
    found.sort(key=rank_key)
    rows = [
        partner_side(s, others, days, slots, weeks, settings) for s in limit(found, settings.per_player, settings.rows)
    ]
    offered = tuple(p.name for p in mine if settings.is_offered(p))
    shown = {s.give.name for s in rows}
    missed = tuple(
        (p.name, no_row_reason(p, kept, band_hits[p.name], gain_hits[p.name], settings))
        for p in mine
        if settings.listed(p) and p.name not in shown
    )
    return Suggestions(base, kept, rows, pairs, scored, len(found), offered, missed)


def no_row_reason(player, kept, band, gains, settings):
    """The reason that a player on the offer list has no row (#170). The first check that applies gives the reason.

    kept: your kept set. band: his pairs in the value band. gains: his pairs in the band with a gain.
    """
    if settings.is_untouchable(player):
        return "he is on the [trade] untouchable list, and untouchable wins over offer."
    if player.value is None:
        return "he has no value."
    if player not in kept:
        return f"he is not in your {settings.kept} kept players, so a trade does not change your playoff starts."
    if not band:
        return "no player of another team has a value in his value band."
    if not gains:
        return "no trade in his value band raises your playoff starts."
    return f"his trades rank below the {settings.rows} trade{'' if settings.rows == 1 else 's'} that the page shows."


def partner_side(s, others, days, slots, weeks, settings):
    """The Suggestion s with the team starts of the partner before and after, by the same rule as your side."""
    team = [p for p in others if p.team_id == s.get.team_id]
    kept = kept_set(team, settings)
    before = week_starts(kept, days, slots, weeks)
    after = week_starts(swap(kept, s.get, s.give), days, slots, weeks)
    return Suggestion(**{**s.__dict__, "partner_before": before, "partner_after": after})
