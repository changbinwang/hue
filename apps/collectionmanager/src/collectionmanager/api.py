#!/usr/bin/env python
# Licensed to Cloudera, Inc. under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  Cloudera, Inc. licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging

from django.http import HttpResponse
from django.utils.translation import ugettext as _

from desktop.lib import i18n
from desktop.lib.exceptions_renderable import PopupException

from beeswax.create_table import _parse_fields, FILE_READERS, DELIMITERS

from controller import CollectionManagerController


LOG = logging.getLogger(__name__)


def parse_fields(request):
  result = {'status': -1, 'message': ''}

  file_type = request.POST.get('file-type', 'log')
  try:
    file_obj = request.fs.open(request.POST.get('file-path'))

    if file_type == 'separated':
      delimiter = [request.POST.get('field-separator', ',')]
      delim, reader_type, fields_list = _parse_fields(
                                          'collections-file',
                                          file_obj,
                                          i18n.get_site_encoding(),
                                          [reader.TYPE for reader in FILE_READERS],
                                          delimiter)
      result['status'] = 0
      result['data'] = fields_list
    elif file_type == 'log':
      result['status'] = 0
      result['data'] = [
        # Syslog format basically
        ['priority', 'header', 'message'],
        ['string', 'string', 'string']
      ]
    elif file_type == 'regex':
      # @TODO: Understand regex use case better.
      result['status'] = 0
      result['data'] = [
        # Syslog format basically
        ['priority', 'header', 'message'],
        ['string', 'string', 'string']
      ]
    else:
      result['status'] = 1
      result['message'] = _('File type %s not supported.') % file_type
  except Exception, e:
    result['message'] = e.message

  return HttpResponse(json.dumps(result), mimetype="application/json")


def collections_and_cores(request):
  searcher = CollectionManagerController(request.user)
  new_solr_collections = searcher.get_new_collections()
  massaged_collections = []
  for coll in new_solr_collections:
    massaged_collections.append({
      'type': 'collection',
      'name': coll
    })
  new_solr_cores = searcher.get_new_cores()
  massaged_cores = []
  for core in new_solr_cores:
    massaged_cores.append({
      'type': 'core',
      'name': core
    })
  response = {
    'status': 0,
    'collections': list(massaged_collections),
    'cores': list(massaged_cores)
  }
  return HttpResponse(json.dumps(response), mimetype="application/json")


def collections_create(request):
  if request.method != 'POST':
    raise PopupException(_('POST request required.'))

  response = {'status': -1}

  collection = json.loads(request.POST.get('collection', '{}'))

  if collection:
    # Create collection and add fields
    searcher = CollectionManagerController(request.user)
    searcher.create_new_collection(collection.get('name', ''), collection.get('fields', []))

    # Index data
    fh = request.fs.open(request.POST.get('file-path'))
    searcher.update_collection_index(collection.get('name', ''), fh.read())
    fh.close()

    response['status'] = 0
    response['message'] = _('Page saved!')
  else:
    response['message'] = _('Collection missing.')

  return HttpResponse(json.dumps(response), mimetype="application/json")


def collections_import(request):
  if request.method != 'POST':
    raise PopupException(_('POST request required.'))

  searcher = CollectionManagerController(request.user)
  imported = []
  not_imported = []
  status = -1
  message = ""
  importables = json.loads(request.POST["collections"])
  for imp in importables:
    try:
      searcher.add_new_collection(imp)
      imported.append(imp['name'])
    except Exception, e:
      not_imported.append(imp['name'] + ": " + unicode(str(e), "utf8"))

  if len(imported) == len(importables):
    status = 0;
    message = _('Collection(s) or core(s) imported successfully!')
  elif len(not_imported) == len(importables):
    status = 2;
    message = _('There was an error importing the collection(s) or core(s)')
  else:
    status = 1;
    message = _('Collection(s) or core(s) partially imported')

  result = {
    'status': status,
    'message': message,
    'imported': imported,
    'notImported': not_imported
  }

  return HttpResponse(json.dumps(result), mimetype="application/json")
