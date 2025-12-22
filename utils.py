import unicodedata

def normalize(text):
    """
    Removes accents, spaces, and casing for easy matching.
    """
    if not text: return ""
    text = unicodedata.normalize('NFD', text)
    text = "".join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.lower().replace(" ", "").replace("'", "").replace("-", "")

def resolve_team_name(graph, user_input):
    """
    Returns the official node name from the graph based on user input.
    """
    node_map = {normalize(node): node for node in graph.nodes()}
    return node_map.get(normalize(user_input))