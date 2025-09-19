import matplotlib.pyplot as plt
import networkx as nx

# Create a directed graph
G = nx.DiGraph()

# Define states
states = {
    "S0": "S0\n(2 days left)",
    "S1": "S1\n(1 day left)",
    "Rdone": "Research Done",
    "Adone": "Assignment Done",
    "BothDone": "Both Done"
}

# Add nodes
for s, label in states.items():
    G.add_node(s, label=label)

# Add transitions with actions and probabilities
edges = [
    ("S0", "Rdone", "Research, p=0.5"),
    ("S0", "S1", "Research, p=0.5"),
    ("S0", "Adone", "Assignment, p=0.9"),
    ("S0", "S1", "Assignment, p=0.1"),
    
    ("S1", "Rdone", "Research, p=0.5"),
    ("S1", "BothDone", "Research, p=0.5"),
    ("S1", "Adone", "Assignment, p=0.9"),
    ("S1", "BothDone", "Assignment, p=0.1"),
]

for u, v, label in edges:
    G.add_edge(u, v, label=label)

# Layout (manual for clarity)
pos = {
    "S0": (0, 0),
    "S1": (2, 0),
    "Rdone": (2, 1.5),
    "Adone": (4, 0.5),
    "BothDone": (4, -1)
}

# Draw nodes
nx.draw_networkx_nodes(G, pos, node_size=2500, node_color="lightblue", edgecolors="black")

# Draw edges
nx.draw_networkx_edges(G, pos, arrowstyle="->", arrowsize=15, edge_color="gray", width=2)

# Node labels
labels = nx.get_node_attributes(G, 'label')
nx.draw_networkx_labels(G, pos, labels, font_size=9)

# Edge labels
edge_labels = nx.get_edge_attributes(G, 'label')
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=7)

plt.title("Finite MDP for Student A", fontsize=12)
plt.axis("off")
plt.show()
