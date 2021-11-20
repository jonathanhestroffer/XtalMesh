# XtalMesh - Tetrahedral Meshing of Polycrystals

<img src="docs/title.PNG" width=100% height=100%>

XtalMesh is an open-source code and containerized software suite used to generate tetrahedral finite-element mesh of polycrystals, and works well for both synthetic and experimental microstructures. The real value of XtalMesh lies in its ability to produce high-fidelity mesh representations of complex grain morphologies, particularly useful when studying local mechanical behavior near/at microstructural hetergoneities like grain boundaries and triple junctions. 

XtalMesh makes use of the powerful and robust tetrahedral meshing code [fTetWild](https://github.com/wildmeshing/fTetWild) as well as geometry processing libraries [PyMesh](https://github.com/PyMesh/PyMesh) and [libigl](https://github.com/libigl/libigl) with python bindings. This collection of software enables the design of customized meshing workflows in a simple python environment.

## Installation

#### Pulling Docker Image (Recommended)

Install and run [Docker](https://docs.docker.com/), then within your command-line shell of choice, pull the XtalMesh Docker image.

```bash
docker pull jonathanhestroffer/xtalmesh
```

#### Building Image from Dockerfile

While a much slower process, you can also choose to build XtalMesh from the Dockerfile provided. In a directory containing only the Dockerfile provided, run the following command:

```bash
docker build -t jonathanhestroffer/xtalmesh .
```

Note: Any edits made to the Dockerfile to achieve a customized build might affect the stability of XtalMesh.

## Basic Usage

The following is a tutorial of XtalMesh using the example files provided in the [SyntheticTest](SyntheticTest) directory of this repository. Save these to your host work directory.

#### Preparing Input

XtalMesh requires four ```.txt``` files and they include:

- nodes.txt
- nodetype.txt
- triangles.txt
- facelabels.txt

These must be generated for your 3D microstructure using [DREAM.3D](http://dream3d.bluequartz.net/). The ```.dream3d``` pipeline used to create these files as well as the files themselves used in this tutorial can be found in [SyntheticTest](SyntheticTest).

#### Running Docker Container

The preferred method of running the Docker container is with the command ```docker run --rm -it -v <host-directory>:<container-directory> jonathanhestroffer/xtalmesh```.

Example:
```bash
docker run --rm -it -v F:/SyntheticTest/:/work jonathanhestroffer/xtalmesh
```

The above deploys a container with directory ```/work``` synced to the ```/SyntheticTest``` directory on the host machine. During execution of XtalMesh, all output files will be generated inside the host directory.

Once inside the container, change to the ```/XtalMesh``` directory.

```bash
cd XtalMesh
```

#### Smoothing

XtalMesh requires the execution of just two python scripts; the first performs Laplacian smoothing of the voxelated microstructure, and can be run from the ```/XtalMesh``` directory as ```python3 xtal_smoother.py <num-iters> <lambda>```

Example:
```
python3 xtal_smoother.py 20 1.0
```

Command Line Arguments:
```
<num-iters> INT               Number of Laplacian smoothing iterations
<lambda> FLOAT                Laplacian operator, λ > 0
```

Once smoothing is complete, all individual feature surface meshes will be written to ```/work/GrainSTLs``` directory. These will then be stitched together to form ```Whole.stl```, available in ```/work``` directory, which will be used for subsequent volume meshing.

#### Meshing

After smoothing, to create volume mesh for the microstructure, run another python script in the ```/XtalMesh``` directory as ```python3 xtal_mesher.py <edge-length> <epsilon>```. This will run the [fTetWild](https://github.com/wildmeshing/fTetWild) meshing code.

Example:
```
python3 xtal_mesher.py 0.05 1e-3
```

Command Line Arguments:
```
<edge-length> FLOAT          Target element edge-length, ratio of the body diagonal (e.g., 0.05 = b/20               
<epsilon> FLOAT              Surface mesh deviation tolerance, ratio of the body diagonal (e.g., 1e-3 = b/1000)
```

Apart from the input microstructure size and resolution, values of ```<edge-length>``` and ```<epsilon>``` can largely affect RAM usage and runtime. Start with values of 0.05 and 1e-3 respectively and adjust as needed. If more RAM is required than what is allocated to the Docker container, then this process will be killed.

You can check CPU and RAM usage of the running container using:

```bash
docker stats
```

#### Output & Visualization

When meshing is complete, an ABAQUS ```.inp``` and VTK ```.vtk``` file are produced. The mesh can most easily be viewed by opening ```XtalMesh.vtk``` with [ParaView](https://www.paraview.org/).

## Important Tips

- The number of input vertices is preserved during surface smoothing. This means smoother grain boundaries and triple junctions can be achieved with higher resolution input microstructures. However, be wary of excessive input resolution as this will have a major impact on memory usage and runtime.