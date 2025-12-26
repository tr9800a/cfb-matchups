import networkx as nx
import utils

def get_series_info(G, team_a, team_b):
    """
    Helper to format the connection string:
    <Team A> played <Team B> in <year> (<Away> AScore-HScore <Home>) <Team A> Series Record: W-L-T
    """
    if not G.has_edge(team_a, team_b):
        return "No history."
    
    history = G.get_edge_data(team_a, team_b)['history']
    if not history:
        return "No games found."
        
    # 1. Calculate Series Record for Team A
    wins = 0
    losses = 0
    ties = 0
    
    for g in history:
        if g.get('home_score') is None: continue
        
        s_home = g['home_score']
        s_away = g['away_score']
        
        # Determine if Team A won/lost
        if g['home'] == team_a:
            if s_home > s_away: wins += 1
            elif s_away > s_home: losses += 1
            else: ties += 1
        else: # team_a is away
            if s_away > s_home: wins += 1
            elif s_home > s_away: losses += 1
            else: ties += 1
            
    # 2. Get Last Game Details
    last = history[-1]
    year = last['season']
    
    # Format: (<Away Team> AScore-HScore <Home Team>)
    away_team = last['away']
    home_team = last['home']
    away_score = last['away_score']
    home_score = last['home_score']
    
    score_str = f"({away_team} {away_score}-{home_score} {home_team})"
    record_str = f"{team_a} Series Record: {wins}-{losses}-{ties}"
    
    return f"{team_a} played {team_b} in {year} {score_str} {record_str}"

def analyze_connection(G, centroid, target):
    c = utils.resolve_team_name(G, centroid)
    t = utils.resolve_team_name(G, target)
    if not c or not t: return
    
    print(f"\n[CONNECTION] {c} -> {t}")
    
    if G.has_edge(c, t):
        # Direct Connection
        msg = get_series_info(G, c, t)
        print(f"   {msg}")
    else:
        # Chain Connection
        try:
            path = nx.shortest_path(G, source=c, target=t)
            print(f"   Chain ({len(path)-1} Degrees):")
            
            for i in range(len(path)-1):
                u = path[i]
                v = path[i+1]
                msg = get_series_info(G, u, v)
                print(f"   {i+1}. {msg}")
                
        except nx.NetworkXNoPath:
            print("   No connection found.")
        except Exception as e:
            print(f"   Error finding path: {e}")

def list_unplayed(G, centroid, universe):
    c = utils.resolve_team_name(G, centroid)
    if not c: return
    played = set(G.neighbors(c))
    valid = {t for t in universe if G.has_node(t)}
    never = sorted(list(valid - played - {c}))
    print(f"\n[UNPLAYED] {c} has never played {len(never)} teams:")
    if never:
        col = max(len(t) for t in never)+2
        for i in range(0, len(never), 3):
             print("".join(w.ljust(col) for w in never[i:i+3]))

def print_league_diameter(G):
    if not nx.is_connected(G): G = G.subgraph(max(nx.connected_components(G), key=len))
    print(f"\n[DIAMETER] {nx.diameter(G)} Degrees")

def print_overall_stats(G):
    print("\n[LEAGUE] Stats...")
    ms = sorted([{'m': f"{u} vs {v}", 'c': len(d['history'])} for u,v,d in G.edges(data=True)], key=lambda x: x['c'], reverse=True)
    print("\n[RIVALRIES] Most Played")
    for m in ms[:5]: print(f"   {m['m']:<40} | {m['c']}")