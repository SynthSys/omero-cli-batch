ARG BASE_CONTAINER=openmicroscopy/omero-server:5.4.10
FROM $BASE_CONTAINER

ARG OMERO_VERSION=5.4.10
ARG ZEROC_ICE_PACKAGE=zeroc-ice36-python

LABEL maintainer="SBS Research Data Management <bio_rdm@ed.ac.uk>"
ARG NB_USER="omero-server"

USER root

# RUN yum -y install libssl1.0-devel
RUN ln -s /usr/lib64/libssl.so.1.0.2k /usr/lib64/libssl.so.1.0.0
RUN ln -s /usr/lib64/libcrypto.so.1.0.2k /usr/lib64/libcrypto.so.1.0.0

USER omero-server
WORKDIR /opt/omero/server

ENV CONDA_DIR=/opt/omero/server/miniconda2 \
    SHELL=/bin/bash \
    LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8

ENV PATH=$CONDA_DIR/bin:$PATH \
    HOME=/opt/omero/server \
    OMERO_VERSION=$OMERO_VERSION

RUN cd /tmp && \
    wget --quiet https://repo.anaconda.com/miniconda/Miniconda2-latest-Linux-x86_64.sh && \
    echo "383fe7b6c2574e425eee3c65533a5101e68a2d525e66356844a80aa02a556695 *Miniconda2-latest-Linux-x86_64.sh" | sha256sum -c - && \
    /bin/bash Miniconda2-latest-Linux-x86_64.sh -f -b -p $CONDA_DIR && \
    rm Miniconda2-latest-Linux-x86_64.sh && \
    # echo "conda 4.7.12" >> $CONDA_DIR/conda-meta/pinned && \
    $CONDA_DIR/bin/conda config --system --prepend channels conda-forge && \
    $CONDA_DIR/bin/conda config --system --prepend channels bioconda && \
    $CONDA_DIR/bin/conda config --system --set auto_update_conda false && \
    $CONDA_DIR/bin/conda config --system --set show_channel_urls true && \
    $CONDA_DIR/bin/conda install --quiet --yes conda && \
    $CONDA_DIR/bin/conda update --all --quiet --yes && \
    conda list python | grep '^python ' | tr -s ' ' | cut -d '.' -f 1,2 | sed 's/$/.*/' >> $CONDA_DIR/conda-meta/pinned && \
    conda clean --all -f -y && \
    rm -rf /opt/omero/server/.cache/yarn

# Install OMERO Python libs
# Cleanup temporary files
# Correct permissions
# Do all this in a single RUN command to avoid duplicating all of the
# files across image layers when the permissions change
#RUN $CONDA_DIR/bin/conda install --quiet --yes \
#    "python-omero=${OMERO_VERSION}" && \
#    # 'openssl=1.0.*' && \
#    $CONDA_DIR/bin/conda clean --all -f -y && \
#    rm -rf /opt/omero/server/.cache/yarn

USER root

# Found we have to install the old SSL and crypto libraries, probably due to OpenJDK base image update
#RUN cd /tmp && \
#    wget --quiet http://nl.archive.ubuntu.com/ubuntu/pool/main/g/glibc/libc6-udeb_2.27-3ubuntu1_amd64.udeb && \
#    wget --quiet http://nl.archive.ubuntu.com/ubuntu/pool/main/o/openssl/libcrypto1.0.0-udeb_1.0.2g-1ubuntu4_amd64.udeb && \
#    wget --quiet http://nl.archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.0.0-udeb_1.0.2g-1ubuntu4_amd64.udeb && \
#    echo "52e0bb2c1f552da8b7120ff3d6a2b38a *libc6-udeb_2.27-3ubuntu1_amd64.udeb" && \
#    echo "d8c283d6b2b587c6b58e163de75a7f66 *libcrypto1.0.0-udeb_1.0.2g-1ubuntu4_amd64.udeb" && \
#    echo "83633d8dc2c32363914282ac32087d7e *libssl1.0.0-udeb_1.0.2g-1ubuntu4_amd64.udeb" && \
#    dpkg -i libc6-udeb_2.27-3ubuntu1_amd64.udeb && \
#    dpkg -i libcrypto1.0.0-udeb_1.0.2g-1ubuntu4_amd64.udeb && \
#    dpkg -i libssl1.0.0-udeb_1.0.2g-1ubuntu4_amd64.udeb

USER $NB_USER
WORKDIR $HOME