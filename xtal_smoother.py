import multiprocessing
import os
import re
import sys
import time

import igl
import networkx as nx
import numpy as np
import pandas as pd
import pymesh
from networkx.linalg.laplacianmatrix import \
    laplacian_matrix as laplacian_matrix
from numba import njit
from tqdm import tqdm


@njit
def form_edge_graph(F, edge_weights):
    """
    Create Impose Natural-Order sorting of strings.

    Parameters
    ----------
    F : ndarray, shape (num_faces,3)
        Array of triangle/face connectivities.
    edge_weights : ndarray, shape(num_nodes,)
        Weights for each node, when multiplied,
        form weights for corresponding edges.

    Returns
    -------
    G : NetworkX edge-weighted graph
    """
    # Form graph edges and weights
    edge_list = []
    for f in F:
        w = edge_weights[f]
        edge_list.append((f[0], f[1], w[0]*w[1]))
        edge_list.append((f[0], f[2], w[0]*w[2]))
        edge_list.append((f[1], f[2], w[1]*w[2]))
    return edge_list


def graph_smooth(V, F, feat):
    """
    Graph-based Laplacian Smoothing.

    Parameters
    ----------
    V : ndarray, shape (num_nodes,3)
        Array of vertex/node coordinates (x, y z).
    F : ndarray, shape (num_faces,3)
        Array of triangle/face connectivities.
    feat : string
        Denotes what features to smooth.

    Returns
    -------
    V : Updated vertex/node coordinates
    """
    # define edge weights
    if feat == "ext_triple":
        edge_weights = 1*np.isin(ntype, 13) + 2*np.isin(ntype, 14)
    elif feat == "int_triple":
        edge_weights = 1*np.isin(ntype, 3) + 2*np.isin(ntype, 4)
    else:
        edge_weights = np.ones((len(V),))

    # form edge-weighted graph
    print("\t forming graph")
    G = nx.Graph()
    G.add_weighted_edges_from(form_edge_graph(F, edge_weights))

    # compute Laplacian
    nodelist = np.linspace(0, len(V)-1, len(V))
    print("\t computing laplacian")
    L = laplacian_matrix(G, nodelist=nodelist, weight="weight")

    # compute weight normalization
    W_norm = np.sum(abs(L), 0)
    W_norm[W_norm == 0] = 1
    W_norm = 1/np.tile(W_norm, [3, 1]).transpose()

    # perform smoothing
    if feat != "bound":
        for m in tqdm(range(laplacian_iters), position=0, ncols=0, desc="\t smoothing"):
            Vnew = V - lamda*np.multiply(geom, np.multiply(L.dot(V), W_norm))
            V = Vnew.copy()
    else:
        pinned = np.isin(ntype, [2, 12])*1
        pinned = np.tile(pinned, [3, 1]).transpose()
        for m in tqdm(range(laplacian_iters), position=0, ncols=0, desc="\t smoothing"):
            Vnew = V - lamda * \
                np.multiply(geom*pinned, np.multiply(L.dot(V), W_norm))
            V = Vnew.copy()
    return np.array(V)


def write_grain_mesh(grain_id):
    """
    Write grain-level surface meshes.

    Parameters
    ----------
    grain_id : scalar
        Respective grain_id to write mesh.

    Returns
    -------
    None
    """
    queryF = 1*np.isin(flabel, grain_id)
    grainF = F[np.where(np.sum(queryF, 1) > 0)[0]]
    fname = cwd + "/GrainSTLs/" + str(grain_id) + ".stl"
    igl.write_triangle_mesh(fname, V, grainF, force_ascii=False)
    mesh = pymesh.compute_outer_hull(pymesh.load_mesh(fname))
    pymesh.save_mesh(fname, mesh)


def natural_sort(l):
    """
    Impose Natural-Order sorting of strings.

    Parameters
    ----------
    l : list of strings

    Returns
    -------
    l : sorted list of strings
    """
    def convert(text):
        return int(text) if text.isdigit() else text.lower()

    def alphanum_key(key):
        return [convert(c) for c in re.split("([0-9]+)", key)]
    return sorted(l, key=alphanum_key)


# Start program
t0 = time.time()
cwd = os.getcwd()
laplacian_iters = int(sys.argv[1])
lamda = float(sys.argv[2])

print("\n\n================")
print(" XTAL_SMOOTHER")
print("================")


# Load Data
print("Reading Triangle Data")
V = pd.read_csv(cwd + "/nodes.txt", skiprows=4, sep="\s+").to_numpy()
F = pd.read_csv(cwd + "/triangles.txt", skiprows=8, sep="\s+").to_numpy()
ntype = pd.read_csv(cwd + "/nodetype.txt").to_numpy().flatten()
flabel = pd.read_csv(cwd + "/facelabels.txt").to_numpy()


# Setting up geometric constraints for nodes on faces/edges/corners
xface = 1*~np.isin(V[:, 0], [np.min(V[:, 0]), np.max(V[:, 0])])
yface = 1*~np.isin(V[:, 1], [np.min(V[:, 1]), np.max(V[:, 1])])
zface = 1*~np.isin(V[:, 2], [np.min(V[:, 2]), np.max(V[:, 2])])
geom = np.vstack([xface, yface, zface]).transpose()


# Perform smoothing
print("Smooth Exterior Triple Lines")
V = graph_smooth(V, F, feat="ext_triple")
print("Smooth Interior Triple Lines")
V = graph_smooth(V, F, feat="int_triple")
print("Smooth Boundaries")
V = graph_smooth(V, F, feat="bound")


# Process-based parallelization of writing grain surface meshes
if os.path.isdir(cwd + "/GrainSTLs"):
    os.system("rm -r " + cwd + "/GrainSTLs")
os.mkdir(cwd + "/GrainSTLs")
print("Writing Grain Surface Meshes")
grain_ids = np.unique(flabel)
pool = multiprocessing.Pool(multiprocessing.cpu_count())
result = pool.map(write_grain_mesh, grain_ids[grain_ids != -1])
pool.close()
pool.join()


# Write whole surface mesh
print("Writing Whole Surface Mesh")
igl.write_triangle_mesh(cwd + "/Whole.stl", V, F, force_ascii=False)


print("FINISHED - Total processing time: ", time.time() - t0, "s\n")
