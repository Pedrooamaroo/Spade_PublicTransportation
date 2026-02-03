"""City graph model for the transport system.

Represents stations as nodes and roads as directed edges,
with weights and allowed vehicle types.
"""

import networkx as nx
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


class CityGraph:
    """
    Directed graph of the city.

    Stores the transport network topology, with edge weights
    and authorized vehicle types for each connection.
    """

    def __init__(self):
        """Creates an empty graph and the position structure for drawing."""
        self.graph = nx.DiGraph()
        self.pos = {}

    def create_sample_map(self):
        """Initializes the network of stations, routes, and map positions."""
        stations = [
            "Central",
            "North",
            "South",
            "East",
            "West",
            "Airport",
            "University",
            "Stadium",
            "GasStation",
        ]
        self.graph.add_nodes_from(stations)

        routes = [
            ("Central", "North", 10, ["bus", "tram"]),
            ("North", "Central", 10, ["bus", "tram"]),
            ("Central", "East", 10, ["bus", "tram"]),
            ("East", "Central", 10, ["bus", "tram"]),
            ("Central", "South", 12, ["bus"]),
            ("South", "Central", 12, ["bus"]),
            ("Central", "West", 8, ["tram"]),
            ("West", "Central", 8, ["tram"]),
            ("West", "North", 12, ["bus"]),
            ("North", "West", 12, ["bus"]),
            ("North", "East", 8, ["tram", "bus"]),
            ("East", "North", 8, ["tram", "bus"]),
            ("East", "Stadium", 6, ["tram"]),
            ("Stadium", "North", 7, ["tram"]),
            ("South", "University", 5, ["bus"]),
            ("University", "South", 5, ["bus"]),
            ("West", "University", 18, ["bus"]),
            ("University", "West", 18, ["bus"]),
            ("South", "Airport", 25, ["bus"]),
            ("Airport", "South", 25, ["bus"]),
            ("East", "Airport", 35, ["bus"]),
            ("Airport", "East", 35, ["bus"]),
            ("South", "GasStation", 5, ["bus"]),
            ("GasStation", "South", 5, ["bus"]),
        ]

        for start, end, weight, allowed in routes:
            self.graph.add_edge(start, end, weight=weight, base_weight=weight, allowed_types=allowed)

        self.pos = {
            "North": (0, 5),
            "Stadium": (4, 6),
            "West": (-5, 1),
            "Central": (0, 1),
            "East": (5, 1),
            "University": (-4, -5),
            "Airport": (6, -6),
            "South": (0, -4),
            "GasStation": (0, -6.5),
        }
        print("Map v5.1 (GasStation South) loaded.")

    def get_shortest_path(self, start_node, end_node, vehicle_type):
        """
        Returns the fastest path between two nodes for a vehicle type.

        Applies Dijkstra on a filtered view of the graph that excludes
        edges where the vehicle type is not allowed.

        Args:
            start_node (str): Origin node.
            end_node (str): Destination node.
            vehicle_type (str): Vehicle type ("bus" or "tram").

        Returns:
            list[str] | None: List of nodes in the shortest path,
            or None if no valid path exists.
        """

        def is_passable(u, v):
            edge_data = self.graph[u][v]
            return vehicle_type in edge_data.get("allowed_types", [])

        view = nx.subgraph_view(self.graph, filter_edge=is_passable)
        try:
            path = nx.shortest_path(
                view, source=start_node, target=end_node, weight="weight"
            )
            return path
        except nx.NetworkXNoPath:
            return None

    def get_total_time(self, path):
        """
        Calculates the total cost (time) of a path.

        Args:
            path (list[str]): Sequence of nodes in the graph.

        Returns:
            int | float: Sum of edge weights in the path.
        """
        if not path or len(path) < 2:
            return 0
        total_time = 0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            total_time += self.graph[u][v]["weight"]
        return total_time
    
    def get_total_distance(self, path):
        """Calculates total cost in DISTANCE."""
        if not path or len(path) < 2:
            return 0
        total = 0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            total += self.graph[u][v].get("base_weight", 10)
        return total

    def print_routes_table(self):
        """Prints a table with all routes, modes, and duration in minutes."""
        data = []
        for u, v, d in self.graph.edges(data=True):
            data.append(
                {
                    "Origin": u,
                    "Dest": v,
                    "Modes": ",".join(d["allowed_types"]),
                    "Min": d["weight"],
                }
            )
        print("\n--- ROUTES TABLE ---")
        print(pd.DataFrame(data).to_string(index=False))
        print("--------------------\n")

    def draw_smart_labels(self, ax, pos):
        """
        Draws cost labels on edges legibly.

        Places the weight value in the middle of each edge and handles
        cases of bidirectional edges to avoid text overlap.
        """
        processed_pairs = set()
        for u, v, d in self.graph.edges(data=True):
            if (u, v) in processed_pairs:
                continue
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

            if self.graph.has_edge(v, u):
                processed_pairs.add((v, u))
                ax.text(
                    cx,
                    cy,
                    f"{d['weight']}m",
                    ha="center",
                    va="center",
                    fontsize=9,
                    bbox=dict(
                        boxstyle="round,pad=0.2",
                        fc="white",
                        ec="#cccccc",
                        alpha=1.0,
                    ),
                    zorder=25,
                )
            else:
                ax.text(
                    cx,
                    cy,
                    f"{d['weight']}m",
                    ha="center",
                    va="center",
                    fontsize=8,
                    bbox=dict(
                        boxstyle="round,pad=0.2",
                        fc="white",
                        ec="none",
                        alpha=0.7,
                    ),
                    zorder=25,
                )

    def visualize(self):
        """Draws the city graph with legend for bus, tram, and mixed routes."""
        fig, ax = plt.subplots(figsize=(14, 12))
        mixed_edges = [
            (u, v)
            for u, v, d in self.graph.edges(data=True)
            if "bus" in d["allowed_types"] and "tram" in d["allowed_types"]
        ]
        bus_only_edges = [
            (u, v)
            for u, v, d in self.graph.edges(data=True)
            if "bus" in d["allowed_types"] and "tram" not in d["allowed_types"]
        ]
        tram_only_edges = [
            (u, v)
            for u, v, d in self.graph.edges(data=True)
            if "tram" in d["allowed_types"] and "bus" not in d["allowed_types"]
        ]

        curv_rad = 0.15
        arc_style = f"arc3, rad={curv_rad}"
        arrow_size = 25
        node_sz = 1000

        if mixed_edges:
            nx.draw_networkx_edges(
                self.graph,
                self.pos,
                edgelist=mixed_edges,
                edge_color="green",
                width=3,
                alpha=0.6,
                connectionstyle=arc_style,
                arrowsize=arrow_size,
                ax=ax,
            )
        if bus_only_edges:
            nx.draw_networkx_edges(
                self.graph,
                self.pos,
                edgelist=bus_only_edges,
                edge_color="blue",
                width=2,
                linestyle="dashed",
                alpha=0.7,
                connectionstyle=arc_style,
                arrowsize=arrow_size,
                ax=ax,
            )
        if tram_only_edges:
            nx.draw_networkx_edges(
                self.graph,
                self.pos,
                edgelist=tram_only_edges,
                edge_color="red",
                width=2,
                alpha=0.8,
                connectionstyle=arc_style,
                arrowsize=arrow_size,
                ax=ax,
            )

        self.draw_smart_labels(ax, self.pos)
        nx.draw_networkx_nodes(
            self.graph,
            self.pos,
            node_size=node_sz,
            node_color="white",
            edgecolors="#333333",
            linewidths=2,
            ax=ax,
        )
        nx.draw_networkx_labels(
            self.graph,
            self.pos,
            font_size=9,
            font_weight="bold",
            ax=ax,
        )

        plt.title("Transport Network with Gas Station", fontsize=16)
        from matplotlib.lines import Line2D

        legend_elements = [
            Line2D([0], [0], color="green", lw=3, label="Mixed"),
            Line2D([0], [0], color="blue", lw=2, linestyle="--", label="Bus"),
            Line2D([0], [0], color="red", lw=2, label="Tram"),
        ]
        ax.legend(handles=legend_elements, loc="upper right")
        plt.axis("off")
        plt.tight_layout()
        plt.show()