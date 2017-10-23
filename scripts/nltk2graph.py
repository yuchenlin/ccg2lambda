# -*- coding: utf-8 -*-
#
#  Copyright 2017 Pascual Martinez-Gomez
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from nltk.sem.logic import *
from logic_parser import lexpr

import networkx as nx

# TODO: make this counter local.
node_id_gen = (i for i in range(10000))

def merge_graphs_to(graph, graphs):
    head_node = graph.head_node
    for g in graphs:
        graph = nx.union(graph, g)
        graph.add_edge(head_node, g.head_node)
    graph.head_node = head_node
    return graph

def formula_to_graph(expr):
    if isinstance(expr, str):
        expr = lexpr(expr)
    expr_str = str(expr)
    G = nx.DiGraph()
    if isinstance(expr, ConstantExpression) or \
       isinstance(expr, AbstractVariableExpression) or \
       isinstance(expr, Variable):
        G.head_node = next(node_id_gen)
        G.add_node(G.head_node, label=expr_str)
    elif isinstance(expr, BinaryExpression):
        G.head_node = next(node_id_gen)
        G.add_node(G.head_node, label=expr.getOp())
        graphs = map(formula_to_graph, [expr.first,  expr.second])
        G = merge_graphs_to(G, graphs)
    elif isinstance(expr, ApplicationExpression):
        func, args = expr.uncurry()
        G = formula_to_graph(func)
        args_graphs = map(formula_to_graph, args)
        G = merge_graphs_to(G, args_graphs)
    elif isinstance(expr, VariableBinderExpression):
        quant = '<quant_unk>'
        if isinstance(expr, QuantifiedExpression):
            quant = expr.getQuantifier()
        elif isinstance(expr, LambdaExpression):
            quant = 'lambda'
        G.head_node = next(node_id_gen)
        G.add_node(G.head_node, label=quant)
        var_node_id = next(node_id_gen)
        G.add_node(var_node_id, label=str(expr.variable))
        G.add_edge(G.head_node, var_node_id)
        graphs = map(formula_to_graph, [expr.term])
        G = merge_graphs_to(G, graphs)
    return G

def get_label(graph, node_id, label='label'):
    return graph.nodes[node_id].get(label, None)

quantifiers = Tokens.QUANTS

def get_scoped_nodes(graph, head_node=None, quant_active=None, quant_scope=None):
    """
    Returns a dictionary where:
    keys are tuples (scope_node_id, expression) and
    values are lists of node IDs within the scope and with
    the same expression.
    """
    if quant_scope is None:
        quant_scope = {}
    label = get_label(graph, head_node)
    if label in quantifiers:
        quant_active = head_node
    elif quant_active in graph.pred[head_node]:
        min_sibling_id = min(list(graph.succ[list(graph.pred[head_node])[0]].keys()))
        assert not graph.succ[min_sibling_id], 'Expected node {0} to be a leaf'.format(head_node)
        quant_scope[(quant_active, label)] = [(head_node, 'leaf')]
    elif (quant_active, label) in quant_scope:
        node_type = 'leaf' if not graph.succ[head_node] else 'internal'
        quant_scope[(quant_active, label)].append((head_node, node_type))
    for child_node_id in graph.succ[head_node]:
        get_scoped_nodes(graph, child_node_id, quant_active, quant_scope)
    return quant_scope

# TODO: decide whether we want to modify the graph in-place.
def merge_leaf_nodes(graph, head_node=None, quant_active=None, quant_scope=None):
    """
    Traverses the graph, merging those nodes
    with the same label within the same quantificaton scope.
    """
    # from pudb import set_trace; set_trace()
    if head_node is None:
        head_node = graph.head_node
    # Get nodes and their scope information.
    scoped_nodes = get_scoped_nodes(graph, head_node)
    for (quant_node, expr), nodes_to_merge in scoped_nodes.items():
        if len(nodes_to_merge) > 1:
            master_node, node_type = nodes_to_merge[0]
            assert node_type == 'leaf'
            for node, node_type in nodes_to_merge[1:]:
                # Merge leaves within the same scope:
                if node_type == 'leaf':
                    graph = nx.contracted_nodes(graph, master_node, node)
                # Add edges from quantifier to internal function names:
                elif node_type == 'internal':
                    graph.add_edge(quant_node, node)
    return graph