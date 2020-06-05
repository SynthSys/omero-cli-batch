from contextlib import contextmanager, closing
import os
import re
import sys
from tempfile import NamedTemporaryFile
import getpass
import random
import subprocess
import threading
import time

import omero
import omero.cli
from omero.gateway import BlitzGateway
from omero import sys as om_sys
from omero import rtypes
from omero.rtypes import rlong
from omero import model

OMERO_SERVER = '172.17.0.3'
OMERO_PORT = 4064

DATASET_NAMES = ['test_dataset1', 'test_dataset2', 'test_dataset3', 'test_dataset4', 'test_dataset5']
TAG_LABELS = ['nucleus', 'isoleucine', 'phenylalanine', 'valine', 'Histidine', 'glucose', 'cytosol',
                'flagella', 'cillia', 'cyanobacteria', 'myxobacteria', 'actinomycete', 'Methanosarcina',
                'Cytoneme', 'prokaryote', 'bacteria', 'archaea', 'chromosome', 'dna', 'cell', 'organelle',
                'mitochondrion', 'vacuole', 'plant', 'algae', 'lysosome', 'cell nucleus', 'endoplasmic reticulum',
                'organism', 'cytoplasm', 'plastid', 'chloroplast', 'golgi apparatus', 'cytoskeleton', 'mitosis',
                'domain', 'vesicle', 'protist', 'cell division', 'amoebozoa', 'excavata', 'protista', 'alga',
                'monophyletic', 'protozoa', 'sar supergroup', 'animal', 'cyanobacteria', 'meiosis', 'cell wall',
                'acritarch', 'diploid', 'haploid', 'cell membrane', 'chemotaxis']

DATASET_DESCRIPTIONS = []
TAG_DESCRIPTIONS = ['oligomeric motors that can bind two or more cytoskeletal filaments',
                    'a fluorophore, enabling visualization and quantification of coupled enzymes on gels',
                    'a substrate peptide that contains the non-natural amino acid Sox',
                    'Bacteria exhaust the glucose before consuming the other carbon source',
                    'Enzyme-linked-immunosorbent assay',
                    'extracellular stimulation by physiological ligands',
                    'inhibition of protein activities by small molecule inhibitors',
                    'alterations in protein-expression levels by RNA interference or overexpression',
                    'biomolecule that transfers information in a signalling network',
                    'cholesterol inhibits the movement of phospholipid fatty acid chains',
                    'At cold temperatures, cholesterol interferes with fatty acid chain interactions',
                    'The hydrophobic domain consists of one, multiple, or a combination of α-helices and β sheet '
                    'protein motifs', 'Covalently bound to single or multiple lipid molecules',
                    'the molecule dissociates to carry on its work in the cytoplasm']
IMAGE_PATH = '/home/jhay/Downloads/Download-Cat-PNG-Clipart.png'

OMERO_BIN_PATH = os.path.join("/home", "jhay", ".conda", "envs", "omeropy", "bin", "omero")
USERNAME = 'root'
PASSWORD = 'omero-root-password'
OMERO_GROUP = 'system'

exit_condition = False

DATASETS_BY_ID_QUERY = "select d from Dataset d where d.id in :dids"

IMAGES_BY_ID_QUERY = "select i from Image i where i.id in :iids"

# '/home/jhay/.conda/envs/myenv/bin/python', '/home/jhay/.conda/envs/omeropy/bin/omero', '-s', '172.17.0.3', '-k',
# 'b7377305-1959-4ea1-ba02-4f7c0694178a', '-p', '4064', 'import', '-g', 'system', '-d', '113',
# '/home/jhay/Downloads/Download-Cat-PNG-Clipart.png', '--no-upgrade-check'
#
# /home/jhay/.conda/envs/myenv/bin/python /home/jhay/.conda/envs/omeropy/bin/omero -s 172.17.0.3 -k
# b7377305-1959-4ea1-ba02-4f7c0694178a -p 4064 import -g system -d 113
# /home/jhay/Downloads/Download-Cat-PNG-Clipart.png --no-upgrade-check

def fileno(file_or_fd):
    fd = getattr(file_or_fd, 'fileno', lambda: file_or_fd)()
    if not isinstance(fd, int):
        raise ValueError("Expected a file (`.fileno()`) or a file descriptor")
    return fd


@contextmanager
def stdout_redirected(to=os.devnull, stdout=None):
    if stdout is None:
        stdout = sys.stdout

    stdout_fd = fileno(stdout)
    # copy stdout_fd before it is overwritten
    # NOTE: `copied`is inheritable on Windows when duplicating a standard stream
    with os.fdopen(os.dup(stdout_fd), 'wb') as copied:
        stdout.flush()  # flush library buffers that dup2 knows nothing about
        try:
            os.dup2(fileno(to), stdout_fd)  # $ exec >&to
        except ValueError:  # filename
            with open(to, 'wb') as to_file:
                os.dup2(to_file.fileno(), stdout_fd)  # $ exec > to
        try:
            yield stdout  # allow code to be run with the redirected stdout
        finally:
            # restore stdout to its previous value
            # NOTE: dup2 makes stdout_fd inheritable unconditionally
            stdout.flush()
            os.dup2(copied.fileno(), stdout_fd)  # $ exec >&copied


def import_image(image_file, conn, dataset_id, session_key):
    image_ids = []

    try:
        dataset = conn.getObject("Dataset", dataset_id)

        # import via cli
        client = conn.c

        args = [sys.executable]
        args.append(OMERO_BIN_PATH)
        args.extend(["-s", OMERO_SERVER, "-k", session_key, "-p", str(OMERO_PORT), "import"])
        args.extend(["-g", OMERO_GROUP])
        # Import into current Dataset
        args.extend(["-d", str(dataset.id)])
        print(image_file)
        args.append(image_file)
        args.append("--no-upgrade-check")

        print(args)
        # args.append(pipes.quote(image_file))
        # args.append(image_file.replace(" ", "\ "))
        #args.append("\"".join(["",os.path.abspath(image_file),""]))

        popen = subprocess.Popen(args,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 universal_newlines=True) # output as string
        out, err = popen.communicate()
        print('wtf')

        #print "out", out
        #print "err", err

        rc = popen.wait()
        if rc != 0:
            raise Exception("import failed: [%r] %s\n%s" % (args, rc, err))
        for x in out.split("\n"):
            if "Image:" in x:
                image_ids.append(int(x.replace('Image:', '')))

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        raise e

    return image_ids


def connect_to_remote(username, password):
    c = omero.client(host=OMERO_SERVER, port=OMERO_PORT,
                     args=["--Ice.Config=/dev/null", "--omero.debug=1"])
    c.createSession(username, password)
    remote_conn = BlitzGateway(client_obj=c)
    cli = omero.cli.CLI()
    cli.loadplugins()
    cli.set_client(c)
    # del os.environ["ICE_CONFIG"]
    return c, cli, remote_conn


def close_remote_connection(c, cli, remote_conn):
    remote_conn.close()
    c.closeSession()
    cli.close()


def create_dataset(cli, dataset_name, dataset_desc):
    name_cmd = 'name=' + dataset_name
    desc_cmd = "description=" + dataset_desc

    temp_file = NamedTemporaryFile().name
    # This temp_file is a work around to get hold of the id of uploaded
    # datasets from stdout.
    with open(temp_file, 'w+') as tf, stdout_redirected(tf):
        cli.onecmd(["obj", "new", "Dataset", name_cmd, desc_cmd])

    with open(temp_file, 'r') as tf:
        txt = tf.readline()
        dataset_id = re.findall(r'\d+', txt)[0]
    print(":".join(["uploaded dataset ", dataset_id]))

    return dataset_id


def create_tag(cli, tag_name, tag_desc):
    label_cmd = 'textValue=' + tag_name
    desc_cmd = "description=" + tag_desc

    temp_file = NamedTemporaryFile().name
    # This temp_file is a work around to get hold of the id of uploaded
    # datasets from stdout.
    with open(temp_file, 'w+') as tf, stdout_redirected(tf):
        cli.onecmd(["obj", "new", "TagAnnotation", label_cmd, desc_cmd])

    with open(temp_file, 'r') as tf:
        txt = tf.readline()
        tag_id = re.findall(r'\d+', txt)[0]
    print(":".join(["uploaded tag ", tag_id]))

    return tag_id


def update_object_tag(client, objects_list, tag_id):
    for object in objects_list:
        print(object)
        print(tag_id)
        print(model.TagAnnotationI(tag_id, False))
        print(object.getId())
        link = None
        if isinstance(object, model.DatasetI):
            print('here')
            link = model.DatasetAnnotationLinkI()
            link.setParent(model.DatasetI(object.getId(), False))
            link.setChild(model.TagAnnotationI(tag_id, False))
        elif isinstance(object, model.ImageI):
            link = model.ImageAnnotationLinkI()
            link.setParent(model.ImageI(object.getId(), False))
            link.setChild(model.TagAnnotationI(tag_id, False))

        tag_link = client.getSession().getUpdateService().saveAndReturnObject(link)


def find_objects_by_query(client, query, params):
    query_service = client.getSession().getQueryService()
    # query = "select p from Project p left outer join fetch p.datasetLinks as links left outer join fetch links.child as dataset where p.id =:pid"

    objects = query_service.findAllByQuery(query, params)

    return objects


def populate_test_data(client, cli, remote_conn):
    image_ids = []
    query_service = client.getSession().getQueryService()
    params = om_sys.Parameters()
    params.map = {}

    for dataset_name in DATASET_NAMES:
        dataset_id = create_dataset(cli, dataset_name, 'Test dataset')
        print(dataset_id)

        # get created dataset object
        dataset_ids = map(rtypes.rlong, [dataset_id]) # wrap dataset ID in list since it's only one ID to map
        params.map = {'dids': rtypes.rlist(dataset_ids)}
        datasets = query_service.findAllByQuery(DATASETS_BY_ID_QUERY, params)

        for i in range(0, 4):
            tag_label = random.choice(TAG_LABELS)
            tag_desc = random.choice(TAG_DESCRIPTIONS)
            tag_id = create_tag(cli, tag_label, tag_desc)
            update_object_tag(client, datasets, rtypes.rlong(tag_id))

        try:
            image_ids = import_image(IMAGE_PATH, remote_conn, dataset_id, client.getSessionId())

            # get created image object
            image_ids = map(rtypes.rlong, image_ids) # wrap image ID in list since it's only one ID to map
            params.map = {'iids': rtypes.rlist(image_ids)}
            images = query_service.findAllByQuery(IMAGES_BY_ID_QUERY, params)

            for image in images:
                for i in range(0, 4):
                    tag_label = random.choice(TAG_LABELS)
                    tag_desc = random.choice(TAG_DESCRIPTIONS)
                    tag_id = create_tag(cli, tag_label, tag_desc)
                    update_object_tag(client, [image], rtypes.rlong(tag_id))
        except Exception as e:
            print(IMAGE_PATH)
        print(image_ids)


def ping_session(interval, client):
    global exit_condition
    ping_count = 0
    while True:
        if exit_condition == False:
            ping_count = ping_count + 1
            print("pinging session: {}".format(ping_count))
            keys = client.getInputKeys()
        else:
            break

        time.sleep(interval)


def main():
    print("hello world!")

    c, cli, remote_conn = connect_to_remote(USERNAME, PASSWORD)

    # run session ping function as daemon to keep connection alive
    keep_alive_thread = threading.Thread(target=ping_session, args=([60, c]))
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    populate_test_data(c, cli, remote_conn)

    global exit_condition
    exit_condition = True
    close_remote_connection(c, cli, remote_conn)


if __name__ == "__main__":
    print('wtf')
    main()
