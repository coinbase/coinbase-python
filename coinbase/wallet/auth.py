# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import hashlib
import hmac
from requests.utils import to_native_string
import time

from requests.auth import AuthBase


class HMACAuth(AuthBase):
  def __init__(self, api_key, api_secret, api_version):
    self.api_key = api_key
    self.api_secret = api_secret
    self.api_version = api_version

  def __call__(self, request):
    timestamp = str(int(time.time()))
    message = timestamp + request.method + request.path_url + (request.body or '')
    secret = self.api_secret

    if not isinstance(message, bytes):
      message = message.encode()
    if not isinstance(secret, bytes):
      secret = secret.encode()

    signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
    request.headers.update({
      to_native_string('CB-VERSION'): self.api_version,
      to_native_string('CB-ACCESS-KEY'): self.api_key,
      to_native_string('CB-ACCESS-SIGN'): signature,
      to_native_string('CB-ACCESS-TIMESTAMP'): timestamp,
    })
    return request


class OAuth2Auth(AuthBase):
  def __init__(self, access_token_getter, api_version):
    self.access_token_getter = access_token_getter
    self.api_version = api_version

  def __call__(self, request):
    access_token = self.access_token_getter()
    request.headers.update({
      to_native_string('CB-VERSION'): self.api_version,
      to_native_string('Authorization'):
        to_native_string('Bearer {}'.format(access_token)),
      })
    return request
