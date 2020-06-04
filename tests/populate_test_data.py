from contextlib import contextmanager, closing
import os
import re
import sys
from tempfile import NamedTemporaryFile
import getpass
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
IMAGE_PATH = '/home/jhay/Downloads/Download-Cat-PNG-Clipart.png'

OMERO_BIN_PATH = os.path.join("/home", "jhay", ".conda", "envs", "omeropy", "bin", "omero")
USERNAME = 'root'
PASSWORD = 'omero-root-password'
OMERO_GROUP = 'system'

exit_condition = False


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


def populate_test_data(client, cli, remote_conn):
    image_ids = []

    for dataset_name in DATASET_NAMES:
        dataset_id = create_dataset(cli, dataset_name, 'Test dataset')

        try:
            image_ids = import_image(IMAGE_PATH, remote_conn, dataset_id, client.getSessionId())
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
