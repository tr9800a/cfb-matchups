import streamlit as st
import pandas as pd
import networkx as nx
import plotly.express as px
from datetime import datetime

# Import local modules
import data
import graph
import utils
from analysis import stats_sor, stats_sos, graph_analysis

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="CFB Analytics Engine",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS TWEAKS ---
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #dcdcdc;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    div.block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# --- CACHED DATA LOADERS ---
@st.cache_data(show_spinner="Loading Game Database...")
def load_master_data():
    """Loads raw JSON data once."""
    games = data.load_games_data()
    stats_db = data.load_season_stats()
    teams_db = data.load_teams_data()
    return games, stats_db, teams_db

@st.cache_data(show_spinner="Building Master Graph...")
def get_master_graph(games):
    """Builds the FULL history graph once. Fast and reusable."""
    # We include ALL divisions for the master graph to ensure connectivity
    # Filters can be applied later on subgraphs
    return graph.build_graph(games)

# --- INITIALIZATION ---
raw_games, stats_db, teams_db = load_master_data()
MASTER_G = get_master_graph(raw_games)
ALL_TEAMS = sorted(list(MASTER_G.nodes()))

# --- SIDEBAR (Minimal Global Settings) ---
st.sidebar.title("🏈 CFB Engine")
st.sidebar.info(f"Loaded {len(raw_games):,} games and {len(ALL_TEAMS)} teams.")

# --- MAIN TABS ---
tab_sor, tab_net, tab_team, tab_sos = st.tabs([
    "🏆 SOR Leaderboards", 
    "🕸️ Network Lab", 
    "📊 Team Deep Dive",
    "💀 SOS Rankings"
])

# ==========================================
# TAB 1: SOR LEADERBOARD (Performance Optimized)
# ==========================================
with tab_sor:
    st.header("Strength of Record (SOR)")
    st.caption("The 'Resume Grader'. Asymmetric logic: big penalties for bad losses, small rewards for expected wins.")

    # 1. ISOLATED CONTROLS (Inside an expander to save space)
    with st.expander("⚙️ Analysis Settings", expanded=True):
        col1, col2, col3 = st.columns([2, 2, 2]) # Adjusted columns
        with col1:
            sor_years = st.slider("Season Range", 1980, 2024, (2024, 2024), key="sor_years")
        with col2:
            # NEW WEEK SLIDER
            # Weeks typically run 1 to ~16 (Reg Season) + 17-20 (Post)
            sor_weeks = st.slider("Week Range", 1, 20, (1, 20), key="sor_weeks")
        with col3:
            sor_divs = st.multiselect("Divisions", ['fbs', 'fcs', 'ii', 'iii'], default=['fbs', 'fcs'], key="sor_divs")
            sor_min_games = st.number_input("Min Games", 1, 15, 6, key="sor_min") # Lowered default min games

    if st.button("🚀 Run SOR Analysis", type="primary"):
        with st.spinner("Crunching the numbers..."):
            valid_teams_set = data.get_team_filter(sor_divs)
            
            # PASS THE WEEKS
            results = stats_sor.calculate_complex_sor(
                MASTER_G, sor_years[0], sor_years[1], stats_db,
                start_week=sor_weeks[0], end_week=sor_weeks[1]
            )

    # 2. RUN BUTTON (Prevents auto-reload loop)
    if st.button("🚀 Run SOR Analysis", type="primary"):
        with st.spinner("Crunching the numbers..."):
            # Filter Graph LOCALLY
            valid_teams_set = data.get_team_filter(sor_divs)
            
            # Run Algorithm
            results = stats_sor.calculate_complex_sor(
                MASTER_G, sor_years[0], sor_years[1], stats_db
            )
            
            # Process Data
            df = pd.DataFrame(results)
            if not df.empty:
                # Filter Logic
                df = df[df['games'] >= sor_min_games]
                df = df[df['team'].isin(valid_teams_set)] if valid_teams_set else df
                
                # Add Rank
                df = df.sort_values(by="sor", ascending=False).reset_index(drop=True)
                df.index += 1
                df['Rank'] = df.index
                
                # Create "Record" String
                df['Record'] = df['w'].astype(str) + "-" + df['l'].astype(str)

                # --- DIVISION EXTREMES ---
                st.subheader("📊 Division Leaders & Trailers")
                cols = st.columns(len(sor_divs))
                
                df['div_clean'] = df['div'].str.lower()
                for i, d in enumerate(sor_divs):
                    d_clean = d.lower()
                    div_df = df[df['div_clean'] == d_clean]
                    if not div_df.empty and i < len(cols):
                        best = div_df.iloc[0]
                        worst = div_df.iloc[-1]
                        with cols[i]:
                            st.markdown(f"**{d.upper()}**")
                            # Added Rank/Record to these cards too
                            st.success(f"#{best['Rank']} {best['team']} ({best['Record']})")
                            st.error(f"#{worst['Rank']} {worst['team']} ({worst['Record']})")
                
                st.divider()

                # --- MAIN TABLE ---
                st.subheader(f"Global Rankings ({len(df)} teams)")
                st.dataframe(
                    # Added Rank and Record to this list
                    df[['Rank', 'team', 'div', 'Record', 'sor', 'games', 'diff']],
                    column_config={
                        "Rank": st.column_config.NumberColumn("Rank", format="%d", width="small"),
                        "sor": st.column_config.NumberColumn("Score", format="%.2f"),
                        "div": st.column_config.TextColumn("Div", width="small"),
                        "team": "Team",
                        "Record": "Record",
                        "games": st.column_config.NumberColumn("Gms", width="small"),
                        "diff": "Diff"
                    },
                    use_container_width=True,
                    height=600
                )
            else:
                st.warning("No teams found matching these criteria.")

# ==========================================
# TAB 2: NETWORK LAB (Full Connectivity)
# ==========================================
with tab_net:
    st.header("🕸️ The Connection Lab")
    st.caption("Search the entire history of college football (1869-Present). No date filters apply here.")
    
    colA, colB = st.columns(2)
    with colA:
        p1 = st.selectbox("Start Team", ALL_TEAMS, index=ALL_TEAMS.index("Oregon") if "Oregon" in ALL_TEAMS else 0)
    with colB:
        p2 = st.selectbox("End Team", ALL_TEAMS, index=ALL_TEAMS.index("Mount Union") if "Mount Union" in ALL_TEAMS else 0)

    col_act1, col_act2 = st.columns([1, 4])
    
    if col_act1.button("Find Connection"):
        try:
            path = nx.shortest_path(MASTER_G, source=p1, target=p2)
            st.success(f"🔗 Connected in {len(path)-1} Degrees!")
            
            for i in range(len(path)-1):
                u = path[i]
                v = path[i+1]
                msg = graph_analysis.get_series_info(MASTER_G, u, v)
                st.info(f"{i+1}. {msg}")
                
        except nx.NetworkXNoPath:
            st.error("🚫 These teams have never been connected (Infinite degrees of separation).")

    # --- RESTORED: DIAMETER ---
    st.divider()
    if st.button("📏 Calculate Longest Chain (Graph Diameter)"):
        with st.spinner("Analyzing graph topology (this is heavy)..."):
            # Get largest component first
            largest_cc = max(nx.connected_components(MASTER_G), key=len)
            S = MASTER_G.subgraph(largest_cc)
            diam = nx.diameter(S)
            st.metric("Max Degrees of Separation", f"{diam} Degrees")

# ==========================================
# TAB 3: TEAM DEEP DIVE
# ==========================================
with tab_team:
    st.header("Team Report Card")
    
    col_t1, col_t2, col_t3 = st.columns([3, 1, 2]) # Added col
    target_team = col_t1.selectbox("Select Team", ALL_TEAMS, key="dd_team")
    dd_year = col_t2.number_input("Season", 1869, 2025, 2024)
    # Optional Week Filter for Deep Dive
    dd_weeks = col_t3.slider("Weeks", 1, 20, (1, 20), key="dd_weeks")
    
    if st.button("Generate Report"):
        # Update Call
        sor_data = stats_sor.calculate_complex_sor(
            MASTER_G, dd_year, dd_year, stats_db, target_team=target_team,
            start_week=dd_weeks[0], end_week=dd_weeks[1]
        )
        
        if sor_data:
            d = sor_data[0]
            
            # Top Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("SOR Score", f"{d['sor']:.2f}")
            m2.metric("Record", f"{d['w']}-{d['l']}")
            m3.metric("Pt Diff", f"{d['diff']:+}")
            m4.metric("SOS Rank", "N/A") # Placeholder
            
            # Visuals
            st.subheader("Game Grades")
            
            df_log = pd.DataFrame(d['details'])
            if not df_log.empty:
                # Color code bar chart
                df_log['Color'] = df_log['grade'].apply(lambda x: 'green' if x > 0 else 'red')
                
                fig = px.bar(
                    df_log, x='opp', y='grade',
                    text='result',
                    color='grade',
                    color_continuous_scale='RdYlGn',
                    title=f"{target_team} ({dd_year}) Game Performance"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    df_log[['year', 'opp', 'opp_div', 'result', 'grade', 'mods']],
                    use_container_width=True
                )
        else:
            st.warning(f"No games found for {target_team} in {dd_year}.")

# ==========================================
# TAB 4: SOS RANKINGS
# ==========================================
with tab_sos:
    st.header("Strength of Schedule (SOS)")
    
    with st.form("sos_form"):
        col1, col2 = st.columns(2)
        sos_year = col1.number_input("Season", 1900, 2025, 2024)
        sos_div = col2.selectbox("Division", ['fbs', 'fcs', 'ii', 'iii'], index=0)
        
        run_sos = st.form_submit_button("Calculate SOS")
    
    if run_sos:
        with st.spinner(f"Ranking schedules for {sos_year}..."):
            div_teams = data.get_team_filter([sos_div])
            candidates = [t for t in div_teams if MASTER_G.has_node(t)]
            
            results = []
            progress = st.progress(0)
            
            for i, team in enumerate(candidates):
                s = stats_sos.calculate_sos(MASTER_G, team, sos_year, sos_year, False, stats_db)
                if s and s['n_games'] >= 6:
                    # Look up Team's own Record (W-L)
                    team_stats = data.get_team_stats(team, sos_year, stats_db)
                    rec_str = f"{team_stats['w']}-{team_stats['l']}"
                    
                    results.append(s | {'team': team, 'Record': rec_str})
                
                if i % 10 == 0: progress.progress(i / len(candidates))
            
            progress.empty()
            
            if results:
                df_sos = pd.DataFrame(results).sort_values("weighted_score", ascending=False)
                df_sos = df_sos.reset_index(drop=True)
                df_sos.index += 1
                df_sos['Rank'] = df_sos.index
                
                st.dataframe(
                    df_sos[['Rank', 'team', 'Record', 'weighted_score', 'n_games', 'n_ranked']],
                    column_config={
                        "Rank": st.column_config.NumberColumn("Rank", format="%d", width="small"),
                        "weighted_score": st.column_config.NumberColumn("SOS Score", format="%.2f"),
                        "n_ranked": "Ranked Opps",
                        "Record": "Record"
                    },
                    use_container_width=True
                )