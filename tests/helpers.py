# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import re
import six

import httpretty as hp


def mock_response(method, uri, data, errors=None, warnings=None, pagination=None):
  def wrapper(fn):
    @six.wraps(fn)
    @hp.activate
    def inner(*args, **kwargs):
      body = {'data': data}
      if errors is not None:
        body['errors'] = errors
      if warnings is not None:
        body['warnings'] = warnings
      if pagination is not None:
        body['pagination'] = pagination
      hp.reset()
      hp.register_uri(method, re.compile('.*'+uri+'$'), json.dumps(body))
      return fn(*args, **kwargs)
    return inner
  return wrapper
