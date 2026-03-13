"""
Similarity Graph Visualizer

Parses pairwise similarity scores and renders an interactive force-directed
graph where edge thickness reflects how similar (suspicious) two submissions are.

Usage:
    python similarity_graph.py data.txt                     # all edges, PNG output
    python similarity_graph.py data.txt --threshold 0.5     # only edges below 0.5
    python similarity_graph.py data.txt --format svg        # export as SVG
    python similarity_graph.py data.txt -o my_graph.pdf     # custom output filename
    python similarity_graph.py data.txt --short-labels 20   # truncate labels to 20 chars
"""

import argparse
import re
import sys
import os
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import networkx as nx
from coolname import generate_slug


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_line(line: str) -> tuple[str, str, float] | None:
    """Parse a single line of 'name1 - name2 : score' format.

    Names can contain spaces, parentheses, underscores, numbers, hyphens, etc.
    We split on ' - ' (space-dash-space) for the pair separator and ' : ' for
    the score separator. This is greedy-safe because names don't contain ' : '.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Split on last occurrence of ' : ' to get the score
    score_sep = " : "
    score_idx = line.rfind(score_sep)
    if score_idx == -1:
        return None

    pair_part = line[:score_idx]
    score_str = line[score_idx + len(score_sep):]

    try:
        score = float(score_str)
    except ValueError:
        print(f"Warning: could not parse score from line: {line!r}", file=sys.stderr)
        return None

    # Split pair on ' - ' — but names themselves can contain hyphens.
    # We use the FIRST occurrence of ' - ' as the separator.
    # This works because the format is: name1 - name2 : score
    # and names don't start/end with spaces around a lone dash.
    pair_sep = " - "
    pair_idx = pair_part.find(pair_sep)
    if pair_idx == -1:
        print(f"Warning: could not split pair from line: {line!r}", file=sys.stderr)
        return None

    name1 = pair_part[:pair_idx].strip()
    name2 = pair_part[pair_idx + len(pair_sep):].strip()

    if not name1 or not name2:
        return None

    return name1, name2, score

def parse_line_full_mode(line: str) -> tuple[str,str,float] | None:
    """Parse a single line of 'name1 | name2 | score' format."""

    line = line.strip()
    if not line or line.startswith("#"):
        return None

    parts = line.split("|")
    if len(parts) != 3:
        print(f"Warning: expected 3 parts separated by '|', got: {line!r}", file=sys.stderr)
        return None

    name1 = parts[0].strip()
    name2 = parts[1].strip()
    score_str = parts[2].strip()

    if not name1 or not name2:
        return None

    try:
        score = float(score_str)
    except ValueError:
        print(f"Warning: could not parse score from line: {line!r}", file=sys.stderr)
        return None

    return name1, name2, score

def parse_file(filepath: str) -> list[tuple[str, str, float]]:
    """Parse all edges from a file."""
    edges = []
    with open(filepath, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1): # iterate over the lines in the file, start enumeration on 1 not 0
            result = parse_line_full_mode(line)
            if result is not None:
                edges.append(result)
    print(f"Parsed {len(edges)} edges from {filepath}")
    return edges

# ---------------------------------------------------------------------------
# Anonymize names
# ---------------------------------------------------------------------------

def get_or_create_nickname(name: str,  nickname_file_path: str, short_label_len: int = 20) -> str:
    nickname_map: dict[str, str] = {}  # fullname -> nickname
    if os.path.exists(nickname_file_path):
        with open(nickname_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" - ", 2)
                if len(parts) == 3:
                    _, nickname, fullname = parts
                    nickname_map[fullname] = nickname
    # already generated
    if name in nickname_map:
        return nickname_map[name]

    # Generate a new unique nickname
    existing_nicknames = set(nickname_map.values())
    nickname = generate_slug(2)
    while nickname in existing_nicknames:
        nickname = generate_slug(2)  # retry if collision

    shortname = shorten_name(name, short_label_len)
    # Append to file
    with open(nickname_file_path, "a", encoding="utf-8") as f:
        f.write(f"{shortname} - {nickname} - {name}\n")

    return nickname


# ---------------------------------------------------------------------------
# Name shortening
# ---------------------------------------------------------------------------

def shorten_name(name: str, max_len: int = 20) -> str:
    """Create a short label from a potentially ugly long name.

    Strategy: Clip right before the first underscore if that is b
        if the name is short enough now, use it as-is.
    Otherwise, truncate to the max-len first letters (makes it searchable)
    """

    # Look for the first underscore before max_len
    underscore_idx = name.find("_", 0, max_len)
    if underscore_idx != -1:
        name = name[:underscore_idx]

    if len(name) <= max_len:
        return name

    # Fallback: just truncate
    return name[:max_len]


# ---------------------------------------------------------------------------
# Graph building
# ---------------------------------------------------------------------------

def build_graph(
    edges: list[tuple[str, str, float]],
    threshold: float | None = None,
) -> nx.Graph:
    """Build a NetworkX graph, optionally filtering edges above threshold."""
    G = nx.Graph()

    for name1, name2, score in edges:
        if threshold is not None and score > threshold:
            G.add_node(name1)
            continue
        G.add_edge(name1, name2, score=score)

    if threshold is not None:
        total = len(edges)
        kept = G.number_of_edges()
        print(f"Threshold {threshold}: keeping {kept}/{total} edges")

    # Remove isolated nodes (no edges after filtering)
    # isolates = list(nx.isolates(G))
    # G.remove_nodes_from(isolates)

    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

def draw_graph(
    G: nx.Graph,
    output_path: str,
    nickname_map: str,
    short_label_len: int = 20,
    title: str | None = None,
    figsize: tuple[int, int] = (40, 20), # cm
    dpi: int = 150, # png and jpg relevant

):
    """Render the graph to a file."""
    if G.number_of_nodes() == 0:
        print("Nothing to draw — graph is empty.")
        return

    cm_conversion = 1/2.54  # centimeters in inches
    fig, ax = plt.subplots(figsize=(figsize[0]*cm_conversion, figsize[1]*cm_conversion))

    # -- Layout --
    # Use spring layout with edge weights. Lower score = more attraction.
    # We invert: weight = 1 - score, so similar pairs cluster together.
    weight_dict = {(u, v): 1.0 - d["score"] for u, v, d in G.edges(data=True)}
    nx.set_edge_attributes(G, weight_dict, "weight")

    # Returns a dictionary of the (x,y) position of every node in the graph
    # Seed makes the output deterministic between runs
    pos = nx.spring_layout(G, k=1.0, iterations=8, weight="weight", seed=42)

    # -- Edge drawing --
    scores = [G[u][v]["score"] for u, v in G.edges()]
    min_score = min(scores) if scores else 0 # old
    max_score = max(scores) if scores else 1 # old
    # min_score = 0
    # max_score = 1

    # Colormap: red (low score / suspicious) -> yellow -> green (higher score / less suspicious)
    cmap = cm.RdYlGn
    norm = mcolors.Normalize(vmin=min_score - 0.02, vmax=max_score + 0.02)

    for (u, v) in G.edges():
        score = G[u][v]["score"]
        # Thickness: lower score = thicker line
        normalized = (score - min_score) / (max_score - min_score)
        thickness = 2.0 - normalized * (2.0 - 0.05)
        color = cmap(norm(score))
        # alpha = max(0.3, 1.0 - score) # old
        # alpha = max(0.1, 1.0 - score) # not sure we need this

        x = [pos[u][0], pos[v][0]]
        y = [pos[u][1], pos[v][1]]
        ax.plot(x, y, color=color, linewidth=thickness, zorder=1)

    # -- Node drawing --
    node_sizes = []
    for node in G.nodes():
        # degree = G.degree(node) # degree is the number of edges connected to that node
        # node_sizes.append(200 + 80 * degree)
        node_sizes.append(200)

    node_x = [pos[n][0] for n in G.nodes()]
    node_y = [pos[n][1] for n in G.nodes()]
    degrees = [G.degree(n) for n in G.nodes()]

    scatter = ax.scatter(
        node_x, node_y,
        s=node_sizes,
        c="white",
        # c=degrees, # might need to bring this back
        # cmap="YlOrRd",
        edgecolors="black", # border color for each circle
        linewidths=0.8, # Border thickness in points
        zorder=2, # circles are drawn on top of edges, that have zorder 1
    )

    # -- Labels --
    # short_labels = {n: shorten_name(n, short_label_len) for n in G.nodes()}
    for node, (x, y) in pos.items():
        label = get_or_create_nickname(node, nickname_map, short_label_len)
        ax.annotate(
            label,
            # short_labels[node],
            (x, y),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=7,
            fontweight="bold",
            color="red",
            zorder=3,
            bbox=dict(
                boxstyle="round,pad=0.2",
                facecolor="white",
                edgecolor="none",
                alpha=0.7,
            )
        )

    # -- Edge score labels on very suspicious edges --
    # score_label_threshold = min_score + 0.05  # label only the most suspicious
    # for (u, v) in G.edges():
    #     score = G[u][v]["score"]
    #     if score <= score_label_threshold:
    #         mid_x = (pos[u][0] + pos[v][0]) / 2
    #         mid_y = (pos[u][1] + pos[v][1]) / 2
    #         ax.annotate(
    #             f"{score:.3f}",
    #             (mid_x, mid_y),
    #             fontsize=6,
    #             color="darkred",
    #             ha="center",
    #             zorder=3,
    #             bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7),
    #         )

    # -- Legend / colorbar --
    # sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    # sm.set_array([])
    # cbar = plt.colorbar(sm, ax=ax, shrink=0.5, pad=0.02)
    # cbar.set_label("Similarity Score (lower = more similar)", fontsize=10)

    # Node color legend
    # cbar2 = plt.colorbar(scatter, ax=ax, shrink=0.3, pad=0.05, location="left")
    # cbar2.set_label("Number of connections", fontsize=10)

    # -- Title and stats --
    if title is None:
        title = "Submission Similarity Graph"
    stats = f"{G.number_of_nodes()} students, {G.number_of_edges()} connections"
    score_range = f"Score range: {min_score:.3f} – {max_score:.3f}"
    ax.set_title(f"{title}\n{stats} · {score_range}", fontsize=14, fontweight="bold")

    ax.set_axis_off()
    plt.tight_layout()

    plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
    print(f"Saved to {output_path}")
    plt.close()


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

def print_summary(G: nx.Graph, nickname_map, top_n: int | None = None):
    """Print a text summary of the most suspicious connections and nodes."""
    if G.number_of_edges() == 0:
        print("No edges to summarize.")
        return

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    # Top suspicious pairs
    edges_sorted = sorted(G.edges(data=True), key=lambda e: e[2]["score"])
    if top_n is None:
        print("\nPrinting all pairs with similarity from highest to lowest:")
        print("-" * 60)
        for u, v, d in edges_sorted:
            # short_u = shorten_name(u, 30)
            # short_v = shorten_name(v, 30)
            short_u = get_or_create_nickname(u, nickname_map)
            short_v = get_or_create_nickname(v, nickname_map)
            print(f"  {d['score']:.4f}  {short_u}  ↔  {short_v}")
    else:
        print(f"\nTop {top_n} most similar pairs:")
        print("-" * 60)
        for u, v, d in edges_sorted[:top_n]:
            # short_u = shorten_name(u, 30)
            # short_v = shorten_name(v, 30)
            short_u = get_or_create_nickname(u, nickname_map)
            short_v = get_or_create_nickname(v, nickname_map)
            print(f"  {d['score']:.4f}  {short_u}  ↔  {short_v}")

    # Most connected nodes
    print(f"\nMost connected students:")
    print("-" * 60)
    degree_sorted = sorted(G.degree(), key=lambda x: x[1], reverse=True)
    if top_n is None:
        for node, degree in degree_sorted:
            # short = shorten_name(node, 40)
            short = get_or_create_nickname(node, nickname_map)
            # Also show their strongest connection
            neighbors = [(G[node][nb]["score"], nb) for nb in G.neighbors(node)]
            if neighbors:
                best_score, best_nb = min(neighbors)
                # short_nb = shorten_name(best_nb, 25)
                short_nb = get_or_create_nickname(best_nb, nickname_map)
                print(f"  {degree:3d} connections  {short}  (strongest: {best_score:.3f} with {short_nb})")
            else:
                print(f"  {degree:3d} connections  {short}")
    else:
        for node, degree in degree_sorted[:top_n]:
            # short = shorten_name(node, 40)
            short = get_or_create_nickname(node, nickname_map)
            # Also show their strongest connection
            neighbors = [(G[node][nb]["score"], nb) for nb in G.neighbors(node)]
            if neighbors:
                best_score, best_nb = min(neighbors)
                # short_nb = shorten_name(best_nb, 25)
                short_nb = get_or_create_nickname(best_nb, nickname_map)
                print(f"  {degree:3d} connections  {short}  (strongest: {best_score:.3f} with {short_nb})")
            else:
                print(f"  {degree:3d} connections  {short}")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Visualize pairwise submission similarity as a graph.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("datafile", help="Path to the similarity data file")
    parser.add_argument(
        "-t", "--threshold", type=float, default=None,
        help="Only show edges with score BELOW this value (e.g. 0.5)",
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="Output file path (default: similarity_graph.<format>)",
    )
    parser.add_argument(
        "-f", "--format", default="png", choices=["png", "svg", "pdf", "jpg"],
        help="Output format (default: png)",
    )
    parser.add_argument(
        "--short-labels", type=int, default=20,
        help="Max characters for node labels (default: 20)",
    )
    parser.add_argument(
        "--title", default=None,
        help="Custom title for the graph",
    )
    parser.add_argument(
        "--figsize", default="40x20",
        help="Figure size as WxH in cm (default: 40x20)",
    )
    parser.add_argument(
        "--dpi", type=int, default=150,
        help="DPI for raster output (png, jpg) (default: 150)",
    )
    parser.add_argument(
        "--no-summary", action="store_true",
        help="Skip printing the text summary",
    )
    parser.add_argument(
        "--nickname-map", default="nickname_map.txt",
        help="The file path for where to store the nickname-realname map txt file"
    )

    args = parser.parse_args()

    # Parse figure size
    try:
        w, h = args.figsize.split("x")
        figsize = (int(w), int(h))
    except ValueError:
        print(f"Invalid figsize '{args.figsize}', using default 40x20", file=sys.stderr)
        figsize = (40, 20)

    # Parse data
    edges = parse_file(args.datafile)
    if not edges:
        print("No edges found. Check your data file format.", file=sys.stderr)
        sys.exit(1)

    # Build graph
    G = build_graph(edges, threshold=args.threshold)

    # Summary
    if not args.no_summary:
        print_summary(G, args.nickname_map) # set top_ n to 30

    # Output path
    if args.output:
        output_path = args.output
    else:
        output_path = f"similarity_graph.{args.format}"

    # Draw
    draw_graph(
        G,
        output_path=output_path,
        nickname_map=args.nickname_map,
        short_label_len=args.short_labels,
        title=args.title,
        figsize=figsize,
        dpi=args.dpi,
        
    )


if __name__ == "__main__":
    # print(shorten_name("ettfan_"))
    # print(shorten_name("ettffssåntettffssan_"))
    # print(shorten_name("ettffssåntettffssant_"))
    # print(shorten_name("ettffssåntettffssantttfergegrergjhfgjkdhgkjdhfgjkhdfgjhdfgjkhdgfkjherg_"))
    main()
