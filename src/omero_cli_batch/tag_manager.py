from contextlib import contextmanager, closing
import os
import re
import sys
from tempfile import NamedTemporaryFile
import getpass
import subprocess

import omero
import omero.cli
from omero.gateway import BlitzGateway
from omero import sys as om_sys
from omero import rtypes
from omero.rtypes import rlong
from omero import model

# OMERO_SERVER = 'demo.openmicroscopy.org'
OMERO_SERVER = '172.17.0.3'
OMERO_PORT = 4064
IMAGE_PATH = '/home/jhay/Downloads/Download-Cat-PNG-Clipart.png'
OMERO_BIN_PATH = os.path.join("/opt", "omero", "server", "OMERO.server", "bin", "omero")
OMERO_BIN_PATH = os.path.join("/home", "jhay", ".conda", "envs", "omeropy", "bin", "omero")
USERNAME = 'jhay'
PASSWORD = ''
OMERO_GROUP = 'system'

# Retrieve annotations by associated dataset ID
ANNOS_BY_DATASET_QUERY = "select a from Annotation a where a.id in \
            (select link.child.id from DatasetAnnotationLink link where link.parent.id = :did)"

# Retrieve annotations by associated image ID
ANNOS_BY_IMAGE_QUERY = "select a from Annotation a where a.id in \
            (select link.child.id from ImageAnnotationLink link where link.parent.id = :iid)"

# Find objects by tag text
PROJECTS_BY_TAG_QUERY = "select p from Project p left outer join fetch p.annotationLinks as alinks \
             left outer join fetch alinks.child as annotation where alinks.child.textValue like :anno_text"

DATASETS_BY_TAG_QUERY = "select d from Dataset d left outer join fetch d.annotationLinks as alinks \
             left outer join fetch alinks.child as annotation where alinks.child.textValue like :anno_text"

IMAGES_BY_TAG_QUERY = "select i from Image i left outer join fetch i.annotationLinks as alinks \
             left outer join fetch alinks.child as annotation where alinks.child.textValue like :anno_text"
'''
Predicates for all scenarios: Multiple tags with the same name, different ID, same description (or null/empty 
    description)

Scenario 1
    * Two or more datasets share an identical tag (i.e. tag object ID is the same for all)
    * There are other tag(s) that have the same name and description as that tag, but none are used by any dataset
    * When the tag manager script is run, it should if necessary, move the datasets to use the tag with the minimum ID 
    value and delete all of the remaining duplicate tags

Scenario 2
    * One or more datasets use a duplicate tag (i.e. tag object IDs are different but names and descriptions are the
    same
    * When the tag manager script is run, it should move all datasets to use the same identical tag with the minimum
    ID value and delete all of the remaining duplicate tags

Scenario 2
    * One or more images use a duplicate tag (i.e. tag object IDs are different but names and descriptions are the
    same
    * When the tag manager script is run, it should move all images to use the same identical tag with the minimum
    ID value and delete all of the remaining duplicate tags
'''

# Scenario 1
DUPLICATE_TAGS_S1_QUERY = "select a from Annotation a, DatasetAnnotationLink l, Dataset d \
    where (select count(*) from Annotation a2 \
    where  a.textValue = a2.textValue \
    and a.description = a2.description) > 1 \
    or (select count(*) from Annotation a2 \
    where a.textValue = a2.textValue \
    and coalesce(a.description, '') = '' \
    and coalesce(a2.description, '') = '') > 1 \
    and l.child = a.id \
    and d.id = l.parent \
    order by a.textValue, a.id"

# Scenario 2
DUPLICATE_TAGS_S2_QUERY = "select a from Annotation a \
    where (select count(*) from Annotation a2 \
    where  a.textValue = a2.textValue \
    and a.description = a2.description) > 1 \
    or (select count(*) from Annotation a2 \
    where a.textValue = a2.textValue \
    and coalesce(a.description, '') = '' \
    and coalesce(a2.description, '') = '') > 1 \
    order by a.textValue, a.id"

# Scenario 3
DUPLICATE_TAGS_S3_QUERY = "select a from Annotation a, ImageAnnotationLink l, Image i \
    where (select count(*) from Annotation a2 \
    where  a.textValue = a2.textValue \
    and a.description = a2.description) > 1 \
    or (select count(*) from Annotation a2 \
    where a.textValue = a2.textValue \
    and coalesce(a.description, '') = '' \
    and coalesce(a2.description, '') = '') > 1 \
    and l.child = a.id \
    and i.id = l.parent \
    order by a.textValue, a.id"

DATASETS_BY_TAG_ID_QUERY = "select d from Dataset d left outer join fetch d.annotationLinks as alinks \
             left outer join fetch alinks.child as annotation where alinks.child.id in :aids"

IMAGES_BY_TAG_ID_QUERY = "select i from Image i left outer join fetch i.annotationLinks as alinks \
             left outer join fetch alinks.child as annotation where alinks.child.id in :aids"


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


def query_remote(cli):
    # invoke login
    # cli.invoke(["login"])
    cli.invoke(["hql", "-q", "'select g.name from ExperimenterGroup g'"])
    # cli.invoke(["import", "---errs", stderr.name, "---file", stdout.name, "--no-upgrade-check", path, "-d", datasetId])


def find_objects_by_query(client, query, params):
    query_service = client.getSession().getQueryService()
    # query = "select p from Project p left outer join fetch p.datasetLinks as links left outer join fetch links.child as dataset where p.id =:pid"

    objects = query_service.findAllByQuery(query, params)

    return objects


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


# def upload_to_omero_cli(conn,imagePath,imgSrc):
def upload_to_omero_cli(cli, imagePath, dataset_id):
    # import via cli
    cmd = ["import", "-d", dataset_id, '-u', USERNAME, '-w', PASSWORD,
           '-s', OMERO_SERVER, '-p', str(OMERO_PORT), imagePath]
    print(cmd)

    image_id = None
    # invoke login
    # cli.invoke("login")
    # cli.invoke("hql -q 'select g.name from ExperimenterGroup g'")
    temp_file = NamedTemporaryFile().name

    with open(temp_file, 'w+') as tf, stdout_redirected(tf):
        cli.invoke(cmd)

    with open(temp_file, 'r') as tf:
        for line in tf:
            print(line)

            res = re.findall('Image:(\d+)', line)

            if len(res) > 0:
                image_id = res[0]

    print(image_id)


def update_dataset_tag(client, datasets_list, tag_id):
    for dataset in datasets_list:
        link = model.DatasetAnnotationLinkI()
        link.setParent(model.DatasetI(dataset.getId().getValue(), False))
        link.setChild(model.TagAnnotationI(tag_id, False))
        tag_link = client.getSession().getUpdateService().saveAndReturnObject(link)


def update_image_tag(client, images_list, tag_id):
    for image in images_list:
        link = model.ImageAnnotationLinkI()
        link.setParent(model.DatasetI(image.getId().getValue(), False))
        link.setChild(model.TagAnnotationI(tag_id, False))
        tag_link = client.getSession().getUpdateService().saveAndReturnObject(link)


def delete_tags(client, tag_id_list, session_key):
    for tag_id in tag_id_list:
        args = [sys.executable]
        args.append(OMERO_BIN_PATH)
        args.extend(["-s", OMERO_SERVER, "-k", session_key, "-p", str(OMERO_PORT), "-g", OMERO_GROUP])
        args.append("delete")
        # args.extend(["-g", OMERO_GROUP])
        # Import into current Dataset
        args.append(':'.join(['TagAnnotation', str(tag_id)]))
        # args.append("--no-upgrade-check")

        popen = subprocess.Popen(args,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 universal_newlines=True)  # output as string
        out, err = popen.communicate()

        # print "out", out
        # print "err", err

        anno_ids = []
        rc = popen.wait()
        if rc != 0:
            raise Exception("import failed: [%r] %s\n%s" % (args, rc, err))
        for x in out.split("\n"):
            if "TagAnnotation:" in x:
                anno_ids.append(str(x.replace('TagAnnotation:', '')))


def delete_duplicate_tags(c, cli, remote_conn):
    params = om_sys.Parameters()
    params.map = {}

    anno_list = find_objects_by_query(c, DUPLICATE_TAGS_S1_QUERY, params)
    anno_list.extend(find_objects_by_query(c, DUPLICATE_TAGS_S2_QUERY, params))
    # print(anno_list)

    cur_tag_name, cur_tag_id = None, None
    duplicate_tag_ids = []

    for anno in anno_list:
        if isinstance(anno, model.TagAnnotationI):
            tag_name = anno.getTextValue().getValue()
            tag_id = anno.getId().getValue()
            print(tag_name)
            print(cur_tag_name)
            print(tag_id)
            print(cur_tag_id)

            if tag_name != cur_tag_name and tag_id != cur_tag_id:
                print("changing")
                # it's a fresh tag; find all datasets for tag and update them
                # params.map = {'aid': rtypes.rlong(cur_tag_id)}
                if len(duplicate_tag_ids) > 0:
                    print('here')
                    print(duplicate_tag_ids)
                    anno_ids = map(rtypes.rlong, duplicate_tag_ids)
                    print(anno_ids)
                    params.map = {'aids': rtypes.rlist(anno_ids)}
                    datasets_list = find_objects_by_query(c, DATASETS_BY_TAG_ID_QUERY, params)
                    print(datasets_list)
                    update_dataset_tag(c, datasets_list, cur_tag_id)

                    delete_tags(c, duplicate_tag_ids, c.getSessionId())
                    print(duplicate_tag_ids)

                # reset the parameters
                cur_tag_name = tag_name
                cur_tag_id = tag_id
                duplicate_tag_ids = []
            elif tag_name == cur_tag_name and tag_id != cur_tag_id:
                # it's a duplicate tag;
                print("duplicate: {}".format(tag_id))
                if tag_id not in duplicate_tag_ids:
                    duplicate_tag_ids.append(tag_id)

    # catch the final iteration
    if len(duplicate_tag_ids) > 0:
        print('here')
        print(duplicate_tag_ids)
        anno_ids = map(rtypes.rlong, duplicate_tag_ids)
        print(anno_ids)
        params.map = {'aids': rtypes.rlist(anno_ids)}
        datasets_list = find_objects_by_query(c, DATASETS_BY_TAG_ID_QUERY, params)
        print(datasets_list)
        update_dataset_tag(c, datasets_list, cur_tag_id)

        delete_tags(c, duplicate_tag_ids, c.getSessionId())
        print(duplicate_tag_ids)


def main():
    USERNAME = 'root'
    PASSWORD = 'omero-root-password'
    print("hello world!")
    # do_change_name()
    c, cli, remote_conn = connect_to_remote(USERNAME, PASSWORD)
    # query_remote(cli)
    # upload_to_omero_cli(cli, IMAGE_PATH, '3973')
    params = om_sys.Parameters()
    dataset_id = 4300  ################## Replace this with your own parameter
    params.map = {'did': rtypes.rlong(dataset_id)}
    delete_duplicate_tags(c, cli, remote_conn)
    close_remote_connection(c, cli, remote_conn)


if __name__ == "__main__":
    main()
