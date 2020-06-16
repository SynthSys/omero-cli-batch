#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Johnny Hay"
__copyright__ = "BioRDM"
__license__ = "mit"

import sys
import os
import argparse
import getpass

from omero_cli_batch.tag_manager import TagManager

# Instantiate the parser
parser = argparse.ArgumentParser(description='Tag Manager CLI Application')

# set of connection params
parser.add_argument('-u', '--username', dest='username',
                    type=str, required=False, metavar='username',
                    help="specifies the username for connection to the remote OMERO server")

parser.add_argument('-s', '--server', dest='server',
                    type=str, required=False, metavar='server',
                    help="specifies the server name of the remote OMERO server to connect")

parser.add_argument('-o', '--port', dest='port', nargs='?',
                    const=4064, type=int, required=False, metavar='port',
                    help="specifies the port on the remote OMERO server to connect (default is 4064)")

parser.add_argument('-a', '--password', dest='password',
                    action='store_true',
                    help="hidden password prompt for connection to the remote OMERO server")

# mandatory args
'''
parser.add_argument('-d', '--data-path', dest='data_path',
                    type=str, required=True, metavar='data-path',
                    help="specifies the system file path to the data directory for uploading")

parser.add_argument('-n', '--dataset-name', dest='dataset_name',
                    type=str, required=True, metavar='dataset-name',
                    help="specifies the name of the destination dataset")
'''

# optional args
parser.add_argument('-i', '--target-tag-id', type=int,
                    dest='target_tag_id', required=False,
                    help="Omero ID of the destination tag for merging and linking objects to")

parser.add_argument('-l', '--target-tag-label', type=str,
                    dest='target_tag_label', required=False,
                    help="Label of the destination tag for merging and linking objects to")

parser.add_argument('-e', '--tag-labels-to-remove', dest='tag_labels_to_remove',
                    nargs='+', type=str, required=False,
                    help="List of regex strings for tag labels which are to be merged and removed on the Omero server")

parser.add_argument('-r', '--tags-to-remove', dest='tags_to_remove',
                    nargs='+', type=int, required=False,
                    help="List of tag labels which are to be merged and removed on the Omero server")

args = parser.parse_args()
target_tag_id = args.target_tag_id
tags_to_remove = args.tags_to_remove
target_tag_label = args.target_tag_label
tag_labels_to_remove = args.tag_labels_to_remove

username = args.username
server = args.server
USERNAME, PASSWORD, HOST, PORT = '', '', '', 0

if username is not None and server is not None:
    # validate args
    if username.strip() is "":
        print("Username is empty")
        quit()

    if server.strip() is "":
        print("Server name is empty")
        quit()

    #PASSWORD = getpass.getpass('Password: '.encode('ascii'))
    PASSWORD = getpass.getpass('Password: ')
    # PASSWORD = str(PASSWORD.encode('ascii')).encode('ascii')
    # PASSWORD = u''.join(PASSWORD)

    USERNAME = username
    SERVER = server
    PORT = args.port

# validate args
if USERNAME.strip() is "":
    print("Username is empty")
    quit()

if SERVER.strip() is "":
    print("Target OMERO server is empty")
    quit()

if PASSWORD.strip() is "":
    print("Password is empty")
    quit()

print(USERNAME)
print(PASSWORD)
print(SERVER)
print(PORT)
# initialise the TagManager
tag_manager = TagManager(username=USERNAME, password=PASSWORD, server=SERVER, port=PORT)

if target_tag_id is not None or target_tag_label is not None:
    # validate args
    if target_tag_id is not None and target_tag_label is not None:
        print("Cannot specify both target tag ID and target tag label; use one or the other")
        quit()

    if target_tag_id is not None and target_tag_id <= 0:
        print("Target tag ID is invalid")
        quit()

    if target_tag_label is not None:
        if target_tag_label.strip() is "":
            print("Target tag label is empty")
            quit()
        else:
            import ast
            print(target_tag_label)
            # tag_annos = tag_manager.get_tag_annos_for_labels(list(ast.literal_eval(str(target_tag_label))))
            tag_annos = tag_manager.get_tag_annos_for_labels([str(target_tag_label)])
            print(tag_annos)
            # pick the tag annotation with the lowest ID as the default target annotation object,
            # in case there are multiple tags with the same label
            target_tag_id = min(anno.getId().getValue() for anno in tag_annos)
            print("target tag id: {}".format(target_tag_id))

    if tags_to_remove is not None and str(tags_to_remove).strip() is not '' and len(tags_to_remove) > 0:
        # pre-process the list of tag labels to be merged
        print(tags_to_remove)
        tags_to_remove = list(tags_to_remove)
        print(tags_to_remove)
        print('here')

    if tag_labels_to_remove is not None and str(tag_labels_to_remove).strip() is not '' and \
            len(tag_labels_to_remove) > 0:
        # pre-process the list of tag labels to be merged
        print(tag_labels_to_remove)
        # tag_labels_to_remove = tag_labels_to_remove
        tag_annos = tag_manager.get_tag_annos_for_labels(tag_labels_to_remove)
        print(tag_annos)
        print('here')
        tags_to_remove = list(anno.getId().getValue() for anno in tag_annos)
        print('tags to remove: {}'.format(tags_to_remove))

    # start tag merge process
    # tag_manager.merge_tags(target_tag_id, tags_to_remove, auto_clean=False)
else:
    # since a target tag ID was not given, assume this is a general cleaning job to remove all identical duplicate tags
    tag_manager.merge_tags(target_tag_id=None, merge_tag_ids=[], auto_clean=True)
