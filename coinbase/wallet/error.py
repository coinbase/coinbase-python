# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


class CoinbaseError(Exception):
  """Base error class for all exceptions raised in this library.

  Will never be raised naked; more specific subclasses of this exception will
  be raised when appropriate."""


class APIError(CoinbaseError):
  """Raised for errors related to interacting with the Coinbase API server."""
  def __init__(self, response, id, message, errors=None):
    self.status_code = response.status_code
    self.response = response
    self.id = id or ''
    self.message = message or ''
    self.request = getattr(response, 'request', None)
    self.errors = errors or []
  def __str__(self): # pragma: no cover
    return 'APIError(id=%s): %s' % (self.id, self.message)


class TwoFactorRequiredError(APIError): pass
class ParamRequiredError(APIError): pass
class ValidationError(APIError): pass
class InvalidRequestError(APIError): pass
class PersonalDetailsRequiredError(APIError): pass
class AuthenticationError(APIError): pass
class UnverifiedEmailError(APIError): pass
class InvalidTokenError(APIError): pass
class RevokedTokenError(APIError): pass
class ExpiredTokenError(APIError): pass
class InvalidScopeError(APIError): pass
class NotFoundError(APIError): pass
class RateLimitExceededError(APIError): pass
class InternalServerError(APIError): pass
class ServiceUnavailableError(APIError): pass


def build_api_error(response, blob=None):
  """Helper method for creating errors and attaching HTTP response/request
  details to them.
  """
  blob = blob or response.json()
  error_list = blob.get('errors', None)
  error = (error_list[0] if error_list else {})
  if error:
    error_id = error.get('id', '')
    error_message = error.get('message', '')
  else:
    # In the case of an OAuth-specific error, the response data is the error
    # blob, and the keys are slightly different. See
    # https://developers.coinbase.com/api/v2#error-response
    error_id = blob.get('error')
    error_message = blob.get('error_description')
  error_class = (
      _error_id_to_class.get(error_id, None) or
      _status_code_to_class.get(response.status_code, APIError))
  return error_class(response, error_id, error_message, error_list)


_error_id_to_class = {
  'two_factor_required': TwoFactorRequiredError,
  'param_required': ParamRequiredError,
  'validation_error': ValidationError,
  'invalid_request': InvalidRequestError,
  'personal_details_required': PersonalDetailsRequiredError,
  'authentication_error': AuthenticationError,
  'unverified_email': UnverifiedEmailError,
  'invalid_token': InvalidTokenError,
  'revoked_token': RevokedTokenError,
  'expired_token': ExpiredTokenError,
  'invalid_scope': InvalidScopeError,
  'not_found': NotFoundError,
  'rate_limit_exceeded': RateLimitExceededError,
  'internal_server_error': InternalServerError,
}

_status_code_to_class = {
    400: InvalidRequestError,
    401: AuthenticationError,
    402: TwoFactorRequiredError,
    403: InvalidScopeError,
    404: NotFoundError,
    422: ValidationError,
    429: RateLimitExceededError,
    500: InternalServerError,
    503: ServiceUnavailableError,
  }

