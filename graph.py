import networkx as nx

def build_graph(games_data, fbs_filter_set=None):
    G = nx.Graph()

    if fbs_filter_set is None:
        fbs_filter_set = set()
    
    should_filter = len(fbs_filter_set) > 0

    for g in games_data:
        h = g['home_team']
        a = g['away_team']

        if should_filter:
            if h not in fbs_filter_set or a not in fbs_filter_set:
                continue

        # If edge exists, append to history. If not, initialize.
        if G.has_edge(h, a):
            G[h][a]['history'].append(g)
            if g['season'] > G[h][a]['last_met']:
                G[h][a]['last_met'] = g['season']
        else:
            G.add_edge(h, a, history=[g], last_met=g['season'])

    return G