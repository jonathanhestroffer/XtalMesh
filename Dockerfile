FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN \
	apt-get update && apt-get -y install \
	libeigen3-dev \
	libgmp-dev \
	libgmpxx4ldbl \
	libmpfr-dev \
	libboost-dev \
	libboost-thread-dev \
	libtbb-dev \
	libssl-dev \
	python3-dev \
	python3-vtk7 \
	python3-setuptools \
	python3-numpy \
	python3-scipy \
	python3-nose \
	python3-pip \
	python3-networkx \
	python3-meshio \
	python3-tqdm \
	git \
	make \
	cmake \
	wget \
	gcc \
	g++


# XtalMesh
RUN \
	git clone https://github.com/jonathanhestroffer/XtalMesh.git


# PyMesh
RUN \
	git clone https://github.com/PyMesh/PyMesh.git	
ENV PYMESH_PATH /PyMesh
RUN \
	cd PyMesh && git submodule update --init	
RUN \
	cd $PYMESH_PATH/third_party && \
	python3 build.py all	
RUN \
	cd $PYMESH_PATH && \
	mkdir build && \
	cd build && \
	cmake .. && \
	make && \
	make tests	
RUN \
	cd $PYMESH_PATH && \
	python3 setup.py install


# fTetWild
RUN \
	git clone https://github.com/wildmeshing/fTetWild.git
RUN \
	cd fTetWild && \
	mkdir build && \
	cd build && \
	cmake .. && \
	make


# libigl
RUN \
	git clone https://github.com/libigl/libigl-python-bindings.git
RUN \
	cd libigl-python-bindings && \
	python3 setup.py install && \
	python3 setup.py test


RUN \
	pip install numba && \
	pip install pandas
