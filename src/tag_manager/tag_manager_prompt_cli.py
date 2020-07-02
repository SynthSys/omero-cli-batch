#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Johnny Hay"
__copyright__ = "BioRDM"
__license__ = "mit"

import sys
import os
import argparse
from argparse_prompt import PromptParser
import io
import csv
import getpass

from tag_manager.tag_manager import TagManager


'''
# Examples of usage
$ cd src

## automatically remove all identical duplicate tags and merge all associated datasets/images into the first 'original'
## tag; no extra parameters required beyond username and server
$ python -m tag_manager.tag_manager_cli -u root -s 172.17.0.3

## merge all datasets/images associated with tags withs labels 'arch%' and 'amoeb%' into one existing tag labelled 
## 'amoebozoa'
$ python -m tag_manager.tag_manager_cli -u root -s 172.17.0.3 -l amoebozoa -e arch% amoeb%

## merge all datasets/images associated with tags withs labels 'arch%' and 'amoeb%' and tags with IDs 245 and 253 
## into one existing tag labelled 'amoebozoa'
$ python -m tag_manager.tag_manager_cli -u root -s 172.17.0.3 -l amoebozoa -e arch% amoeb% -r 245 253

## merge all datasets/images associated with tags with labels 'cell wall' into one existing tag with label 'cell'
$ python -m tag_manager.tag_manager_cli -u root -s 172.17.0.3 -l cell -e "cell wall"

## error: Cannot specify both target tag ID and target tag label; use one or the other
$ python -m tag_manager.tag_manager_cli -u root -s 172.17.0.3 -i 233 -l amoebozoa -e arch% amoeb%

## merge all datasets/images associated with tags with labels 'arch%' and 'amoeb%' into one existing tag with ID 233
$ python -m tag_manager.tag_manager_cli -u root -s 172.17.0.3 -i 233 -e arch% amoeb%

## merge all datasets/images associated with tags with labels 'arch%' and 'amoeb%' and tags with IDs 245 and 253 
## into one existing tag with ID 233
$ python -m tag_manager.tag_manager_cli -u root -s 172.17.0.3 -i 233 -e arch% amoeb% -r 245 253

## merge all datasets/images associated with tags with label '"Screaming" Hairy l'éléphan%' 
## into one existing tag with ID 233
$ python -m tag_manager.tag_manager_cli -u root -s 172.17.0.3 -i 233 \ 
    -e "\"Screaming\" Hairy l'éléphan%"
'''

# Instantiate the parser
# see https://pypi.org/project/argparse-prompt/
parser = PromptParser(description='Tag Manager CLI Application')

# set of connection params
parser.add_argument('-u', '--username', dest='username',
                    required=True, metavar='username',
                    help="specifies the username for connection to the remote OMERO server", type=str, prompt=False)

parser.add_argument('-s', '--server', dest='server',
                    required=True, metavar='server',
                    help="specifies the server name of the remote OMERO server to connect", type=str, prompt=False)

parser.add_argument('-o', '--port', dest='port', nargs='?',
                    const=4064, required=False, metavar='port',
                    help="specifies the port on the remote OMERO server to connect (default is 4064)", type=int,
                    prompt=False)

parser.add_argument('-a', '--password', dest='password',
                    action='store_true',
                    help="hidden password prompt for connection to the remote OMERO server", prompt=False)

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
parser.add_argument('-i', '--target-tag-id',
                    dest='target_tag_id', required=False,
                    help="Omero ID of the destination tag for merging and linking objects to", type=int)

parser.add_argument('-l', '--target-tag-label',
                    dest='target_tag_label', required=False,
                    help="Label of the destination tag for merging and linking objects to", type=str)

parser.add_argument('-e', '--tag-labels-to-remove', dest='tag_labels_to_remove',
                    nargs='+', required=False,
                    help="List of regex strings for tag labels which are to be merged and removed on the Omero server",
                    type=str)

parser.add_argument('-r', '--tags-to-remove', dest='tags_to_remove',
                    nargs='+', required=False,
                    help="List of tag IDs which are to be merged and removed on the Omero server")

parser.add_argument('-d', '--dry-run', type=bool,
                    dest='dry_run', required=False,
                    help="Instructs the tag manager to report intended changes rather than actually perform the merge "
                         "and tag deletion process. Non-destructive and allows you to see what will be changed without "
                         "actually doing so.")

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

dry_run = False

if args.dry_run is not None:
    dry_run = args.dry_run

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
            tag_annos = tag_manager.get_tag_annos_for_labels([str(target_tag_label)])
            # pick the tag annotation with the lowest ID as the default target annotation object,
            # in case there are multiple tags with the same label
            target_tag_id = int(min(anno.getId().getValue() for anno in tag_annos))

    if tags_to_remove is not None and str(tags_to_remove).strip() is not '' and len(tags_to_remove) > 0:
        # pre-process the list of tag IDs to be merged
        tag_ids_to_remove = list(tags_to_remove)

    if tag_labels_to_remove is not None and str(tag_labels_to_remove).strip() is not '' and \
            len(tag_labels_to_remove) > 0:
        '''
        csv.register_dialect('MyDialect', delimiter=' ', doublequote=False, escapechar='\\', quotechar='"',
                             lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
        print(csv.list_dialects())
        print(tag_labels_to_remove)

        delimiter = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default

        doublequote = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default

        escapechar = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default

        lineterminator = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default

        quotechar = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default

        quoting = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default

        skipinitialspace = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default

        strict = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default
        '''

        '''
        def utf_8_encoder(unicode_csv_data):
            for line in unicode_csv_data:
                yield line.encode('utf-8')

        tags = csv.reader(utf_8_encoder(str(tag_labels_to_remove)), dialect='MyDialect')

        for row in tags:
            # decode UTF-8 back to Unicode, cell by cell:
            print(str(cell, 'utf-8') for cell in row)
        '''
        # pre-process the list of tag labels to be merged
        tag_annos = tag_manager.get_tag_annos_for_labels(tag_labels_to_remove)

        if tags_to_remove is None:
            tag_ids_to_remove = []

        tag_ids_to_remove.extend(list(int(anno.getId().getValue()) for anno in tag_annos))

    # ensure that the target_tag_id is not present in the tags_to_remove
    while target_tag_id in tag_ids_to_remove:
        tag_ids_to_remove.remove(target_tag_id)

    print('tags to remove: {}'.format(tag_ids_to_remove))
    print("target tag id: {}".format(target_tag_id))

    # start tag merge process
    tag_manager.merge_tags(target_tag_id, tag_ids_to_remove, auto_clean=False, dry_run=dry_run)
else:
    # since a target tag ID was not given, assume this is a general cleaning job to remove all identical duplicate tags
    tag_manager.merge_tags(target_tag_id=None, merge_tag_ids=[], auto_clean=True, dry_run=dry_run)
