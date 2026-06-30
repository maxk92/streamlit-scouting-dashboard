import os
import pandas as pd
import numpy as np
import duckdb

import matplotlib.pyplot as plt
import seaborn as sns

from analytics.constants import LEAGUE_NAME_DICT, POSITION_MAPPING, POSITION_MAPPING_SIDES
from analytics.player_pipeline import build_player_game_df, build_player_season_df

import streamlit as st

pd.set_option('display.max_columns', 22)
pd.set_option('display.width', 500)

# =========================================
# === Option A: Load from parquet files ===
# =========================================

df_players = pd.read_parquet('data/df_players-2526.parquet')
df_player_matches = pd.read_parquet('data/df_player_matches-2526.parquet')


# ===========================================
# === Option B: Load from DuckDB database ===
# ===========================================

#DB_PATH = '/home/max/soccerdata/data/WhoScored/duckdb/football.duckdb'
#con = duckdb.connect(DB_PATH, read_only=True)

#def query_df(sql: str) -> pd.DataFrame:
#    return con.execute(sql).df()

# Load per-game data from player_match_vaep (pre-aggregated — fast)
#df_player_matches_raw = build_player_game_df(con)

# Rename VAEP columns to legacy names expected by downstream cells
#df_p_per_match = df_player_matches_raw.rename(columns={
#    'vaep_total': 'total_vaep_value',
#    'off_total':  'total_offensive_value',
#    'def_total':  'total_defensive_value',
#})

# Game-level MultiIndex DataFrame (includes synthetic categories already)
#df_player_matches = df_p_per_match.set_index(['league', 'season', 'team', 'player_name'])

#df = build_player_season_df(con, seasons=['2526'], include_market_value=True)


# ==================================
# === Define variables and lists ===
# ==================================

_POSITION_ORDER = ["CB", "FB", "CM", "AM", "WM", "FW", "GK"]
_LEAGUE_ORDER = ["ENG-Premier League", "ESP-La Liga", "GER-Bundesliga", "ITA-Serie A", "FRA-Ligue 1",
                 "BEL-Pro League", "NED-Eredivisie", "POR-Liga Portugal", "SCO-Premiership", "TUR-Super Lig", "RUS-Premier League",
                 "BRA-Serie A", "USA-Major League Soccer"
                 'USA-Major League Soccer',
                 "ENG-Championship", "ENG-League One", "GER-2 Bundesliga",
                 "EUR-Champions League", "EUR-Europa League"
                  ]
all_leagues_raw = df_players.reset_index()['league'].unique().tolist()
all_leagues = [p for p in _LEAGUE_ORDER if p in all_leagues_raw]

all_positions_raw = df_players.reset_index()['main_position'].unique()
all_positions = [p for p in _POSITION_ORDER if p in all_positions_raw]

all_types = df_players.reset_index()['type_name'].unique().tolist()

# ==================================
# === Variable preprocessing =======
# ==================================

df_players['market_value_mio_eur'] = df_players['market_value_eur'] / 1_000_000
df_player_matches['market_value_mio_eur'] = df_player_matches['market_value_eur'] / 1_000_000

# ==================================
# === Dashboard starts here ========
# ==================================


st.title("MKW Player Scouting Dashboard")

st.set_page_config(
    page_title="MKW Player Scouting",
    page_icon=":soccer:",
    layout="wide",
)

# ================================
# === Filtering Sidebar ==========
# ================================

with st.sidebar:
    st.header("Filter Players", divider=False)
    st.write("Specify the player attributes that your players should meet.")

  #  selected_leagues = st.multiselect(
  #      "Select Leagues", df_players.reset_index()['league'].unique().tolist(), default=df_players.reset_index()['league'].unique().tolist()[0]
  #  )

    selected_leagues = st.pills(
       "Leagues",
       options=all_leagues, 
       selection_mode="multi",
       default="EUR-Champions League",
       )

    st.header("Select Positions", divider=False)
    col1, col2 = st.columns(2)
    selected_positions = []
    for i, pos in enumerate(all_positions):
        col = col1 if i % 2 == 0 else col2
        if col.checkbox(pos, value=True, key=f"cb_pos_{pos}"):
            selected_positions.append(pos)

    minimum_minutes, maximum_minutes = st.slider(
        "Minutes Played Range",
        min_value=0,
        max_value=int(df_players.reset_index()['minutes_played'].max()),
        value=(0, int(df_players.reset_index()['minutes_played'].max())),
        step=10,
    )

    minimum_marketval, maximum_marketval = st.slider(
        "Market Value Range [Mio. €]",
        min_value=0,
        max_value=int(df_players.reset_index()['market_value_mio_eur'].max()),
        value=(0, int(df_players.reset_index()['market_value_mio_eur'].max())),
        step=1
    )

    selected_type = st.multiselect(
        "Select Action Type", all_types, default=["total_nogoals", "dribbling", "passing", "defending", "shot"]
    )

# =================================
# === Tabs for Table and Chart ====
# =================================

tab1, tab2 = st.tabs(["Table", "Chart"])

with tab1:

    df_filtered = df_players.reset_index()[
        (df_players.reset_index()['league'].isin(selected_leagues)) &
        (df_players.reset_index()['main_position'].isin(selected_positions)) &
        (df_players.reset_index()['minutes_played'] >= minimum_minutes) &
        (df_players.reset_index()['minutes_played'] <= maximum_minutes) &
        (df_players.reset_index()['market_value_mio_eur'] >= minimum_marketval) & #| (df_players.reset_index()['market_value_mio_eur'].isna())) &
        (df_players.reset_index()['market_value_mio_eur'] <= maximum_marketval) & #| (df_players.reset_index()['market_value_mio_eur'].isna())) &
        (df_players.reset_index()['type_name'].isin(selected_type))
    ][
        ['league', 'season', 'team', 'player_name', 'main_position', 'minutes_played', 'market_value_mio_eur', 'type_name', 'vaep_total', 'vaep90', 'off_total', 'def_total', 'off90', 'vaep_stability']
        ].copy()


    st.dataframe(
        df_filtered,
        column_config={
            "league": st.column_config.TextColumn(
                "League",
            ),
            "season": st.column_config.TextColumn(
                "Season",
            ),
            "team": st.column_config.TextColumn(
                "Team",
            ),
            "player_name": st.column_config.TextColumn(
                "Player",
            ),
            "main_position": st.column_config.TextColumn(
                "Position",
            ),
            "minutes_played": st.column_config.NumberColumn(
                "Minutes Played",
                format="%d",
            ),
           "market_value_mio_eur": st.column_config.NumberColumn(
                "Market Value (€m)",
                format="%.1f",
            ),
            "type_name": st.column_config.TextColumn(
                "Type",
            ),
            "vaep_total": st.column_config.NumberColumn(
                "VAEP (Total)",
                format="%.2f",
            ),
            "vaep90": st.column_config.NumberColumn(
                "VAEP per 90",
                format="%.2f",
            ),
            "off_total": st.column_config.NumberColumn(
                "Offensive VAEP (Total)",
                format="%.2f",
            ),
            "def_total": st.column_config.NumberColumn(
                "Defensive VAEP (Total)",
                format="%.2f",
            ),
            "off90": st.column_config.NumberColumn(
                "Offensive VAEP per 90",
                format="%.2f",
            ),
            "vaep_stability": st.column_config.NumberColumn(
                "VAEP Stability",
                format="%.2f",
            ),
        },
     )

with tab2:

    selected_player = st.multiselect(
        "Select Player to compare visually", df_players.reset_index()['player_name'].unique().tolist()
    )

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.stripplot(x='vaep90', y='type_name', data=df_filtered, ax=ax)

    _HIGHLIGHT_COLORS = ['red', 'limegreen', 'orange', 'purple', 'deeppink', 'gold']

    df_selected_players = df_filtered[df_filtered['player_name'].isin(selected_player)]

    palette = {
        name: _HIGHLIGHT_COLORS[i % len(_HIGHLIGHT_COLORS)]
        for i, name in enumerate(selected_player)
    }

    sns.scatterplot(
        x='vaep90',
        y='type_name',
        data=df_selected_players,
        hue='player_name',
        palette=palette,
        s=100,
        zorder=5,
        ax=ax
    )
    top_per_type = (
        df_filtered
        .reset_index()
        .loc[df_filtered.reset_index().groupby("type_name")["vaep90"].idxmax()]
    )

    for _, row in top_per_type.iterrows():
        ax.annotate(
            row["player_name"],
            xy=(row["vaep90"], row["type_name"]),
            xytext=(6, 0), textcoords="offset points",
            va="center", fontsize=15
        )

    st.pyplot(fig)

    plt.close(fig)