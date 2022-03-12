import ast
import astor
import astpretty
import re
from graphviz import Source, Graph, Digraph
import sys

filename = sys.argv[1]  # the filename of the Python program we're analyzing
linenum = int(sys.argv[2])  # the line number argument to the slicer
varname = sys.argv[3]  # the variable name argument to the slicer

# note that most of this starter code comes directly from the CFG
# visualizer we played with in class. so there shouldn't be
# a ton of fresh content to figure out here.
# scroll to the bottom for the new stuff

# what's this AST thing look like?
code = open(filename).read()
tree = ast.parse(code)
astpretty.pprint(tree)

# it's convenient for us to keep track of all the CFG nodes that exist
# let's provide a way of registering them and keeping track

REGISTRY_IDX = 0

REGISTRY = {}


def get_registry_idx():
    global REGISTRY_IDX
    v = REGISTRY_IDX
    REGISTRY_IDX += 1
    return v


def reset_registry():
    global REGISTRY_IDX
    global REGISTRY
    REGISTRY_IDX = 0
    REGISTRY = {}


def register_node(node):
    node.rid = get_registry_idx()
    REGISTRY[node.rid] = node


def get_registry():
    return dict(REGISTRY)


# how shall we represent nodes in our Control Flow Graph?
class CFGNode(dict):
    def __init__(self, parents=[], ast=None):
        assert type(parents) is list
        register_node(self)
        self.parents = parents
        self.ast_node = ast
        self.update_children(parents)  # requires self.rid
        self.children = []
        self.calls = []

    def i(self):
        return str(self.rid)

    def update_children(self, parents):
        for p in parents:
            p.add_child(self)

    def add_child(self, c):
        if c not in self.children:
            self.children.append(c)

    def lineno(self):
        return self.ast_node.lineno if hasattr(self.ast_node, "lineno") else 0

    def __str__(self):
        return "id:%d line[%d] parents: %s : %s" % (
            self.rid,
            self.lineno(),
            str([p.rid for p in self.parents]),
            self.source(),
        )

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return self.rid == other.rid

    def __neq__(self, other):
        return self.rid != other.rid

    def set_parents(self, p):
        self.parents = p

    def add_parent(self, p):
        if p not in self.parents:
            self.parents.append(p)

    def add_parents(self, ps):
        for p in ps:
            self.add_parent(p)

    def source(self):
        return astor.to_source(self.ast_node).strip()

    def to_json(self):
        return {
            "id": self.rid,
            "parents": [p.rid for p in self.parents],
            "children": [c.rid for c in self.children],
            "calls": self.calls,
            "at": self.lineno(),
            "ast": self.source(),
        }


# and how shall we represent the Control Flow Graph itself?
class PyCFG:
    def __init__(self):
        # first let's make our root node
        self.founder = CFGNode(parents=[], ast=ast.parse("start").body[0])
        self.founder.ast_node.lineno = 0

    def parse(self, src):
        # this is just the same ast.parse we did at the start of class
        return ast.parse(src)

    def walk(self, node, myparents):
        # which of the functions below will we call?
        # to process this kind of AST node
        fname = "on_%s" % node.__class__.__name__.lower()
        if hasattr(self, fname):
            fn = getattr(self, fname)
            v = fn(node, myparents)
            return v
        else:
            return myparents

    def on_module(self, node, myparents):
        """
        Module(stmt* body)
        If you look at that AST we printed at start of class, you'll see this
        is the root of our AST
        """
        # each time a statement is executed unconditionally, make a link from
        # the result to next statement
        p = myparents
        for n in node.body:
            p = self.walk(n, p)
        return p  # return list of exit CFGNodes

    def on_assign(self, node, myparents):
        """
        Assign(expr* targets, expr value)
        """
        if len(node.targets) > 1:
            raise NotImplemented("Parallel assignments")

        p = [CFGNode(parents=myparents, ast=node)]
        p = self.walk(node.value, p)

        return p  # return list of exit CFGNodes

    def on_while(self, node, myparents):
        # For a while node, the earliest parent is the node.test
        _test_node = CFGNode(
            parents=myparents,
            ast=ast.parse("_while: %s" % astor.to_source(node.test).strip()).body[0],
        )
        # Copy source location (lineno, col_offset, end_lineno, and end_col_offset)
        # from second node to first node
        ast.copy_location(_test_node.ast_node, node.test)
        test_node = self.walk(node.test, [_test_node])

        # now we evaluate the body, one at a time.
        assert len(test_node) == 1
        p1 = test_node
        for n in node.body:
            p1 = self.walk(n, p1)

        # our last node from the body is also one of the ways we could enter
        # _test_node, because we could go back through the loop
        # so add that parent relationship here
        _test_node.add_parents(p1)

        return test_node  # return list of exit CFGNodes

    def on_binop(self, node, myparents):
        left = self.walk(node.left, myparents)
        right = self.walk(node.right, left)
        return right  # return list of exit CFGNodes

    def on_compare(self, node, myparents):
        left = self.walk(node.left, myparents)
        right = self.walk(node.comparators[0], left)
        return right  # return list of exit CFGNodes

    def on_unaryop(self, node, myparents):
        return self.walk(node.operand, myparents)  # return list of exit CFGNodes

    def on_expr(self, node, myparents):
        p = [CFGNode(parents=myparents, ast=node)]
        return self.walk(node.value, p)  # return list of exit CFGNodes

    def update_children(self):
        for nid, node in REGISTRY.items():
            for p in node.parents:
                p.add_child(node)

    def gen_cfg(self, src):
        node = self.parse(src)
        nodes = self.walk(node, [self.founder])  # let's traverse this AST!!
        self.last_node = CFGNode(parents=nodes, ast=ast.parse("stop").body[0])
        # give both start and stop the fake line number 0
        ast.copy_location(self.last_node.ast_node, self.founder.ast_node)
        self.update_children()


def gen_cfg(fnsrc):
    reset_registry()  # in case you're generating multiple CFGs
    cfg = PyCFG()
    cfg.gen_cfg(fnsrc)
    cache = dict(REGISTRY)
    return cache


# just helper functions for making our nice visualizations!
# feel free to ignore this
# ------------------------------------------------------------
def to_graph(cache, arcs=[]):
    graph = Digraph(comment="Control Flow Graph")
    colors = {0: "blue", 1: "red"}
    kind = {0: "T", 1: "F"}
    cov_lines = set(i for i, j in arcs)
    for nid, cnode in cache.items():
        lineno = cnode.lineno()
        shape, peripheries = "oval", "1"
        if isinstance(cnode.ast_node, ast.AnnAssign):
            if cnode.ast_node.target.id in {"_if", "_for", "_while"}:
                shape = "diamond"
            elif cnode.ast_node.target.id in {"enter", "exit"}:
                shape, peripheries = "oval", "2"
        else:
            shape = "rectangle"
        graph.node(
            cnode.i(),
            "%d: %s" % (lineno, unhack(cnode.source())),
            shape=shape,
            peripheries=peripheries,
        )
        for pn in cnode.parents:
            plineno = pn.lineno()
            if (
                hasattr(pn, "calllink")
                and pn.calllink > 0
                and not hasattr(cnode, "calleelink")
            ):
                graph.edge(pn.i(), cnode.i(), style="dotted", weight=100)
                continue

            if arcs:
                if (plineno, lineno) in arcs:
                    graph.edge(pn.i(), cnode.i(), color="green")
                elif plineno == lineno and lineno in cov_lines:
                    graph.edge(pn.i(), cnode.i(), color="green")
                # child is exit and parent is covered
                elif hasattr(cnode, "fn_exit_node") and plineno in cov_lines:
                    graph.edge(pn.i(), cnode.i(), color="green")
                # parent is exit and one of its parents is covered.
                elif (
                    hasattr(pn, "fn_exit_node")
                    and len(set(n.lineno() for n in pn.parents) | cov_lines) > 0
                ):
                    graph.edge(pn.i(), cnode.i(), color="green")
                # child is a callee (has calleelink) and one of the parents is covered.
                elif plineno in cov_lines and hasattr(cnode, "calleelink"):
                    graph.edge(pn.i(), cnode.i(), color="green")
                else:
                    graph.edge(pn.i(), cnode.i(), color="red")
            else:
                order = {c.i(): i for i, c in enumerate(pn.children)}
                if len(order) < 2:
                    graph.edge(pn.i(), cnode.i())
                else:
                    o = order[cnode.i()]
                    graph.edge(pn.i(), cnode.i(), color=colors[o], label=kind[o])
    return graph


def unhack(v):
    for i in ["if", "while", "for", "elif"]:
        v = re.sub(r"^_%s:" % i, "%s:" % i, v)
    return v


# ------------------------------------------------------------


def print_lines_in_slice(lines_in_slice):
    lines_in_slice.sort()
    print(lines_in_slice)


def print_slice(lines_in_slice, nodes):
    print(lines_in_slice)
    for line in lines_in_slice:
        print(nodes[line].source())


def collect_references(ast_node):
    if type(ast_node) == ast.Name:
        return [ast_node.id]
    elif type(ast_node) == ast.Constant:
        return []
    elif type(ast_node) == ast.BinOp:
        return collect_references(ast_node.left) + collect_references(ast_node.right)


def slice(nodes, linenum, varname):
    # how should we find the slice?
    # slice should return a list of the line numbers that should be included in the slice
    # for grading purposes, please
    #    (1) call the print_slice function on the list of line numbers
    #    (2) remove other print statements
    lines_in_slice = []

    # Instantiate the relevant set R as the empty set.
    relevant = set()

    # Insert varname into the relevant set.
    relevant.add(varname)

    # Get the starting node based on the input linenum.
    # Track the current node as we traverse up the CFG.
    start_loc = nodes[linenum]
    current_loc = start_loc

    while len(relevant) != 0 and current_loc.source() != "start":
        parents = current_loc.parents

        for parent in parents:
            # Define sets to hold def(m) and ref(m) for each parent statement.
            def_m = set()
            ref_m = set()

            if isinstance(parent.ast_node, ast.Assign):
                # Add all defined variables to def(m).
                for target in parent.ast_node.targets:
                    def_m.add(target.id)

                # Define relevant_m to be the set difference relevant \ def_m.
                relevant_m = relevant.difference(def_m)

                # Find all elements in def_m that are in relevant.
                intersect = relevant.intersection(def_m)

                # If def_m in relevant...
                if len(intersect) > 0:
                    # Add all referenced variables to ref(m).
                    ref_m = set(collect_references(parent.ast_node.value))
                    relevant_m = relevant_m.union(ref_m)

                    # Add m to the slice.
                    lines_in_slice.append(parent.lineno())

                # Update the relevant set.
                relevant = relevant_m

            # Update the current_loc to point to the parent node.
            current_loc = parent

    print_slice(lines_in_slice, nodes)


nodes = gen_cfg(code)
slice(nodes, linenum, varname)
