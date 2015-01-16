# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from requests import HTTPError


class CoinbaseError(Exception):
  """Base error class for all exceptions raised in this library.

  Will never be raised naked; more specific subclasses of this exception will
  be raised when appropriate."""


class APIError(HTTPError, CoinbaseError):
  """Raised for errors related to interacting with the Coinbase API server."""


class UnexpectedDataFormatError(APIError):
  """Raised when the data returned by the Coinbase API is an unexpected format.
  """

class AuthenticationError(APIError):
  """Raised by the API Client if there was an authentication error."""


class InvalidAccessToken(AuthenticationError):
  """Raised by the OAuthClient when the current access token is no longer
  valid."""


class ExpiredAccessToken(InvalidAccessToken):
  """Raised by the OAuthClient when the current access token is expired."""


class TokenRefreshError(APIError):
  """Raised by the OAuthClient when there is a failure refreshing the access
  token."""


class TwoFactorTokenRequired(APIError):
  """Raised when a user's Two Factor Auth token needs to be included in the
  request."""


def build_api_error(error_cls, response, description=None):
  """Helper method for creating errors and attaching HTTP response/request
  details to them.
  """
  if description is None:
    description = 'HTTP %d: %s' % (response.status_code, response.reason)
  error = error_cls(description)
  error.status_code = response.status_code
  error.response = response
  error.request = getattr(response, 'request', None)
  raise error
