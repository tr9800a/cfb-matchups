import streamlit as st
import pandas as pd
import networkx as nx
import data
import graph
import utils
from analysis import stats_sor, stats_sos, stats_standard, graph_analysis

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="CFB Analytics Engine",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS STYLING ---
st.markdown("""
<style>
    .metric-card {
        background-color: #0E1117;
        border: 1px solid #303030;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
    .stDataFrame { font-size: 14px; }
    div[data-testid="stExpander"] details summary p {
        font-size: 1.2rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if 'start_year' not in st.session_state:
    st.session_state.start_year = 2024
if 'end_year' not in st.session_state:
    st.session_state.end_year = 2024

# --- HELPER FUNCTIONS ---
def get_game_score(g, side):
    """Safely retrieves points/score from game dict."""
    if side == 'home':
        return g.get('home_points') if g.get('home_points') is not None else g.get('home_score')
    else:
        return g.get('away_points') if g.get('away_points') is not None else g.get('away_score')

def get_tier_label(tier_num):
    labels = {
        1: "P4", 2: "G5", 3: "FCS Pwr", 
        4: "FCS Std", 5: "D2 Pwr", 6: "D2 Std", 
        7: "D3 Pwr", 8: "D3 Std"
    }
    return labels.get(tier_num, f"T{tier_num}")

def render_chain(G, path, start_year, end_year):
    """Renders a formatted connection chain between teams in the path."""
    st.markdown(f"**🔗 Connection Chain ({start_year}-{end_year})**")
    
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        
        # Retrieve Edge History
        if G.has_edge(u, v):
            history = G[u][v]['history']
            valid_history = [g for g in history if start_year <= g['season'] <= end_year]
            
            if not valid_history:
                st.warning(f"{u} vs {v} (No games in this range, but connected in graph)")
                continue

            series_summary = graph_analysis.get_series_summary(u, v, valid_history)
            
            # Get Most Recent Game
            valid_history.sort(key=lambda x: x['season'], reverse=True)
            last_g = valid_history[0]
            hs = get_game_score(last_g, 'home')
            as_ = get_game_score(last_g, 'away')
            
            st.markdown(f"**{i+1}. {u} vs {v}**")
            st.caption(f"Last Met: {last_g['season']} • Result: {last_g['home_team']} {hs} - {last_g['away_team']} {as_}")
            st.text(f"Series: {series_summary}")
        else:
            st.error(f"Broken Link: {u} and {v} are not connected.")
        st.divider()

# --- CACHED DATA LOADING ---
@st.cache_resource(show_spinner="Loading Game Database...")
def load_all_games():
    return data.load_games_data()

@st.cache_resource(show_spinner="Building Graph...")
def get_graph(_games, start_year, end_year, div_filter, include_postseason, non_conf):
    if not _games: return nx.Graph()
    
    filtered_games = [g for g in _games if start_year <= g['season'] <= end_year]
    
    if not include_postseason:
        filtered_games = [g for g in filtered_games if g.get('season_type') == 'regular']
    if non_conf:
        filtered_games = [g for g in filtered_games if not g.get('conference_game')]

    div_set = data.get_team_filter(div_filter)
    G = graph.build_graph(filtered_games, fbs_filter_set=div_set)
    return G

@st.cache_data
def get_season_stats():
    return data.load_season_stats()

@st.cache_data
def run_sor_analysis(_G, start, end, _stats, start_week, end_week):
    return stats_sor.calculate_complex_sor(
        _G, start, end, _stats, target_team=None, start_week=start_week, end_week=end_week
    )

# --- CALLBACKS ---
def set_years(start, end):
    st.session_state.start_year = start
    st.session_state.end_year = end

# --- MAIN APP ---
def main():
    st.title("🏈 CFB Advanced Analytics Engine")
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Configuration")
        view = st.radio(
            "Select Module", 
            ["Leaderboards (SOR)", "Team Deep Dive", "Connection Chains", "Network Topology", "Conference Analysis"]
        )
        st.divider()
        
        st.write("### Season Range")
        b1, b2 = st.columns(2)
        with b1: 
            st.button("All Time", on_click=set_years, args=(1869, 2025), use_container_width=True)
        with b2: 
            st.button("AP Era", on_click=set_years, args=(1936, 2025), use_container_width=True)
            
        c1, c2 = st.columns(2)
        with c1: st.number_input("Start", 1869, 2025, key="start_year")
        with c2: st.number_input("End", 1869, 2025, key="end_year")
            
        with st.expander("Advanced Filters"):
            include_postseason = st.checkbox("Include Postseason", False)
            non_conf_only = st.checkbox("Non-Conference Only", False)
            week_range = st.slider("Week Range", 0, 20, (0, 16))
            divisions = st.multiselect("Divisions", ['fbs', 'fcs', 'ii', 'iii'], default=['fbs', 'fcs', 'ii', 'iii'])
            div_param = divisions if divisions else ['fbs']

    start_year = st.session_state.start_year
    end_year = st.session_state.end_year

    # --- LAZY LOADING ---
    if view in ["Leaderboards (SOR)", "Team Deep Dive", "Connection Chains", "Conference Analysis", "Network Topology"]:
        all_games = load_all_games()
        G = get_graph(all_games, start_year, end_year, div_param, include_postseason, non_conf_only)
        stats_db = get_season_stats()
        
        # Ensure stats_sor has the updated maps
        stats_sor.CONF_TIER_MAP.update({
            'Big Six': 1, 'Big 6': 1,
            'Big Seven': 1, 'Big 7': 1,
            'Southwest': 1, 'Southwest Conference': 1,
            'Big 12': 1, 'Big 12 Conference': 1,
            'SEC': 1, 'Southeastern': 1, 'Southeastern Conference': 1
        })

    # --- VIEW 1: LEADERBOARDS (SOR) ---
    if view == "Leaderboards (SOR)":
        st.subheader(f"🏆 Strength of Record Leaderboard ({start_year}-{end_year})")
        
        if st.button("Run Analysis", type="primary"):
            with st.spinner("Running Recursive Algorithm..."):
                results = run_sor_analysis(G, start_year, end_year, stats_db, week_range[0], week_range[1])
                
                valid_data = []
                if results:
                    # 1. Determine tier membership based on LAST season in range
                    # Each tier should be evaluated individually based on membership in the last filtered season
                    tier_teams = {t: [] for t in range(1, 9)}  # Teams that belong to each tier
                    team_tier_map = {}  # Cache tier assignments
                    
                    for r in results:
                        team = r['team']
                        # Get last regular season membership for this team
                        last_conf, last_class, last_year = data.get_last_regular_season_membership(
                            team, start_year, end_year
                        )
                        
                        if last_conf and last_class:
                            # Determine which tier this team belongs to based on last season
                            tier = stats_sor.get_team_tier(team, last_conf, last_class)
                            team_tier_map[team] = tier
                            if tier in tier_teams:
                                tier_teams[tier].append(r)
                        else:
                            # Fallback: use tier from calculation (historical average)
                            tier = r['tier']
                            team_tier_map[team] = tier
                            if tier in tier_teams:
                                tier_teams[tier].append(r)
                    
                    # 2. Calculate max games per tier (only for teams in that tier)
                    tier_max_games = {}
                    for tier, team_results in tier_teams.items():
                        if team_results:
                            tier_max_games[tier] = max(r['games'] for r in team_results)
                    
                    # 3. Apply tier-specific threshold (60% of leader for that tier)
                    for r in results:
                        team = r['team']
                        tier = team_tier_map.get(team, r['tier'])
                        
                        leader_games = tier_max_games.get(tier, 0)
                        # Require 60% of the leader's volume for that specific tier
                        threshold = max(4, int(leader_games * 0.6))
                        
                        if r['games'] >= threshold:
                            # Update the tier in the result to match the determined tier
                            r['tier'] = tier
                            valid_data.append(r)
                            
                    st.caption(f"Applied Tier-Specific Thresholds (60% of leader per tier). e.g., P4 Leader: {tier_max_games.get(1,0)}, D3 Leader: {tier_max_games.get(7,0)}")
                
                # 3. Sort & Rank the unified list
                valid_data.sort(key=lambda x: x['sor'], reverse=True)
                for i, r in enumerate(valid_data):
                    r['rank'] = i + 1

                # --- BUILD EXTREMES TABLE (From Valid Data Only) ---
                st.markdown("### 📊 Tier Extremes (Best & Worst)")
                
                tier_groups = {t: [] for t in range(1, 9)} # Initialize all 8 tiers
                for r in valid_data:
                    t = r['tier']
                    if t in tier_groups: tier_groups[t].append(r)
                
                tier_extremes = []
                for t in range(1, 9):
                    teams = tier_groups[t]
                    t_label = get_tier_label(t)
                    
                    if teams:
                        best = teams[0]
                        worst = teams[-1]
                        tier_extremes.append({
                            "Tier": t_label,
                            "Best Team": f"#{best['rank']} {best['team']} ({best['w']}-{best['l']})",
                            "Best Score": round(best['sor'], 1),
                            "Worst Team": f"#{worst['rank']} {worst['team']} ({worst['w']}-{worst['l']})",
                            "Worst Score": round(worst['sor'], 1)
                        })
                    else:
                        tier_extremes.append({
                            "Tier": t_label,
                            "Best Team": "-", "Best Score": "-",
                            "Worst Team": "-", "Worst Score": "-"
                        })
                
                st.dataframe(pd.DataFrame(tier_extremes), hide_index=True, use_container_width=True)
                st.divider()

                # --- BUILD GLOBAL LEADERBOARD (From Valid Data Only) ---
                st.markdown("### 🌍 Global Rankings")
                
                df_data = []
                for r in valid_data:
                    df_data.append({
                        "Rank": r['rank'],
                        "Team": r['team'],
                        "Tier": get_tier_label(r['tier']),
                        "SOR": round(r['sor'], 2),
                        "Record": f"{r['w']}-{r['l']}",
                        "Diff": r['diff'],
                        "Games": r['games']
                    })
                
                df = pd.DataFrame(df_data)
                st.dataframe(
                    df,
                    column_order=("Rank", "Team", "Tier", "SOR", "Record", "Diff", "Games"),
                    column_config={
                        "SOR": st.column_config.NumberColumn("SOR Score", format="%.1f"),
                        "Diff": st.column_config.NumberColumn("Point Diff", format="%+d")
                    },
                    hide_index=True, use_container_width=True, height=800
                )
                
    # --- VIEW 2: TEAM DEEP DIVE ---
    elif view == "Team Deep Dive":
        st.subheader("🕵️ Individual Team Report")
        all_teams = sorted(list(G.nodes))
        default_ix = all_teams.index("Oregon") if "Oregon" in all_teams else 0
        target_team = st.selectbox("Select Team", all_teams, index=default_ix)
        
        if target_team:
            col1, col2, col3, col4 = st.columns(4)
            with st.spinner(f"Analyzing {target_team}..."):
                sor_data = stats_sor.calculate_complex_sor(
                    G, start_year, end_year, stats_db, target_team=target_team,
                    start_week=week_range[0], end_week=week_range[1]
                )
            
            if sor_data:
                d = sor_data[0]
                with col1: st.metric("Record", f"{d['w']}-{d['l']}")
                with col2: st.metric("SOR Score", f"{d['sor']:.1f}")
                with col3: st.metric("Tier", get_tier_label(d['tier']))
                with col4: st.metric("Point Diff", f"{d['diff']:+}")
                st.divider()
                
                st.write("#### Game Grades")
                games_df = []
                for g in d['details']:
                    games_df.append({
                        "Year": g['year'],
                        "Opponent": g['opp'],
                        "Result": g['result'],
                        "Grade": round(g['grade'], 1),
                        "Modifiers": g['mods']
                    })
                st.dataframe(pd.DataFrame(games_df).sort_values(by="Year", ascending=False), use_container_width=True)
                
                with st.expander("Show Network Topology (Furthest Connection)"):
                    st.caption(f"Calculating path using games played between {start_year} and {end_year}")
                    if st.button("Calculate Eccentricity"):
                        try:
                            lengths = nx.single_source_shortest_path_length(G, target_team)
                            max_dist = max(lengths.values())
                            furthest = [n for n, dist in lengths.items() if dist == max_dist]
                            target_node = furthest[0]
                            path = nx.shortest_path(G, target_team, target_node)
                            st.info(f"The furthest teams from {target_team} are {max_dist} degrees away.")
                            render_chain(G, path, start_year, end_year)
                        except Exception as e:
                            st.error(f"Error: {e}")

    # --- VIEW 3: CONNECTION CHAINS ---
    elif view == "Connection Chains":
        st.subheader("🔗 6 Degrees of Separation")
        st.caption(f"Finding connections using games played between {start_year} and {end_year}")
        col1, col2 = st.columns(2)
        with col1: team_a = st.selectbox("Start Team", sorted(list(G.nodes)), key="t1")
        with col2: team_b = st.selectbox("End Team", sorted(list(G.nodes)), index=1, key="t2")
            
        if st.button("Find Path"):
            try:
                path = nx.shortest_path(G, team_a, team_b)
                st.success(f"Found path with {len(path)-1} degrees of separation!")
                render_chain(G, path, start_year, end_year)
            except nx.NetworkXNoPath:
                st.error("No connection found between these teams.")

    # --- VIEW 4: NETWORK TOPOLOGY ---
    elif view == "Network Topology":
        st.subheader("🕸️ Network Topology & Diameter")
        st.caption(f"Analyzing structure based on games played between {start_year} and {end_year}")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("Total Nodes", len(G.nodes))
            st.metric("Total Edges", len(G.edges))
        with col2:
            if st.button("Calculate League Diameter"):
                with st.spinner("Analyzing graph connectivity..."):
                    if nx.is_connected(G):
                        G_target = G
                    else:
                        st.warning("Graph is disconnected. Analyzing Largest Component only.")
                        G_target = G.subgraph(max(nx.connected_components(G), key=len))
                    
                    diam = nx.diameter(G_target)
                    st.metric("Diameter", f"{diam} Degrees")
                    
                    periphery = nx.periphery(G_target)
                    path = []
                    found = False
                    for i in range(len(periphery)):
                        if found: break
                        for j in range(i+1, len(periphery)):
                            try:
                                p = nx.shortest_path(G_target, periphery[i], periphery[j])
                                if len(p)-1 == diam:
                                    path = p
                                    found = True
                                    break
                            except: continue
                    
                    if path:
                        st.success(f"Longest Path: {path[0]} ↔ {path[-1]}")
                        with st.expander("Show Full Chain", expanded=True):
                            render_chain(G, path, start_year, end_year)

    # --- VIEW 5: CONFERENCE ANALYSIS ---
    elif view == "Conference Analysis":
        st.subheader("⚔️ Conference Showdown")
        confs = ["SEC", "Big Ten", "Big 12", "ACC", "Pac-12", "American Athletic", "Mountain West", "Sun Belt", "MAC", "Conference USA", "SWC", "Big Eight", "Big East", "Ivy"]
        c1 = st.selectbox("Conference 1", confs, index=0)
        c2 = st.selectbox("Conference 2", confs, index=0)
        
        if st.button("Analyze Matchups"):
            c1_teams = data.get_teams_in_conference_range(c1, start_year, end_year)
            c2_teams = data.get_teams_in_conference_range(c2, start_year, end_year)
            
            matchups = []
            c1_wins = 0
            c2_wins = 0
            ties = 0
            c1_points = 0
            c2_points = 0
            
            all_games_flat = []

            for t1 in c1_teams:
                if t1 not in G: continue
                for t2 in c2_teams:
                    if t2 not in G: continue
                    if G.has_edge(t1, t2):
                        h = G[t1][t2]['history']
                        wins=0; losses=0; t=0
                        
                        for g in h:
                            if start_year <= g['season'] <= end_year:
                                # Determine score
                                s1 = get_game_score(g, 'home') if g.get('home') == t1 or g.get('home_team') == t1 else get_game_score(g, 'away')
                                s2 = get_game_score(g, 'away') if g.get('home') == t1 or g.get('home_team') == t1 else get_game_score(g, 'home')
                                
                                if s1 is None or s2 is None: continue
                                
                                # Aggregate Stats
                                c1_points += s1
                                c2_points += s2
                                
                                winner = None
                                if s1 > s2: 
                                    wins+=1
                                    c1_wins+=1
                                    winner = c1
                                elif s2 > s1: 
                                    losses+=1
                                    c2_wins+=1
                                    winner = c2
                                else: 
                                    t+=1
                                    ties+=1
                                
                                all_games_flat.append({
                                    "season": g['season'],
                                    "week": g.get('week', 0),
                                    "winner": winner
                                })

                        if wins+losses+t > 0:
                            matchups.append({
                                "Team 1": t1, "Team 2": t2, 
                                "Record": f"{wins}-{losses}-{t}", 
                                "Total": wins+losses+t
                            })
            
            # --- SUMMARY METRICS ---
            total_games = c1_wins + c2_wins + ties
            if total_games > 0:
                # 1. Streaks
                # Sort games by Season then Week
                all_games_flat.sort(key=lambda x: (x['season'], x['week']))
                
                max_c1_streak = 0
                max_c2_streak = 0
                curr_c1 = 0
                curr_c2 = 0
                
                for g in all_games_flat:
                    if g['winner'] == c1:
                        curr_c1 += 1
                        curr_c2 = 0
                        max_c1_streak = max(max_c1_streak, curr_c1)
                    elif g['winner'] == c2:
                        curr_c2 += 1
                        curr_c1 = 0
                        max_c2_streak = max(max_c2_streak, curr_c2)
                    else: # Tie breaks streak
                        curr_c1 = 0
                        curr_c2 = 0
                
                # 2. Display Metrics
                st.markdown("### 📊 Head-to-Head Summary")
                m1, m2, m3, m4 = st.columns(4)
                
                c1_pct = (c1_wins / total_games) * 100
                c2_pct = (c2_wins / total_games) * 100
                
                with m1:
                    st.metric(label=f"Wins ({c1})", value=c1_wins, delta=f"{c1_pct:.1f}%")
                with m2:
                    st.metric(label=f"Wins ({c2})", value=c2_wins, delta=f"{c2_pct:.1f}%")
                with m3:
                    diff = c1_points - c2_points
                    st.metric(label="Point Differential", value=f"{diff:+}", help=f"{c1} Points - {c2} Points")
                with m4:
                    st.metric(label=f"Longest Streak ({c1})", value=max_c1_streak, help=f"Longest consecutive win streak for {c1}")
                
                # Sub-metrics row
                s1, s2, s3, s4 = st.columns(4)
                with s1: st.caption(f"**Ties:** {ties}")
                with s2: st.caption(f"**Total Games:** {total_games}")
                with s3: 
                    avg_score_1 = c1_points / total_games
                    avg_score_2 = c2_points / total_games
                    st.caption(f"**Avg Score:** {avg_score_1:.1f} - {avg_score_2:.1f}")
                with s4:
                    st.metric(label=f"Longest Streak ({c2})", value=max_c2_streak)
                
                st.divider()

            if matchups:
                st.markdown("### 📜 Series Details")
                st.dataframe(pd.DataFrame(matchups).sort_values("Total", ascending=False), hide_index=True, use_container_width=True)
            else:
                st.warning("No matchups found between these conferences in this era.")

if __name__ == "__main__":
    main()