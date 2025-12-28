import data
import graph

print("--- DIAGNOSTIC START ---")

# 1. Check Data Loading & Patching
print("\n1. Loading Games...")
games = data.load_games_data()
print(f"   Loaded {len(games)} games.")

if len(games) > 0:
    # Find a 2024 game to check
    g24 = next((g for g in games if g['season'] == 2024), None)
    if g24:
        print(f"   Sample 2024 Game: {g24.get('home_team')} vs {g24.get('away_team')}")
        print(f"   Keys present: {list(g24.keys())[:10]}...")
        print(f"   'home_division' (Patched): {g24.get('home_division')}")
        print(f"   'home_classification' (Raw): {g24.get('home_classification')}")
        print(f"   'home' (Patched): {g24.get('home')}")
    else:
        print("   ⚠️ No 2024 games found in cache!")

# 2. Check FBS Filter
print("\n2. Testing FBS Filter...")
fbs_teams = data.get_team_filter(['fbs'])
print(f"   Found {len(fbs_teams)} FBS teams.")

# 3. Check Graph Building
print("\n3. Building Graph (2024)...")
games_2024 = [g for g in games if g['season'] == 2024]
G = graph.build_graph(games_2024, fbs_filter_set=fbs_teams)
print(f"   Graph Nodes: {len(G.nodes)}")
print(f"   Graph Edges: {len(G.edges)}")

if len(G.nodes) > 0:
    node = list(G.nodes)[0]
    print(f"   Sample Node: {node}")
    deg = G.degree[node]
    print(f"   Games played by {node}: {deg}")
    if deg < 10:
        print("   ⚠️ WARNING: Teams have fewer than 10 games. 'Min Games' filter will hide them.")
else:
    print("   ⚠️ Graph is empty!")

print("\n--- DIAGNOSTIC END ---")