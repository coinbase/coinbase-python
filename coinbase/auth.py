# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import hashlib
import hmac
import time
from requests.auth import AuthBase


class HMACAuth(AuthBase):
  def __init__(self, api_key, api_secret):
    self.api_key = api_key
    self.api_secret = api_secret

  def __call__(self, request):
    nonce = int(time.time() * 1e6)
    message = str(nonce) + request.url + (request.body or '')
    secret = self.api_secret

    if not isinstance(message, bytes):
      message = message.encode()
    if not isinstance(secret, bytes):
      secret = secret.encode()

    signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
    request.headers.update({
      'ACCESS_KEY': self.api_key,
      'ACCESS_SIGNATURE': signature,
      'ACCESS_NONCE': nonce})
    return request


class OAuth2Auth(AuthBase):
  def __init__(self, access_token_getter):
    self.access_token_getter = access_token_getter

  def __call__(self, request):
    access_token = self.access_token_getter()
    request.headers.update({
        'Authorization': 'Bearer {0}'.format(access_token),
      })
    return request
