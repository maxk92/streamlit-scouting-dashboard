"""
Player aggregation pipeline.

Provides `build_player_season_df` and `build_player_game_df` — the query +
aggregation logic that was previously copy-pasted into player-scouting.ipynb
and player-report.ipynb.

Usage (notebook):
    import sys; sys.path.insert(0, '..')
    from analytics.player_pipeline import build_player_season_df, build_player_game_df
    import duckdb

    con = duckdb.connect('/home/max/soccerdata/data/WhoScored/duckdb/football.duckdb',
                         read_only=True)
    df = build_player_season_df(con, seasons=['2526'], leagues=['ENG-Premier League'])
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .constants import POSITION_MAPPING, POSITION_MAPPING_SIDES


def _has_view(con, view_name: str) -> bool:
    """Return True if *view_name* exists as a VIEW in the connected DuckDB."""
    rows = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_name = ? AND table_type = 'VIEW'",
        [view_name],
    ).fetchone()
    return rows[0] > 0


def _build_where(
    seasons: Optional[list[str]],
    leagues: Optional[list[str]],
    table_alias: str = "",
) -> tuple[str, list]:
    """Return (WHERE clause fragment, params list) for optional season/league filters."""
    prefix = f"{table_alias}." if table_alias else ""
    clauses, params = [], []
    if seasons:
        placeholders = ", ".join("?" * len(seasons))
        clauses.append(f"{prefix}season IN ({placeholders})")
        params.extend(seasons)
    if leagues:
        placeholders = ", ".join("?" * len(leagues))
        clauses.append(f"{prefix}league IN ({placeholders})")
        params.extend(leagues)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def build_player_season_df(
    con,
    seasons: Optional[list[str]] = None,
    leagues: Optional[list[str]] = None,
    include_market_value: bool = False,
) -> pd.DataFrame:
    """
    Return per-season, per-player, per-type_name aggregates.

    type_name values include both atomic action types (pass, shot, …) and the
    five synthetic categories (total, total_nogoals, passing, dribbling, defending).

    If the `player_season_vaep` VIEW exists it is queried directly (fast path).
    Otherwise the function falls back to computing the aggregation on the fly from
    the `actions`, `matches`, and `playerstats` tables (slow path — same result).

    The returned DataFrame has columns:
        player_id, player_name, league, season, type_name, team,
        vaep_total, off_total, def_total, n_actions, vaep_stability,
        minutes_played, vaep90, off90, def90,
        position, main_position, main_position_sides
        [market_value_eur, tm_player_id]  ← only if include_market_value=True

    position         — hyphen-joined unique positions via POSITION_MAPPING_SIDES, excl. Sub
    main_position    — majority position via POSITION_MAPPING, excl. Sub
    main_position_sides — majority position via POSITION_MAPPING_SIDES, excl. Sub
    """
    where, params = _build_where(seasons, leagues)

    if _has_view(con, "player_season_vaep"):
        sql = f"SELECT * FROM player_season_vaep {where}"
        df = con.execute(sql, params).df()
    else:
        df = _build_player_season_slow(con, where, params)

    if include_market_value and _has_view(con, "player_market_value_at_match"):
        mv = _season_market_value(con, seasons, leagues)
        df = df.merge(mv, on=["player_id", "league", "season"], how="left")

    return df


def build_player_game_df(
    con,
    seasons: Optional[list[str]] = None,
    leagues: Optional[list[str]] = None,
    include_market_value: bool = False,
) -> pd.DataFrame:
    """
    Return per-game, per-player, per-type_name aggregates.

    If `player_match_vaep` table exists it is queried directly (fast path).
    Otherwise falls back to the full 3-way join (slow path).

    The returned DataFrame has columns:
        player_id, player_name, game_id, league, season, type_name, team,
        vaep_total, off_total, def_total, n_actions, minutes_played,
        position, position_sides
        [market_value_eur, tm_player_id]  ← only if include_market_value=True
    """
    has_table = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'player_match_vaep'"
    ).fetchone()[0] > 0

    where, params = _build_where(seasons, leagues)

    if has_table:
        sql = f"SELECT * FROM player_match_vaep {where}"
        df = con.execute(sql, params).df()
    else:
        df = _build_player_game_slow(con, where, params)

    if "position_code" in df.columns:
        df["position"]       = df["position_code"].map(POSITION_MAPPING)
        df["position_sides"] = df["position_code"].map(POSITION_MAPPING_SIDES)

    if include_market_value and _has_view(con, "player_market_value_at_match"):
        mv = _game_market_value(con, seasons, leagues)
        df = df.merge(mv, on=["player_id", "game_id"], how="left")

    return df


# =============================================================================
# Market value helpers
# =============================================================================

def _game_market_value(
    con,
    seasons: Optional[list[str]],
    leagues: Optional[list[str]],
) -> pd.DataFrame:
    """
    Return (player_id, game_id, market_value_eur, tm_player_id) from the
    player_market_value_at_match view, filtered to the requested seasons/leagues.
    market_value_eur is the most recent TM value before each match date.
    """
    where, params = _build_where(seasons, leagues)
    sql = f"""
        SELECT player_id, game_id, tm_player_id, market_value_eur
        FROM player_market_value_at_match
        {where}
    """
    return con.execute(sql, params).df()


def _season_market_value(
    con,
    seasons: Optional[list[str]],
    leagues: Optional[list[str]],
) -> pd.DataFrame:
    """
    Return (player_id, league, season, market_value_eur, tm_player_id) aggregated
    to season level by taking the median market value across all game appearances.
    Null values (unmatched players) are preserved as NaN.
    """
    where, params = _build_where(seasons, leagues)
    sql = f"""
        SELECT
            player_id,
            league,
            season,
            tm_player_id,
            MEDIAN(market_value_eur)  AS market_value_eur
        FROM player_market_value_at_match
        {where}
        GROUP BY player_id, league, season, tm_player_id
    """
    return con.execute(sql, params).df()


# =============================================================================
# Slow-path fallbacks (reproduce the original notebook aggregation pipeline)
# =============================================================================

_GAME_SQL = """
SELECT
    CAST(a.player_id AS INTEGER) AS player_id,
    a.game_id,
    a.type_name,
    MIN(a.team)              AS team,
    SUM(a.vaep_value)        AS vaep_total,
    SUM(a.offensive_value)   AS off_total,
    SUM(a.defensive_value)   AS def_total,
    COUNT(*)                 AS n_actions,
    m.league,
    m.season,
    ps.player_name,
    ps.position_code,
    ps.minutes_played
FROM actions a
JOIN matches m ON a.game_id = m.game_id
JOIN playerstats ps
  ON a.game_id = ps.game_id
 AND CAST(a.player_id AS INTEGER) = ps.player_id
{where}
GROUP BY a.player_id, a.game_id, a.type_name,
         m.league, m.season,
         ps.player_name, ps.position_code, ps.minutes_played
"""

_GROUP_COLS = [
    "player_id", "player_name", "game_id", "team",
    "league", "season", "position_code", "minutes_played",
]
_AGG = {"vaep_total": "sum", "off_total": "sum", "def_total": "sum", "n_actions": "sum"}


def _build_player_game_slow(con, where: str, params: list) -> pd.DataFrame:
    sql = _GAME_SQL.format(where=where)
    df = con.execute(sql, params).df()
    df = df.rename(columns={
        "total_vaep_value": "vaep_total",
        "total_offensive_value": "off_total",
        "total_defensive_value": "def_total",
    })

    cats = {
        "total":         df,
        "total_nogoals": df[df.type_name != "goal"],
        "passing":       df[df.type_name.isin(["pass", "cross"])],
        "dribbling":     df[df.type_name.isin(["dribble", "take_on"])],
        "defending":     df[df.type_name.isin(["tackle", "interception", "keeper_save"])],
    }
    extras = []
    for cat_name, sub in cats.items():
        agg = sub.groupby(_GROUP_COLS)[list(_AGG)].sum().reset_index()
        agg["type_name"] = cat_name
        extras.append(agg)

    return pd.concat([df] + extras, ignore_index=True)


def _build_player_season_slow(con, where: str, params: list) -> pd.DataFrame:
    df_game = _build_player_game_slow(con, where, params)

    season_minutes = (
        df_game[df_game.type_name == "total"]
        .drop_duplicates(["player_id", "player_name", "game_id", "league", "season"])
        .groupby(["player_id", "player_name", "league", "season"])["minutes_played"]
        .sum()
        .reset_index()
        .rename(columns={"minutes_played": "total_minutes"})
    )

    # Pre-compute per-game position columns excluding Sub for the season aggregation.
    # Use the total row only (one position per game per player).
    pos_df = df_game[
        (df_game.type_name == "total")
        & df_game.position_code.notna()
        & ~df_game.position_code.isin(["Sub", ""])
    ].copy()
    pos_df["_pos"]       = pos_df["position_code"].map(POSITION_MAPPING)
    pos_df["_pos_sides"] = pos_df["position_code"].map(POSITION_MAPPING_SIDES)

    def _mode(s):
        vc = s.dropna().value_counts()
        return vc.index[0] if len(vc) else None

    pos_agg = (
        pos_df.groupby(["player_id", "league", "season"])
        .agg(
            position=("_pos_sides", lambda x: "-".join(sorted(set(x.dropna())))),
            main_position=("_pos", _mode),
            main_position_sides=("_pos_sides", _mode),
        )
        .reset_index()
    )

    idx = ["player_id", "player_name", "league", "season", "type_name"]
    df_season = (
        df_game
        .groupby(idx + ["team"])
        .agg(
            vaep_total=("vaep_total", "sum"),
            off_total=("off_total", "sum"),
            def_total=("def_total", "sum"),
            n_actions=("n_actions", "sum"),
            vaep_stability=("vaep_total", "std"),
        )
        .reset_index()
        .merge(season_minutes, on=["player_id", "player_name", "league", "season"])
        .merge(pos_agg, on=["player_id", "league", "season"], how="left")
    )

    df_season["minutes_played"] = df_season["total_minutes"].replace(0, 1)
    df_season["vaep90"] = df_season["vaep_total"] / df_season["minutes_played"] * 90
    df_season["off90"]  = df_season["off_total"]  / df_season["minutes_played"] * 90
    df_season["def90"]  = df_season["def_total"]  / df_season["minutes_played"] * 90

    return df_season
