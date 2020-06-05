#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Johnny Hay"
__copyright__ = "BioRDM"
__license__ = "mit"

import sys
import os
import argparse
import getpass

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
parser.add_argument('-t', '--target-tag-id', type=int,
                    dest='target_tag_id', required=False,
                    help="Omero ID of the destination tag for merging and linking objects to")

parser.add_argument('-r', '--tags-to-remove', dest='tags_to_remove',
                    nargs='+', type=str, required=False,
                    help="List of tag labels which are to be merged and removed on the Omero server")

args = parser.parse_args()
target_tag_id = args.target_tag_id
tags_to_remove = args.tags_to_remove

username = args.username
server = args.server
USERNAME, PASSWORD, HOST, PORT = '', '', '', 0

if username is not None and server is not None:
    # validate args
    if username.strip() is "":
        print("Username is empty")
        quit()

    if server.strip() is "":
        print("Dataset name is empty")
        quit()

    #PASSWORD = getpass.getpass('Password: '.encode('ascii'))
    PASSWORD = getpass.getpass('Password: ')
    # PASSWORD = str(PASSWORD.encode('ascii')).encode('ascii')
    # PASSWORD = u''.join(PASSWORD)

    USERNAME = username
    HOST = server
    PORT = args.port

# validate args
if USERNAME.strip() is "":
    print("Username is empty")
    quit()

if HOST.strip() is "":
    print("Target OMERO server is empty")
    quit()

if PASSWORD.strip() is "":
    print("Password is empty")
    quit()

# initialise the PyOmeroUploader
tag_manager = TagManager(username=USERNAME, password=PASSWORD, server=HOST, port=PORT)

if target_tag_id is not None:
    # validate args
    if target_tag_id.strip() is "":
        print("Data path is empty")
        quit()

    if tags_to_remove is not None and tags_to_remove.strip() is not '':
        # pre-process the list of tag labels to be merged
        print('here')

    # start tag merge process
    tag_manager.merge_tags(target_tag_id, tags_to_remove)
else:
    # since a target tag ID was not given, assume this is a general cleaning job to remove all identical duplicate tags
    tag_manager.manage_duplicate_tags(c)
