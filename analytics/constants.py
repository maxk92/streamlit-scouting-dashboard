"""
Shared analytics constants for notebooks and dashboards.

All mappings/lists that were previously copy-pasted into every notebook
live here as a single source of truth.
"""

# Transfermarkt → WhoScored league name mapping
LEAGUE_NAME_DICT: dict[str, str] = {
    "MLS": "USA-Major League Soccer",
    "Liga Portugal": "POR-Primeira Liga",
    "Série A": "BRA-Serie A",
    "Bundesliga": "GER-Bundesliga",
    "Serie A": "ITA-Serie A",
    "Eredivisie": "NED-Eredivisie",
    "Jupiler Pro League": "BEL-Pro League",
    "League One": "ENG-League One",
    "2. Bundesliga": "GER-2 Bundesliga",
    "Ligue 1": "FRA-Ligue 1",
    "Süper Lig": "TUR-Super Lig",
    "LaLiga": "ESP-La Liga",
    "Premier Liga": "RUS-Premier League",
    "Premiership": "SCO-Premiership",
    "Premier League": "ENG-Premier League",
    "Championship": "ENG-Championship",
}

# WhoScored position code → simplified position (no left/right distinction)
POSITION_MAPPING: dict[str, str] = {
    "DMR": "CM", "DML": "CM", "DMC": "CM",
    "AML": "AM", "AMR": "WM", "AMC": "AM",
    "ML": "WM",  "MR": "WM",  "MC": "CM",
    "DC": "CB",  "DL": "FB",  "DR": "FB",
    "FW": "FW",  "FWL": "WM", "FWR": "WM",
    "GK": "GK",  "Sub": "Sub",
}

# WhoScored position code → simplified position (left/right preserved)
POSITION_MAPPING_SIDES: dict[str, str] = {
    "DMR": "CM", "DML": "CM", "DMC": "CM",
    "AML": "LM", "AMR": "RM", "AMC": "AM",
    "ML": "LM",  "MR": "RM",  "MC": "CM",
    "DC": "CB",  "DL": "LB",  "DR": "RB",
    "FW": "FW",  "FWL": "LM", "FWR": "RM",
    "GK": "GK",  "Sub": "Sub",
}

# Synthetic category name → the type_names it aggregates over.
# These categories are pre-computed in player_match_vaep; this dict
# documents the mapping for reference and for ad-hoc use.
ACTION_CATEGORIES: dict[str, list[str]] = {
    "passing":   ["pass", "cross"],
    "dribbling": ["dribble", "take_on"],
    "defending": ["tackle", "interception", "keeper_save"],
    # 'total' and 'total_nogoals' are defined by exclusion (all / all-except-goal)
}

# Action types counted in league/team analysis notebooks
INCLUDED_ACTION_TYPES: list[str] = [
    "pass", "interception", "dribble", "keeper_pick_up", "cross", "clearance",
    "shot", "corner", "tackle", "take_on", "throw_in", "bad_touch", "offside",
    "freekick", "goalkick", "foul", "keeper_claim", "keeper_save",
    "keeper_punch", "shot_penalty",
]

# All 5 synthetic category names stored in player_match_vaep / player_season_vaep
SYNTHETIC_TYPE_NAMES: list[str] = [
    "total", "total_nogoals", "passing", "dribbling", "defending",
]
