# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import six


def _clean_params(params, bools_to_ints=False, drop_nones=True, recursive=True):
  """Clean up a dict of API parameters to be sent to the Coinbase API.

  Some endpoints require boolean options to be represented as integers. By
  default, will remove all keys whose value is None, so that they will not be
  sent to the API endpoint at all.
  """
  cleaned = {}
  for key, value in six.iteritems(params):
    if bools_to_ints and isinstance(value, bool):
      value = int(value)
    elif drop_nones and value is None:
      continue
    elif recursive and isinstance(value, dict):
      value = _clean_params(value, bools_to_ints, drop_nones, recursive)
    cleaned[key] = value
  return cleaned


def encode_params(params, **kwargs):
  """Clean and JSON-encode a dict of parameters."""
  cleaned = _clean_params(params, **kwargs)
  return json.dumps(cleaned)


def unnest(*keys):
  def _unnest(value):
    for key in keys:
      value = value[key]
    return value
  return _unnest
