import subprocess
from subprocess import call
import os
from tempfile import NamedTemporaryFile
import re
import sys
import logging
from contextlib import contextmanager
import getpass
import omero
import omero.cli
from omero.gateway import BlitzGateway
from omero.rtypes import rint, rlong, rstring, robject, unwrap

#DATA_PATH = os.path.join("D:\\", "Users", "Chickens", "Documents", "EPCC", "code_projects", \
#                         "andrewr_test_data")
DATA_PATH = os.path.join("/var", "test_data")
PERMITTED_FILE_EXTS = [".czi"]
OMERO_BIN_PATH = os.path.join("/opt", "omero", "server", "OMERO.server", "bin", "omero")
OMERO_SERVER = "publicomero.bio.ed.ac.uk"
# OMERO_SERVER = "demo.openmicroscopy.org"
# OMERO_SERVER = "127.0.0.1"
OMERO_USER = "jhay1"
# OMERO_USER = "jhay"
# OMERO_USER = "root"
OMERO_PASSWORD = getpass.getpass()
OMERO_GROUP = "rdm_scrapbook"
# OMERO_GROUP = "default"
OMERO_PORT = 4064

# logging config
fmtstr = " Name: %(asctime)s: (%(filename)s): %(levelname)s: %(funcName)s Line: %(lineno)d - %(message)s"
datestr = "%m/%d/%Y %I:%M:%S %p "
# basic logging config
logging.basicConfig(
    filename="uploader_output.log",
    level=logging.DEBUG,
    filemode="w",
    format=fmtstr,
    datefmt=datestr,
)


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

def connect_to_remote(password, username):
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

def import_image(image_file, conn, dataset_id, session_key):
    image_ids = []

    try:
        dataset = conn.getObject("Dataset", dataset_id)

        # import via cli
        client = conn.c

        args = [sys.executable]
        args.append(OMERO_BIN_PATH)
        args.extend(["-s", OMERO_SERVER, "-k", session_key, "-p", str(OMERO_PORT), "import"])
        # Import into current Dataset
        args.extend(["-d", str(dataset.id)])
        logging.debug(image_file)
        args.append(image_file)
        # args.append(pipes.quote(image_file))
        # args.append(image_file.replace(" ", "\ "))
        #args.append("\"".join(["",os.path.abspath(image_file),""]))

        popen = subprocess.Popen(args,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        out, err = popen.communicate()
        print 'out', out
        print 'err', err
        rc = popen.wait()
        if rc != 0:
            raise Exception("import failed: [%r] %s\n%s" % (args, rc, err))
        for x in out.split("\n"):
            if "Image:" in x:
                image_ids.append(long(x.replace('Image:', '')))

    except Exception as e:
        logging.error(e)

    return image_ids

def do_upload():

    call(["ls", "-l", DATA_PATH])

    dataset_id, full_dataset_name = None, None
    cur_subdir = None

    try:
        # Connect to remote omero
        c, cli, remote_conn = connect_to_remote(OMERO_PASSWORD, OMERO_USER)

        for subdir, dirs, files in os.walk(DATA_PATH):

            if subdir != cur_subdir:
                cur_subdir = subdir
                # it's a new subdirectory, therefore new dataset
                dataset_id, full_dataset_name = None, None

            for file in files:
                if file.endswith(tuple(PERMITTED_FILE_EXTS)):
                    if dataset_id is None:
                        dataset_desc = "A dataset"

                        path_parts = subdir.split(os.sep)

                        path_parts_len = len(path_parts)
                        strain = path_parts[path_parts_len - 1]
                        dataset_name = path_parts[path_parts_len - 2]
                        figure = path_parts[path_parts_len - 3]

                        full_dataset_name = "_".join([figure, dataset_name, strain]).replace(" ", "")
                        logging.debug(full_dataset_name)

                        name_cmd = 'name=' + full_dataset_name
                        desc_cmd = "description=" + dataset_desc

                        temp_file = NamedTemporaryFile().name
                        # This temp_file is a work around to get hold of the id of uploaded
                        # datasets from stdout.
                        with open(temp_file, 'w+') as tf, stdout_redirected(tf):
                            cli.onecmd(["obj", "new", "Dataset", name_cmd, desc_cmd])

                        with open(temp_file, 'r') as tf:
                            txt = tf.readline()
                            dataset_id = re.findall(r'\d+', txt)[0]
                        logging.info(":".join(["uploaded dataset ", dataset_id]))
                        remote_ds = remote_conn.getObject("Dataset", rlong(dataset_id))
                        logging.debug(remote_ds.getId())

                    logging.debug(file)
                    filepath = os.path.join(subdir, file)
                    logging.debug(filepath)

                    if dataset_id is not None:
                        image_ids = None
                        # This temp_file is a work around to get hold of the id of uploaded
                        # images from stdout.
                        image_desc = "an image"
                        target_dataset = ":".join(["Dataset", "id", dataset_id])
                        # target_dataset = ":".join(["Dataset", "name", full_dataset_name])
                        if filepath:
                            #cli.onecmd(["import", filepath, '-T', target_dataset, "-g", OMERO_GROUP,
                            #            '--description', image_desc, '--no-upgrade-check'])
                            image_ids = import_image(filepath, remote_conn, dataset_id, c.getSessionId())
                            logging.debug(image_ids)

                            if image_ids is not None:
                                for uploaded_image_id in image_ids:
                                    logging.info(":".join(["uploaded image ", str(uploaded_image_id)]))

                                    remote_img = remote_conn.getObject("Image", rlong(uploaded_image_id))

                                    if remote_img is not None:
                                        logging.debug(remote_img.getId())

    except Exception as e:
        logging.exception("Error")
    finally:
        close_remote_connection(c, cli, remote_conn)

def main():
    logging.debug("hello world!")
    do_upload()

if __name__ == "__main__":
    main()
