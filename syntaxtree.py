import ast
import pydot

class SyntaxTree:
    def __init__(self, root_node):
        self.root = {}
        self.root["name"] = root_node
        self.root["children"] = []
        self.root["parent"] = None
        self.root["id"] = 1
        self.max_id = 1
        self.current_node = self.root

    def add_leaf(self, operation):
        new_node = {}
        new_node["name"] = operation
        new_node["children"] = []
        new_node["parent"] = self.current_node
        self.max_id += 1
        new_node["id"] = self.max_id
        self.current_node["children"].append(new_node)
        self.current_node = new_node

    def up(self):
        self.current_node = self.current_node["parent"]

    def generate_dot(self, filename):
        graph = pydot.Dot("ast", graph_type="digraph")
        def walk(n, g):
            g.add_node(pydot.Node(str(n["id"]), label=n["name"]))
            for c in n["children"]:
                g.add_edge(pydot.Edge(str(n["id"]), str(c["id"])))
                walk(c, g)
        walk(self.root, graph)
        graph.write_png(filename)

    def generate_subgraphs(self, depth, min_entries):
        def short_walk(node, depth_remaining, text):
            if depth_remaining == 0 or len(node["children"]) == 0: 
                return (1, node["name"])
            common_text = []
            total_entries = 1
            for subnode in node["children"]:
                entries, result = short_walk(subnode, depth_remaining - 1, text)
                total_entries += entries
                common_text.append(result)
            common_text.sort()
            return total_entries, node["name"] + "-" + "-".join(common_text)

        def long_walk(node, collection):
            entries, res = short_walk(node, depth, "")
            if entries > min_entries:
                if res not in collection:
                    collection[res] = 0
                collection[res] += 1
            for subnode in node["children"]:
                long_walk(subnode, collection)
            return collection

        all_nodes = {}
        long_walk(self.root, all_nodes)
        return all_nodes

    def __add__(self, other):
        new_graph = SyntaxTree("SuperNode")
        def walk(node):
            node["id"] += other.max_id + 1
            for n in node["children"]:
                walk(n)
        walk(self.root)
        self.max_id += other.max_id + 1
        def walk_other(node):
            node["id"] += 1
            for n in node["children"]:
                walk(n)
        walk_other(other.root)
        new_graph.root["children"].append(self.root)
        new_graph.root["children"].append(other.root)
        return new_graph

    def compare(self, other, depth, min_width):
        my_nodes = self.generate_subgraphs(depth, min_width)
        other_nodes = other.generate_subgraphs(depth, min_width)
        diff = 0
        for key in my_nodes:
            if key not in other_nodes:
                diff += my_nodes[key]
            else:
                diff += abs(my_nodes[key] - other_nodes[key])

        total_subgraphs = sum([my_nodes[k] for k in my_nodes])
        return (diff / total_subgraphs)

            

def generate_ast_py(filename):
    # Returns tree of operations

    class NameHider(ast.NodeTransformer):
        def visit_Name(self, node):
            node.id = "var"
            return node

        def visit_Constant(self, node):
            node.value = None
            return node

    with open(filename) as cur_file:
        t = ast.parse(cur_file.read(), filename=filename)
    t = NameHider().visit(t)

    

    def fancy_walk(node, tree):
        for elem in ast.iter_child_nodes(node):
            tree.add_leaf(elem.__class__.__name__)
            fancy_walk(elem, tree)
            tree.up()

    st = SyntaxTree(t.__class__.__name__)
    fancy_walk(t,st)

    return st




if __name__ == "__main__":
    mytree = generate_ast_py("plagi.py")
    print(f"Similarity: {mytree.compare(mytree, 1, 2)}")
    #mytree.generate_dot("test.png")
    res = mytree.generate_subgraphs(1, 2)
    for key in res:
        print(f"{key}: {res[key]}")
