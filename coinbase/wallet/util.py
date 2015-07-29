# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import six
import warnings

from coinbase.wallet.compat import urlparse


def clean_params(params, drop_nones=True, recursive=True):
  """Clean up a dict of API parameters to be sent to the Coinbase API.

  Some endpoints require boolean options to be represented as integers. By
  default, will remove all keys whose value is None, so that they will not be
  sent to the API endpoint at all.
  """
  cleaned = {}
  for key, value in six.iteritems(params):
    if drop_nones and value is None:
      continue
    if recursive and isinstance(value, dict):
      value = clean_params(value, drop_nones, recursive)
    cleaned[key] = value
  return cleaned


def encode_params(params, **kwargs):
  """Clean and JSON-encode a dict of parameters."""
  cleaned = clean_params(params, **kwargs)
  return json.dumps(cleaned)


def check_uri_security(uri):
  """Warns if the URL is insecure."""
  if urlparse(uri).scheme != 'https':
    warning_message = (
        'WARNING: this client is sending a request to an insecure'
        ' API endpoint. Any API request you make may expose your API key and'
        ' secret to third parties. Consider using the default endpoint:\n\n'
        '  %s\n') % uri
    warnings.warn(warning_message, UserWarning)
  return uri
