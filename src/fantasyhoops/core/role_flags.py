"""The starter flag and the closer flag of a player, from the games of the rotation log (#75).

The input is the frame of core/rotation.py player_games(). This module writes no file.
- Starter flag: his starts in his last window_games games that he played.
- Closer flag: his closes in the last close_window close games of his NBA team. A close game that he did not
  play counts as "not closed".
The windows count games, not days. The check order is New, then Regular, then Inconsistent:
- New: the last new_games (new_closes) games are all starts (closes), and fewer than half of the earlier games in
  the window are.
- Regular: regular_share or more of the window.
- Inconsistent: some_share or more, but less than regular_share.
- No flag: less than some_share, or fewer games than min_games (min_close_games).
The caller gives the settings: [adds.flags] in config.toml.
"""

NEW = "New"
REGULAR = "Regular"
INCONSISTENT = "Inconsistent"


def flag(history, window, min_games, new_games, regular_share, some_share):
    """NEW, REGULAR, INCONSISTENT or None for a list of True (a start or a close) and False, oldest first."""
    last = list(history)[-window:]
    if len(last) < min_games:
        return None
    earlier = last[:-new_games]
    if all(last[-new_games:]) and sum(earlier) < len(earlier) / 2:
        return NEW
    share = sum(last) / len(last)
    if share >= regular_share:
        return REGULAR
    if share >= some_share:
        return INCONSISTENT
    return None


def starter_flag(games, player_id, settings):
    """The starter flag of the player with this ESPN player_id. games: the frame of player_games()."""
    mine = games[games.player_id == player_id].sort_values("date")
    return flag(
        mine.started.tolist(),
        settings["window_games"],
        settings["min_games"],
        settings["new_games"],
        settings["regular_share"],
        settings["some_share"],
    )


def closer_flag(games, player_id, team, settings):
    """The closer flag of the player over the close games of team, his current NBA team."""
    close = (
        games[(games.team == team) & games.close_game][["game_id", "date"]]
        .drop_duplicates("game_id")
        .sort_values("date")
    )
    closed = set(games[(games.player_id == player_id) & games.closed].game_id)
    return flag(
        [g in closed for g in close.game_id],
        settings["close_window"],
        settings["min_close_games"],
        settings["new_closes"],
        settings["regular_share"],
        settings["some_share"],
    )


def role_flags(games, player_id, team, settings):
    """(starter flag, closer flag) of the player. Each flag is NEW, REGULAR, INCONSISTENT or None."""
    return starter_flag(games, player_id, settings), closer_flag(games, player_id, team, settings)
