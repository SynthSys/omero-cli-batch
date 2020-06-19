# OMERO CLI Batch

This Python script uploads data to an OMERO server in batches


# Description

There are two command line tools packaged in the OMERO CLI Batch toolkit.
The first tool is the 'uploader', which is for depositing data and metadata 
into a target remote OMERO server instance. The second tool is the 'tag 
manager', which is for automatically cleaning and rationalising tag 
annotations on a target remote OMERO server instance.

## Uploader

There are two versions of the CLI tool. The `src/omero_cli_batch/uploader.py`
script is designed for running in a Python3 virtual environment where 
[omero-py](https://pypi.org/project/omero-py/) 5.6.2 is installed. 
The target OMERO server needs to be version 5.6 or higher for this script to 
work. The `src/omero_cli_batch/uploader27.py` script is designed for running 
in a Python2 virtual environment where 
[python-omero](https://anaconda.org/bioconda/python-omero) 5.4.10 is installed.

## Tag Manager

The tag manager - `src/omero_cli_batch/tag_manager.py` offers two main features:

1. An automated cleaning function which will query the specified OMERO server 
database and find any tag annotations that share identical label text values 
and descriptions. Any tags like this are merged into one tag, all objects linked
to duplicate tags are re-linked to the target tag and the duplicate tags are 
then deleted.
2. A tag curation feature that allows the user to specify a target tag ID or 
label text value along with a list of tag IDs/labels which are to be merged into 
the target tag and then deleted. As with (1), all objects linked with tags to be 
merged are re-linked with the target tag. 

# Requirements and running

You must have an OMERO Python virtual environment and the OMERO CLI tools
present in the file system. The best way to achieve this is by deploying
the OMERO server Docker images (https://hub.docker.com/r/openmicroscopy/omero-server)
and running them with the data directory mounted to the container.

## Uploader

### Python 2 - python-omero 5.4.10

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

### Python 3 - omero-py 5.6.1

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

## Tag Manager

The easiest way to run the tag manager is using the CLI in 
`src/omero_cli_batch/tag_manager_cli.py`. Available options are:

```shell script
optional arguments:
  -h, --help            show help message and exit

  # Connection parameters
  -u username, --username username
                        specifies the username for connection to the remote
                        OMERO server
  -s server, --server server
                        specifies the server name of the remote OMERO server
                        to connect
  -o [port], --port [port]
                        specifies the port on the remote OMERO server to
                        connect (default is 4064)
  -a, --password        hidden password prompt for connection to the remote
                        OMERO server

  # Tag management parameters
  -i, --target-tag-id
                        Omero ID of the destination tag for merging and
                        linking objects to
  -l, --target-tag-label
                        Label of the destination tag for merging and linking
                        objects to
  -e, --tag-labels-to-remove
                        List of regex strings for tag labels which are to be
                        merged and removed on the Omero server
  -r, --tags-to-remove
                        List of tag labels which are to be merged and removed
                        on the Omero server
  -d, --dry-run         Instructs the tag manager to report intended changes
                        rather than actually perform the merge and tag
                        deletion process. Non-destructive and allows you to 
                        see what will be changed without actually doing so.
```

Example commands for running the tag manager CLI:

```shell script
$ cd src

# merge all datasets/images associated with tags withs labels 'arch%' and 
# 'amoeb%' into one existing tag labelled 'amoebozoa'
$ python -m omero_cli_batch.tag_manager_cli -u root -s 172.17.0.3 -l amoebozoa \
  -e arch% amoeb% -r 245 253 -o 4064

# merge all datasets/images associated with tags withs labels 'arch%' and 
# 'amoeb%' and tags with IDs 245 and 253 into one existing tag with ID 233
$ python -m omero_cli_batch.tag_manager_cli -u root -s 172.17.0.3 -l amoebozoa \
  -e arch% amoeb% -o 4064

# merge all datasets/images associated with tags with labels 'cell wall' 
# into one existing tag with label 'cell'
$ python -m omero_cli_batch.tag_manager_cli -u root -s 172.17.0.3 -l cell \
  -e "cell wall" -o 4064

# error: Cannot specify both target tag ID and target tag label; use 
# one or the other
$ python -m omero_cli_batch.tag_manager_cli -u root -s 172.17.0.3 -i 233 \
  -l amoebozoa -e arch% amoeb% -o 4064

# merge all datasets/images associated with tags with labels 'arch%' 
# and 'amoeb%' into one existing tag with ID 233
$ python -m omero_cli_batch.tag_manager_cli -u root -s 172.17.0.3 -i 233 \
  -e arch% amoeb% -o 4064

# merge all datasets/images associated with tags with labels 'arch%' 
# and 'amoeb%' and tags with IDs 245 and 253 into one existing tag with ID 233
$ python -m omero_cli_batch.tag_manager_cli -u root -s 172.17.0.3 -i 233 \
  -e arch% amoeb% -r 245 253 -o 4064

# merge all datasets/images associated with tags with label '"Screaming" Hairy l'éléphan%' 
# into one existing tag with ID 233
$ python -m omero_cli_batch.tag_manager_cli -u root -s 172.17.0.3 -i 233 \ 
    -e "\"Screaming\" Hairy l'éléphan%" -o 4064
```

# Note

This project has been set up using PyScaffold 3.2.3. For details and usage
information on PyScaffold see https://pyscaffold.org/.
