import glob
import os
import re
import sys
import time

import igl
import meshio
import numpy as np
import pymesh
from numba import njit
from tqdm import tqdm


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


@njit
def tets_to_tris(tets):
    """
    Get corresponding triangles of a tetrahedron.

    Parameters
    ----------
    tets : ndarray, shape (num_tets, 10)
        Array of 10-node tetrahedron connectivities.

    Returns
    -------
    tris : ndarray, shape (4*num_tets, 6)
        Array of triangle connectivities. 
    """
    num_tets = len(tets)
    tris = np.zeros((4*num_tets, 6), dtype=tets.dtype)
    for i, c in enumerate(tets):
        tris[4*i:4*(i+1)] = np.asarray([[c[0], c[2], c[1], c[4], c[5], c[6]],
                                        [c[0], c[1], c[3], c[4], c[7], c[8]],
                                        [c[0], c[3], c[2], c[6], c[7], c[9]],
                                        [c[1], c[2], c[3], c[5], c[8], c[9]]], dtype="int32")
    return tris


def surface_tris(tets):
    """
    Get triangles at exterior surface of volume mesh.

    Parameters
    ----------
    tets : ndarray, shape (num_tets, 10)
        Array of 10-node tetrahedron connectivities.

    Returns
    -------
    tris : ndarray, shape (num_tris, 6)
        Array of triangle connectivities. 
    """
    tris = tets_to_tris(tets)
    ind = np.argsort(tris, axis=1)
    tris_sort = np.take_along_axis(tris, ind, axis=1)

    # count times triangles appear (2 = interior, 1 = exterior)
    _, idx, cnts = np.unique(
        tris_sort, axis=0, return_inverse=True, return_counts=True)
    tri_count = cnts[idx]
    return tris[tri_count == 1]


def generate_element_sets(mesh, grain_ids):
    """
    Create element sets based on grain ids.

    Parameters
    ----------
    mesh : meshio.Mesh object
    grain_ids : ndarray

    Returns
    -------
    mesh : meshio.Mesh object
        Mesh with added element sets.
    """
    cell_data = np.zeros((len(grain_ids),))
    mesh.cell_sets["ALLELEMENTS"] = [np.arange(len(grain_ids))]
    for g in np.unique(grain_ids):
        numStr = str(g).zfill(4)
        mesh.cell_sets["GRAIN_" +
                       numStr] = np.where(grain_ids == g)
        cell_data[np.where(grain_ids == g)[0]] = g
    mesh.cell_data["GrainIds"] = cell_data
    return mesh


def generate_node_sets(mesh, nodes, epsilon):
    """
    Create node sets.

    Parameters
    ----------
    mesh : meshio.Mesh object
    nodes : ndarray, shape (num_nodes, 3)
        Array of node positions (x, y, z).
    epsilon : scalar
        fTetWild envelope size.

    Returns
    -------
    mesh : meshio.Mesh object
        Mesh with added node sets.
    """
    mesh.point_sets["ALLNODES"] = np.arange(len(nodes))

    # get boundary nodes
    tets = mesh.cells[0][1]
    b_node_id = surface_tris(tets).flatten()
    b_node = nodes[b_node_id]

    # get X, Y, Z limits of RVE
    V, _ = igl.read_triangle_mesh("Whole.stl")
    min_x, max_x = np.min(V[:, 0]), np.max(V[:, 0])
    min_y, max_y = np.min(V[:, 1]), np.max(V[:, 1])
    min_z, max_z = np.min(V[:, 2]), np.max(V[:, 2])

    # assign boundary condition node sets (faces of RVE)
    bc_sets = ["f_n-1",
               "f_n+1",
               "f_n-2",
               "f_n+2",
               "f_n-3",
               "f_n+3"]
    delta = igl.bounding_box_diagonal(nodes)*float(epsilon)
    BCs = [np.where(b_node[:, 0] < min_x+delta)[0],
           np.where(b_node[:, 0] > max_x-delta)[0],
           np.where(b_node[:, 1] < min_y+delta)[0],
           np.where(b_node[:, 1] > max_y-delta)[0],
           np.where(b_node[:, 2] < min_z+delta)[0],
           np.where(b_node[:, 2] > max_z-delta)[0]]
    for i in range(len(BCs)):
        mesh.point_sets[bc_sets[i]] = b_node_id[BCs[i]]
    return mesh


# Start program
t0 = time.time()
edge_length = sys.argv[1]
epsilon = sys.argv[2]

print("\n\n================")
print(" XTAL_MESHER")
print("================")

# Compile c++ linear->quad conversion script
os.system("./tet_mesh_l2q.sh")

# Call fTetWild
print("Meshing With fTetWild")
os.system(
    "/fTetWild/build/./FloatTetwild_bin"
    + " --input Whole.stl"
    + " --output Volume_1.msh"
    + " --disable-filtering"
    + " -l " + edge_length
    + " -e " + epsilon
)
while os.path.exists("Volume_1.msh") == False:
    time.sleep(10)
print("Meshing Completed")


# Load fTetWild output
mesh = pymesh.load_mesh("Volume_1.msh")
elements = mesh.elements
nodes = mesh.vertices


# Prepare winding number computation & grain ID assignment
numcells = len(elements)
centroids = np.mean(nodes[elements], 1)
grain_ids = np.zeros((numcells,))


# Loop through grains & perform inside/outside segmentation
files = glob.glob("GrainSTLs/*.stl")
for f in tqdm(files,
              leave=True,
              ncols=0,
              desc="Assigning Element GrainIDs",
              ):
    grain_id = os.path.basename(f)[:-4]
    V, F = igl.read_triangle_mesh(f)

    # skip bad mesh
    if V.shape[0] < 4:
        continue

    P = igl.fast_winding_number_for_meshes(V, F, centroids)
    grain_ids[np.where(P > 0.01)[0]] = int(grain_id)


# Remove void mesh (ID == 0)
print("Removing Bounding Mesh")
ind = np.where(grain_ids != 0)[0]
submesh = pymesh.submesh(mesh, ind, 0)
grain_ids = grain_ids[ind].astype(int)


# Convert to quadratic with tet_mesh_l2q
print("Converting To Quadratic Tets")
nodes, elements = submesh.vertices, submesh.elements
np.savetxt("lin_nodes.txt", nodes)
np.savetxt("lin_elements.txt", elements, fmt="%i")
os.system("./tet_mesh_l2q lin")
while os.path.exists("lin_l2q_elements.txt") == False:
    time.sleep(10)


# Load quadratic mesh & re-order elements
nodes = np.loadtxt("lin_l2q_nodes.txt").astype("double")
elements = np.loadtxt("lin_l2q_elements.txt").astype("int32")
elements = elements[:, [0, 1, 2, 3, 4, 7, 5, 6, 8, 9]]
cells = [("tetra10", elements)]
mesh = meshio.Mesh(nodes, cells)
print('Generating Element and Node Sets...')
mesh = generate_element_sets(mesh, grain_ids)
mesh = generate_node_sets(mesh, nodes, epsilon)


# Write output
print("Writing .VTK & .INP")
meshio.abaqus.write("XtalMesh.inp", mesh)
meshio.vtk.write("XtalMesh.vtk", mesh)


# Fix XtalMesh.inp
with open("XtalMesh.inp", "r+") as f:
    lines = f.readlines()
    f.seek(0)
    f.truncate()
    idx = lines.index("*Element,type=C3D10MH\n")
    lines[idx] = "*Element, type=C3D10\n"
    f.writelines(lines[:-1])


# Clean-up
os.system("rm -rf Volume_1*")
os.system("rm -rf lin*")


print("FINISHED - Total processing time: ", time.time() - t0, "s\n")
