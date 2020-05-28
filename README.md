# OMERO CLI Batch

This Python script uploads data to an OMERO server in batches


# Description

There are two versions of the CLI tool. The `src/omero_cli_batch/uploader.py`
script is designed for running in a Python3 virtual environment where 
[omero-py](https://pypi.org/project/omero-py/) 5.6.2 is installed. 
The target OMERO server needs to be version 5.6 or higher for this script to 
work. The `src/omero_cli_batch/uploader27.py` script is designed for running 
in a Python2 virtual environment where 
[python-omero](https://anaconda.org/bioconda/python-omero) 5.4.10 is installed.


# Requirements and running

You must have an OMERO Python virtual environment and the OMERO CLI tools
present in the file system. The best way to achieve this is by deploying
the OMERO server Docker images (https://hub.docker.com/r/openmicroscopy/omero-server)
and running them with the data directory mounted to the container.

## Python 2 - python-omero 5.4.10

For the **Python 2** version, here are the instructions:

```shell script

docker pull openmicroscopy/omero-server:5.4.10

docker run -d --name postgres -e POSTGRES_PASSWORD=postgres postgres

docker run -d --name omero-server_5.4.10 --link postgres:db
    -e CONFIG_omero_db_user=postgres \
    -e CONFIG_omero_db_pass=postgres \
    -e CONFIG_omero_db_name=postgres \
    -e ROOTPASS=omero-root-password \
    -p 4063:4063 -p 4064:4064 \
    -v '/home/user/omero_data:/var/test_data:ro'
    -v '/home/user/code/omero-cli-batch:/opt/omero/server/omero-cli-batch:ro'
    openmicroscopy/omero-server:5.4.10

# need to install the OMERO libraries on the 5.4.10 server
docker exec -uroot -it omero-server_5.4.10 /bin/bash
yum install -y openssl-devel
ln -s /usr/lib64/libssl.so.1.0.2k /usr/lib64/libssl.so.1.0.0
ln -s /usr/lib64/libcrypto.so.1.0.2k /usr/lib64/libcrypto.so.1.0.0
exit

docker exec -it omero-server_5.4.10 /bin/bash
cd ~
#install Miniconda to /opt/omero/server/miniconda2
wget https://repo.anaconda.com/miniconda/Miniconda2-latest-Linux-x86_64.sh
chmod u+x Miniconda2-latest-Linux-x86_64.sh
./Miniconda2-latest-Linux-x86_64.sh
conda create -n omero python=2.7
conda activate omero
conda install -c bioconda python-omero=5.4.10

# add omero jars to classpath
ln -s /opt/omero/server/OMERO.server-5.4.10-ice36-b105/lib/ /opt/omero/server/miniconda2/envs/omero/lib/lib

# run the uploader27 script
/opt/omero/server/omero-cli-batch/src/omero_cli_batch/uploader27.py
```

## Python 3 - omero-py 5.6.1

For the **Python 3** version, here are the instructions:

```shell script
docker pull openmicroscopy/omero-server:5.6.1

docker run -d --name postgres -e POSTGRES_PASSWORD=postgres postgres

docker run -d --name omero-server_5.6.1 --link postgres:db \
    -e CONFIG_omero_db_user=postgres \
    -e CONFIG_omero_db_pass=postgres \
    -e CONFIG_omero_db_name=postgres \
    -e ROOTPASS=omero-root-password \
    -p 4063:4063 -p 4064:4064 \
    -v '/home/user/omero_data:/var/test_data:ro' \
    -v '/home/user/code/omero-cli-batch:/opt/omero/server/omero-cli-batch:ro' \
    openmicroscopy/omero-server:5.6.1

docker exec -it -uroot omero-server_5.6.1 /bin/bash
source /opt/omero/server/venv3/bin/activate
pip install backoff
exit

docker exec -it omero-server_5.6.1 /bin/bash
source /opt/omero/server/venv3/bin/activate

# run the uploader script
python3 /opt/omero/server/omero-cli-batch/src/omero_cli_batch/uploader.py
```


# Note

This project has been set up using PyScaffold 3.2.3. For details and usage
information on PyScaffold see https://pyscaffold.org/.
