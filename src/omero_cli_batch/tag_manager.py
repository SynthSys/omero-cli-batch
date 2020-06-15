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

# OMERO_SERVER = 'demo.openmicroscopy.org'
# OMERO_SERVER = '172.17.0.3'
OMERO_SERVER = 'publicomero.bio.ed.ac.uk'
OMERO_PORT = 4064
IMAGE_PATH = '/home/jhay/Downloads/Download-Cat-PNG-Clipart.png'
OMERO_BIN_PATH = os.path.join("/opt", "omero", "server", "OMERO.server", "bin", "omero")
OMERO_BIN_PATH = os.path.join("/home", "jhay", ".conda", "envs", "omeropy", "bin", "omero")
USERNAME = 'jhay'
PASSWORD = ''
OMERO_GROUP = 'rdm_scrapbook'

# Retrieve annotations by associated dataset ID
ANNOS_BY_IDS_QUERY = "select a from Annotation a where a.id in :aids"

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

Scenario 3
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
    and l.child = a.id \
    and d.id = l.parent \
    order by a.textValue, a.id"

DUPLICATE_TAGS_S2_QUERY = "select a from Annotation a, DatasetAnnotationLink l, Dataset d \
    where (select count(*) from Annotation a2 \
    where a.textValue = a2.textValue \
    and coalesce(a.description, '') = '' \
    and coalesce(a2.description, '') = '') > 1 \
    and l.child = a.id \
    and d.id = l.parent \
    order by a.textValue, a.id"

# Scenario 2
DUPLICATE_TAGS_S3_QUERY = "select a from Annotation a \
    where (select count(*) from Annotation a2 \
    where  a.textValue = a2.textValue \
    and a.description = a2.description) > 1 \
    order by a.textValue, a.id"

DUPLICATE_TAGS_S4_QUERY = "select a from Annotation a \
    where (select count(*) from Annotation a2 \
    where a.textValue = a2.textValue \
    and coalesce(a.description, '') = '' \
    and coalesce(a2.description, '') = '') > 1 \
    order by a.textValue, a.id"

# Scenario 3
DUPLICATE_TAGS_S5_QUERY = "select a from Annotation a, ImageAnnotationLink l, Image i \
    where (select count(*) from Annotation a2 \
    where  a.textValue = a2.textValue \
    and a.description = a2.description) > 1 \
    and l.child = a.id \
    and i.id = l.parent \
    order by a.textValue, a.id"

DUPLICATE_TAGS_S6_QUERY = "select a from Annotation a, ImageAnnotationLink l, Image i \
    where (select count(*) from Annotation a2 \
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

exit_condition = False


class TagManager:

    session_exit_condition = False

    def __init__(self, username, password, server, port=4064):
        self.USERNAME = username
        self.PASSWORD = password
        self.SERVER = server
        self.PORT = port

    def connect_to_remote(self, username, password):
        c = omero.client(host=self.SERVER, port=self.PORT,
                         args=["--Ice.Config=/dev/null", "--omero.debug=1"])
        c.createSession(username, password)
        remote_conn = BlitzGateway(client_obj=c)
        cli = omero.cli.CLI()
        cli.loadplugins()
        cli.set_client(c)
        # del os.environ["ICE_CONFIG"]
        return c, cli, remote_conn

    def close_remote_connection(self, c, cli, remote_conn):
        remote_conn.close()
        c.closeSession()
        cli.close()

    def query_remote(self, cli):
        # invoke login
        # cli.invoke(["login"])
        cli.invoke(["hql", "-q", "'select g.name from ExperimenterGroup g'"])
        # cli.invoke(["import", "---errs", stderr.name, "---file", stdout.name, "--no-upgrade-check", path, "-d", datasetId])

    def find_objects_by_query(self, client, query, params):
        query_service = client.getSession().getQueryService()
        # query = "select p from Project p left outer join fetch p.datasetLinks as links left outer join fetch links.child as dataset where p.id =:pid"

        objects = query_service.findAllByQuery(query, params)

        return objects

    def fileno(self, file_or_fd):
        fd = getattr(file_or_fd, 'fileno', lambda: file_or_fd)()
        if not isinstance(fd, int):
            raise ValueError("Expected a file (`.fileno()`) or a file descriptor")
        return fd

    @contextmanager
    def stdout_redirected(self, to=os.devnull, stdout=None):
        if stdout is None:
            stdout = sys.stdout

        stdout_fd = self.fileno(stdout)
        # copy stdout_fd before it is overwritten
        # NOTE: `copied`is inheritable on Windows when duplicating a standard stream
        with os.fdopen(os.dup(stdout_fd), 'wb') as copied:
            stdout.flush()  # flush library buffers that dup2 knows nothing about
            try:
                os.dup2(self.fileno(to), stdout_fd)  # $ exec >&to
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

    def update_object_tag(self, client, objects_list, tag_id):
        for object in objects_list:
            link = None
            if isinstance(object, omero.model.DatasetI):
                link = model.DatasetAnnotationLinkI()
                link.setParent(model.DatasetI(object.getId(), False))
                link.setChild(model.TagAnnotationI(tag_id, False))
            elif isinstance(object, omero.model.ImageI):
                link = model.ImageAnnotationLinkI()
                link.setParent(model.ImageI(object.getId(), False))
                link.setChild(model.TagAnnotationI(tag_id, False))

            tag_link = client.getSession().getUpdateService().saveAndReturnObject(link)

    def delete_tags(self, client, tag_id_list, session_key):
        for tag_id in tag_id_list:
            args = [sys.executable]
            args.append(OMERO_BIN_PATH)
            args.extend(["-s", self.SERVER, "-k", session_key, "-p", str(self.PORT), "-g", OMERO_GROUP])
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

    def update_tag_links(self, duplicate_tag_ids, client, query, replacement_tag_id):
        params = om_sys.Parameters()
        params.map = {}

        print('here')
        print(duplicate_tag_ids)
        anno_ids = map(rtypes.rlong, duplicate_tag_ids)
        print(anno_ids)
        params.map = {'aids': rtypes.rlist(anno_ids)}
        objects_list = self.find_objects_by_query(client, query, params)
        print("updating these objects:")
        print(objects_list)
        object_ids = [i.getId().getValue() for i in objects_list]
        print(object_ids)

        self.update_object_tag(client, objects_list, replacement_tag_id)

    def delete_duplicate_tags(self, duplicate_tag_ids, client):
        self.delete_tags(client, duplicate_tag_ids, client.getSessionId())
        print("Deleting these tags:")
        print(duplicate_tag_ids)

    def do_tag_merge(self, client, merge_tag_id, duplicate_tag_ids):
        # ensure the target tag is not in the list to be deleted!
        while merge_tag_id in duplicate_tag_ids:
            duplicate_tag_ids.remove(merge_tag_id)

        if len(duplicate_tag_ids) > 0:
            self.update_tag_links(duplicate_tag_ids, client, DATASETS_BY_TAG_ID_QUERY, merge_tag_id)
            self.update_tag_links(duplicate_tag_ids, client, IMAGES_BY_TAG_ID_QUERY, merge_tag_id)

            self.delete_duplicate_tags(duplicate_tag_ids, client)

    def manage_duplicate_tags(self, client, target_tag_id=None, merge_tag_ids=None):
        params = om_sys.Parameters()
        params.map = {}
        query_filter = om_sys.Filter()
        #query_filter.limit = rtypes.rint(10) # should limit and enhance performance of query, but does not seem to
        params.theFilter = query_filter
        anno_list = []
        print(merge_tag_ids)

        if merge_tag_ids == None or len(merge_tag_ids) == 0:
            anno_list = self.find_objects_by_query(client, DUPLICATE_TAGS_S1_QUERY, params)
            anno_list.extend(self.find_objects_by_query(client, DUPLICATE_TAGS_S2_QUERY, params))
            anno_list.extend(self.find_objects_by_query(client, DUPLICATE_TAGS_S3_QUERY, params))
            anno_list.extend(self.find_objects_by_query(client, DUPLICATE_TAGS_S4_QUERY, params))
            anno_list.extend(self.find_objects_by_query(client, DUPLICATE_TAGS_S5_QUERY, params))
            anno_list.extend(self.find_objects_by_query(client, DUPLICATE_TAGS_S6_QUERY, params))
        else:
            if len(merge_tag_ids) > 0:
                print(merge_tag_ids)
                print(target_tag_id)
                all_tag_ids = merge_tag_ids
                all_tag_ids.append(target_tag_id)
                print(all_tag_ids)
                anno_ids = map(rtypes.rlong, all_tag_ids)
                print(anno_ids)
                params.map = {'aids': rtypes.rlist(anno_ids)}
                anno_list = self.find_objects_by_query(client, ANNOS_BY_IDS_QUERY, params)

        cur_tag_name, cur_tag_id = None, None
        duplicate_tag_ids = []
        merge_tag_id = None

        if merge_tag_ids == None or len(merge_tag_ids) == 0:
            for anno in anno_list:
                print(anno)
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
                            if target_tag_id is None:
                                merge_tag_id = cur_tag_id
                            else:
                                merge_tag_id = target_tag_id

                            self.do_tag_merge(client, merge_tag_id, duplicate_tag_ids)

                        # reset the parameters
                        cur_tag_name = tag_name
                        cur_tag_id = tag_id
                        duplicate_tag_ids = []
                        merge_tag_id = None
                    elif tag_name == cur_tag_name and tag_id != cur_tag_id:
                        # it's a duplicate tag;
                        print("duplicate: {}".format(tag_id))
                        if tag_id not in duplicate_tag_ids:
                            duplicate_tag_ids.append(tag_id)

        else:
            duplicate_tag_ids = merge_tag_ids

        # catch the final iteration
        if len(duplicate_tag_ids) > 0:
            if target_tag_id is None:
                merge_tag_id = cur_tag_id
            else:
                merge_tag_id = target_tag_id

            self.do_tag_merge(client, merge_tag_id, duplicate_tag_ids)

    def ping_session(self, interval, client):
        ping_count = 0
        while True:
            if self.session_exit_condition == False:
                ping_count = ping_count + 1
                print("pinging session: {}".format(ping_count))
                keys = client.getInputKeys()
            else:
                break

            time.sleep(interval)

    def merge_tags(self, target_tag_id=None, merge_tag_ids=[], auto_clean=False):
        c, cli, remote_conn = self.connect_to_remote(self.USERNAME, self.PASSWORD)

        # run session ping function as daemon to keep connection alive
        keep_alive_thread = threading.Thread(target=self.ping_session, args=([60, c]))
        keep_alive_thread.daemon = True
        keep_alive_thread.start()

        if auto_clean == True:
            self.manage_duplicate_tags(c)
        elif auto_clean == False and target_tag_id is not None and len(merge_tag_ids) > 0:
            self.manage_duplicate_tags(c, target_tag_id=target_tag_id, merge_tag_ids=merge_tag_ids)
        else:
            print("No target tag or merge tags identified")

        # global exit_condition
        self.session_exit_condition = True
        self.close_remote_connection(c, cli, remote_conn)


def main():
    OMERO_SERVER = '172.17.0.3'
    USERNAME = 'root'
    PASSWORD = 'omero-root-password'
    OMERO_GROUP = 'system'

    # USERNAME = 'xxxxxx'
    # PASSWORD = 'xxxxxx'
    # OMERO_GROUP = 'rdm_scrapbook'

    print("hello world!")

    tag_manager = TagManager(username=USERNAME, password=PASSWORD, server=OMERO_SERVER)
    c, cli, remote_conn = tag_manager.connect_to_remote(USERNAME, PASSWORD)

    # run session ping function as daemon to keep connection alive
    keep_alive_thread = threading.Thread(target=tag_manager.ping_session, args=([60, c]))
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    tag_manager.manage_duplicate_tags(c)

    # global exit_condition
    tag_manager.session_exit_condition = True
    tag_manager.close_remote_connection(c, cli, remote_conn)


if __name__ == "__main__":
    main()
