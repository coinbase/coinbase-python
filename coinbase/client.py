# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import re
import requests
import warnings

from coinbase.compat import imap
from coinbase.compat import quote
from coinbase.compat import urljoin
from coinbase.compat import urlparse
from coinbase.model import PaymentMethod
from coinbase.auth import HMACAuth
from coinbase.auth import OAuth2Auth
from coinbase.error import APIError
from coinbase.error import AuthenticationError
from coinbase.error import ExpiredAccessToken
from coinbase.error import InvalidAccessToken
from coinbase.error import TokenRefreshError
from coinbase.error import TwoFactorTokenRequired
from coinbase.error import UnexpectedDataFormatError
from coinbase.error import build_api_error
from coinbase.model import APIObject
from coinbase.model import Account
from coinbase.model import User
from coinbase.util import encode_params


class Client(object):
  """ API Client for the Coinbase API.

  Entry point for making requests to the Coinbase API. Provides helper methods
  for common API endpoints, as well as niceties around response verification
  and formatting.

  Any errors will be raised as exceptions. These exceptions will always be
  subclasses of `coinbase.error.APIError`. HTTP-related errors will also be
  subclasses of `requests.HTTPError`.

  Full API docs, including descriptions of each API and its paramters, are
  available here: https://developers.coinbase.com/api
  """
  VERIFY_SSL = True
  BASE_API_URI = 'https://api.coinbase.com/v1/'
  _model_key = '__api_client'

  def __init__(self, api_key, api_secret, base_api_uri=None):
    if not api_key:
      raise ValueError('Missing `api_key`.')
    if not api_secret:
      raise ValueError('Missing `api_secret`.')

    # Allow passing in a different API base.
    self._set_base_api_uri(base_api_uri or self.BASE_API_URI)

    # Set up a requests session for interacting with the API.
    self.session = self._build_session(HMACAuth, api_key, api_secret)

  def _build_session(self, auth_class, *args, **kwargs):
    """Internal helper for creating a requests `session` with the correct
    authentication handling."""
    session = requests.session()
    session.auth = auth_class(*args, **kwargs)
    session.headers.update({'Accept': 'application/json',
                            'Content-Type': 'application/json',
                            'User-Agent': 'coinbase/python/1.0'})
    return session

  def _set_base_api_uri(self, base_api_uri):
    """Internal helper for setting a new base API URL. Warns if the URL is
    insecure."""
    self.BASE_API_URI = base_api_uri
    if urlparse(self.BASE_API_URI).scheme != 'https':
      warning_message = (
          'WARNING: this client is sending a request to an insecure'
          ' API endpoint. Any API request you make may expose your API key and'
          ' secret to third parties. Consider using the default endpoint:\n\n'
          '  %s\n') % Client.BASE_API_URI
      warnings.warn(warning_message, UserWarning)

  def _create_api_uri(self, *parts):
    """Internal helper for creating fully qualified endpoint URIs."""
    return urljoin(self.BASE_API_URI, '/'.join(imap(quote, parts)))

  def _request(self, method, *relative_path_parts, **kwargs):
    """Internal helper for creating HTTP requests to the Coinbase API.

    Raises an APIError if the response is not 200. Otherwise, returns the
    response object. Not intended for direct use by API consumers.
    """
    uri = self._create_api_uri(*relative_path_parts)
    kwargs.update({'verify': self.VERIFY_SSL})
    response = getattr(self.session, method)(uri, **kwargs)
    return self._handle_response(response)

  def _handle_response(self, response):
    """Internal helper for handling API responses from the Coinbase server.

    Raises the appropriate exceptions when necessary; otherwise, returns the
    response.
    """
    if response.status_code == 200:
      return response
    # If the API response was not 200, an error occurred. Raise an exception
    # with the details of the error and references to the full response and,
    # when possible, request. These exceptions are intended to bubble up to the
    # consuming user. If the error is authentication related, raise a more
    # specific exception.
    if response.status_code == 401:
      raise build_api_error(AuthenticationError, response)
    raise build_api_error(APIError, response)

  def _get(self, *args, **kwargs):
    return self._request('get', *args, **kwargs)

  def _post(self, *args, **kwargs):
    return self._request('post', *args, **kwargs)

  def _put(self, *args, **kwargs):
    return self._request('put', *args, **kwargs)

  def _delete(self, *args, **kwargs):
    return self._request('delete', *args, **kwargs)

  def _make_api_object(self, *args, **kwargs):
    root_api_object = kwargs.get('account', None) or APIObject(api_client=self)
    return root_api_object.load(*args, **kwargs)

  def get_authorization(self, **kwargs):
    """https://developers.coinbase.com/api#authorization"""
    response = self._get('authorization', **kwargs)
    return self._make_api_object(response.json())

  def get_accounts(self, page=None, limit=None, all_accounts=None):
    """https://developers.coinbase.com/api#list-accounts"""
    data = encode_params({
        'page': page,
        'limit': limit,
        'all_accounts': all_accounts,
      }, bools_to_ints=True)
    response = self._get('accounts', data=data)
    return self._make_api_object(value=response.json(), paged_key='accounts')

  def get_account(self, account_id=None):
    """https://developers.coinbase.com/api#show-an-account

    If the `account_id` parameter is omitted, this method will fetch details
    on the primary account.
    """
    if account_id is None:
      account_id = 'primary'
    response = self._get('accounts', account_id)
    api_obj = self._make_api_object(response.json())
    account = api_obj.get('account', None)
    if not isinstance(account, Account):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return account

  def create_account(self, name):
    """https://developers.coinbase.com/api#create-an-account"""
    data = encode_params({
        'account': {
          'name': name,
        },
      })
    response = self._post('accounts', data=data)
    api_obj = self._make_api_object(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(APIError, response, 'Failed to create an account')
    account = api_obj.get('account', None)
    if not isinstance(account, Account):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return account

  def get_contacts(self, page=None, limit=None, all_accounts=None):
    """https://developers.coinbase.com/api#contacts"""
    data = encode_params({
        'page': page,
        'limit': limit,
        'all_accounts': all_accounts,
      })
    response = self._get('contacts', data=data)
    return self._make_api_object(response.json(), paged_key='contacts')

  def get_current_user(self):
    """https://developers.coinbase.com/api#get-current-user"""
    response = self._get('users', 'self')
    api_obj = self._make_api_object(response.json())
    user = api_obj.get('user', None)
    if not isinstance(user, User):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return user

  def get_buy_price(self, qty=None, currency=None):
    """https://developers.coinbase.com/api#get-the-buy-price-for-bitcoin"""
    data = encode_params({
        'qty': qty,
        'currency': currency,
      })
    response = self._get('prices','buy', data=data)
    return self._make_api_object(response.json())

  def get_sell_price(self, qty=None, currency=None):
    """https://developers.coinbase.com/api#get-the-sell-price"""
    data = encode_params({
        'qty': qty,
        'currency': currency,
      })
    response = self._get('prices','sell', data=data)
    return self._make_api_object(response.json())

  def get_spot_price(self, currency=None):
    """https://developers.coinbase.com/api#get-the-spot-price-of-bitcoin"""
    data = encode_params({
        'currency': currency,
      })
    response = self._get('prices','spot_rate', data=data)
    return self._make_api_object(response.json())

  def get_supported_currencies(self):
    """https://developers.coinbase.com/api#currencies"""
    response = self._get('currencies')
    return self._make_api_object(response.json())

  def get_exchange_rates(self):
    """https://developers.coinbase.com/api#list-exchange-rates-between-btc-and-other-currencies"""
    response = self._get('currencies', 'exchange_rates')
    return self._make_api_object(response.json())

  def create_user(self,
      email, password, referrer_id=None, client_id=None, scopes=None):
    """https://developers.coinbase.com/api#create-a-new-user"""
    data = encode_params({
        'user': {
          'email': email,
          'password': password,
          'referrer_id': referrer_id,
          'client_id': client_id,
          'scopes': (
            ' '.join(scopes) if isinstance(scopes, (list, tuple)) else scopes),
        },
      })
    response = self._post('users', data=data)
    api_obj = self._make_api_object(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(APIError, response, 'Failed to create a user')
    return api_obj

  def get_payment_methods(self):
    """https://developers.coinbase.com/api#payment-methods"""
    response = self._get('payment_methods')
    return self._make_api_object(response.json(), paged_key='payment_methods')

  def get_payment_method(self, payment_method_id):
    """https://developers.coinbase.com/api#show-a-payment-method"""
    response = self._get('payment_methods', payment_method_id)
    api_obj = self._make_api_object(response.json())
    payment_method = api_obj.get('payment_method', None)
    if not isinstance(payment_method, PaymentMethod):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return payment_method



class OAuthClient(Client):
  TOKEN_ENDPOINT_URI = 'https://www.coinbase.com/oauth/token'

  def __init__(self,
               client_id,
               client_secret,
               access_token,
               refresh_token,
               token_endpoint_uri=None,
               base_api_uri=None):
    if not access_token:
      raise ValueError("Missing `access_token`.")
    if not refresh_token:
      raise ValueError("Missing `refresh_token`.")
    if not client_id:
      raise ValueError("Missing `client_id`.")
    if not client_secret:
      raise ValueError("Missing `client_secret`.")

    self.client_id = client_id
    self.client_secret = client_secret
    self.access_token = access_token
    self.refresh_token = refresh_token

    self._set_base_api_uri(base_api_uri or self.BASE_API_URI)
    self.TOKEN_ENDPOINT_URI = token_endpoint_uri or self.TOKEN_ENDPOINT_URI

    # Set up a requests session for interacting with the API.
    self.session = self._build_session(OAuth2Auth, lambda: self.access_token)

  def _handle_response(self, response):
    # 402 will only be returned if the API endpoint requires that the oauth
    # client include the user's 2FA token as a parameter on the request.
    if response.status_code == 402:
      raise build_api_error(TwoFactorTokenRequired, response)

    # Non-authentication errors should be handled by the standard Client
    # response processing logic.
    if response.status_code != 401:
      return super(OAuthClient, self)._handle_response(response)

    auth_header = response.headers.get('www-authenticate', None)
    details = auth_header and _parse_authenticate_header(auth_header)
    if details and details.get('error') == 'invalid_token':
      if 'expired' in details.get('error_description', ''):
        raise build_api_error(ExpiredAccessToken, response)
      raise build_api_error(InvalidAccessToken, response)
    raise build_api_error(AuthenticationError, response)

  def refresh(self):
    """Attempt to refresh the current access token / refresh token pair.

    If successful, the relevant attributes of this client will be updated
    automatically and the dict of token values and information given  by the
    Coinbase OAuth server will be returned to the caller.

    If unsuccessful, raises a TokenRefreshError.
    """
    params = {
      'grant_type': 'refresh_token',
      'client_id': self.client_id,
      'client_secret': self.client_secret,
      'refresh_token': self.refresh_token
    }
    response = self.session.post(
        self.TOKEN_ENDPOINT_URI, params=params, verify=self.VERIFY_SSL)

    if not response.status_code == 200:
      raise build_api_error(TokenRefreshError, response)

    data = response.json()
    self.access_token = data.get('access_token')
    self.refresh_token = data.get('refresh_token')
    return data


def _parse_authenticate_header(header):
   return dict(re.findall('([a-zA-Z\_]+)\=\"(.*?)\"', header))
