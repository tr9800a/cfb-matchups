import networkx as nx
import utils

def get_game_score(g, side):
    """Safely retrieves points/score from game dict"""
    if side == 'home':
        return g.get('home_points') if g.get('home_points') is not None else g.get('home_score')
    else:
        return g.get('away_points') if g.get('away_points') is not None else g.get('away_score')

def get_series_summary(team1, team2, history):
    """Calculates the W-L-T record between two teams."""
    t1_wins = 0
    t2_wins = 0
    ties = 0
    
    for g in history:
        # Determine score for team1 and team2
        # Note: We have to check which side team1 was on
        is_home = (g.get('home_team') == team1 or g.get('home') == team1)
        
        s1 = get_game_score(g, 'home') if is_home else get_game_score(g, 'away')
        s2 = get_game_score(g, 'away') if is_home else get_game_score(g, 'home')
        
        if s1 is None or s2 is None: continue
        
        if s1 > s2: t1_wins += 1
        elif s2 > s1: t2_wins += 1
        else: ties += 1
        
    if t1_wins > t2_wins:
        return f"{team1} leads {t1_wins}-{t2_wins}-{ties}"
    elif t2_wins > t1_wins:
        return f"{team2} leads {t2_wins}-{t1_wins}-{ties}"
    else:
        return f"Series tied {t1_wins}-{t2_wins}-{ties}"

def print_league_diameter(G):
    print(f"[DIAMETER] Analyzing graph topology... (This may take a moment)", end='\r')
    
    if len(G.nodes) == 0:
        print("[DIAMETER] Graph is empty.")
        return

    # Diameter is only defined for connected graphs. 
    if not nx.is_connected(G):
        largest_cc = max(nx.connected_components(G), key=len)
        G = G.subgraph(largest_cc).copy()
        print(f"[DIAMETER] Graph disconnected. Analyzing largest component ({len(G.nodes)} nodes).")

    try:
        diameter = nx.diameter(G)
        print(f"[DIAMETER] Diameter found: {diameter}. finding path...", end='\r')
        
        # Find the specific path
        periphery = nx.periphery(G)
        longest_path = []
        found = False
        
        for i in range(len(periphery)):
            if found: break
            for j in range(i+1, len(periphery)):
                u, v = periphery[i], periphery[j]
                try:
                    path = nx.shortest_path(G, u, v)
                    if len(path) - 1 == diameter:
                        longest_path = path
                        found = True
                        break
                except:
                    continue
        
        if not longest_path:
            print(f"\n[DIAMETER] {diameter} Degrees (Could not reconstruct path)")
            return

        start_team = longest_path[0]
        end_team = longest_path[-1]
        
        print(f"\n[DIAMETER] {diameter} DEGREES OF SEPARATION")
        print(f"           {start_team} <--> {end_team}")
        print("="*80)
        
        for i in range(len(longest_path) - 1):
            t1 = longest_path[i]
            t2 = longest_path[i+1]
            
            history = G[t1][t2]['history']
            series_rec = get_series_summary(t1, t2, history)
            
            # Most recent game
            history.sort(key=lambda x: x['season'], reverse=True)
            g = history[0]
            
            h_score = get_game_score(g, 'home')
            a_score = get_game_score(g, 'away')
            
            print(f"{i+1}. {t1} vs {t2} ({series_rec})")
            print(f"   Last Met: {g['season']} ({g['home_team']} {h_score}, {g['away_team']} {a_score})")
            print("-" * 80)
            
    except Exception as e:
        print(f"\n[ERROR] Calculation failed: {e}")

def analyze_connection(G, team1_input, team2_input):
    """
    Finds the shortest path (Kevin Bacon style) between two teams.
    """
    t1 = utils.resolve_team_name(G, team1_input)
    t2 = utils.resolve_team_name(G, team2_input)
    
    if not t1 or not t2:
        print("Could not resolve team names.")
        return

    try:
        path = nx.shortest_path(G, t1, t2)
        degrees = len(path) - 1
        
        print(f"\n[CONNECTION] {t1} <--> {t2}")
        print(f"             {degrees} Degrees of Separation")
        print("="*80)
        
        for i in range(len(path) - 1):
            u = path[i]
            v = path[i+1]
            
            history = G[u][v]['history']
            series_rec = get_series_summary(u, v, history)
            
            # Get Most Recent Game
            history.sort(key=lambda x: x['season'], reverse=True)
            g = history[0]
            
            h_score = get_game_score(g, 'home')
            a_score = get_game_score(g, 'away')
            
            # Formatted Output
            print(f"{i+1}. {u} vs {v}")
            print(f"   Series: {series_rec}")
            print(f"   Last Met: {g['season']} ({g['home_team']} {h_score} - {g['away_team']} {a_score})")
            print("-" * 80)
            
    except nx.NetworkXNoPath:
        print(f"\n[NO PATH] No connection found between {t1} and {t2} in this dataset.")
    except Exception as e:
        print(f"Error: {e}")

def print_overall_stats(G):
    """
    Prints basic graph topology stats.
    """
    print(f"\n[GRAPH STATS] {len(G.nodes)} Teams, {len(G.edges)} Matchups")
    if len(G.nodes) > 0:
        density = nx.density(G)
        print(f"              Density: {density:.4f}")
        
        degrees = [d for n, d in G.degree()]
        avg_deg = sum(degrees) / len(degrees)
        print(f"              Avg Games/Opponents: {avg_deg:.1f}")
        
        # Connectivity
        num_components = nx.number_connected_components(G)
        if num_components == 1:
            print("              Graph is Fully Connected")
        else:
            largest = len(max(nx.connected_components(G), key=len))
            print(f"              Disconnected ({num_components} islands)")
            print(f"              Largest Cluster: {largest} teams")

def list_unplayed(G, centroid_input, universe_set):
    """
    Lists teams in the 'universe' (e.g., FBS) that the centroid has NEVER played.
    """
    center = utils.resolve_team_name(G, centroid_input)
    if not center: return

    played = set(G.neighbors(center))
    played.add(center)
    
    if not universe_set:
        universe_set = set(G.nodes())
        
    unplayed = [t for t in universe_set if t not in played and t in G.nodes()]
    unplayed.sort()
    
    print(f"\n[UNPLAYED] Teams {center} has never played ({len(unplayed)} found)")
    print("="*80)
    
    col_width = 25
    cols = 3
    for i in range(0, len(unplayed), cols):
        chunk = unplayed[i:i+cols]
        row = "".join(f"{t:<{col_width}}" for t in chunk)
        print(row)

def print_team_eccentricity(G, team_input):
    """
    Finds the 'Eccentricity' of a team (the furthest node from them in the graph).
    """
    t1 = utils.resolve_team_name(G, team_input)
    if not t1:
        print(f"Could not resolve team: {team_input}")
        return
    
    # 1. Calculate distance to ALL other teams
    try:
        lengths = nx.single_source_shortest_path_length(G, t1)
    except Exception as e:
        print(f"[ERROR] Could not calculate paths: {e}")
        return
    
    # 2. Find the max distance
    max_dist = 0
    farthest_teams = []
    
    for team, dist in lengths.items():
        if dist > max_dist:
            max_dist = dist
            farthest_teams = [team]
        elif dist == max_dist:
            farthest_teams.append(team)
            
    if max_dist == 0:
        print(f"[ECCENTRICITY] {t1} has no connections.")
        return

    # 3. Print Results
    target = farthest_teams[0]
    print(f"\n[ECCENTRICITY] Furthest connection from {t1}")
    print(f"               Max Distance: {max_dist} Degrees")
    print(f"               Teams at this distance: {len(farthest_teams)} (e.g., {target})")
    
    # Reuse the existing analysis to print the chain
    analyze_connection(G, t1, target)