# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import re
import six
import unittest2
import warnings
try:
  from urlparse import urlparse
except ImportError:
  from urllib.parse import urlparse

import httpretty as hp

from coinbase.client import Client
from coinbase.client import OAuthClient
from coinbase.error import APIError
from coinbase.error import AuthenticationError
from coinbase.error import TokenRefreshError
from coinbase.error import TwoFactorTokenRequired
from coinbase.error import ExpiredAccessToken
from coinbase.error import InvalidAccessToken
from coinbase.error import UnexpectedDataFormatError
from coinbase.model import APIObject
from coinbase.model import Account
from coinbase.model import Money
from coinbase.model import User
from coinbase.model import PaymentMethod


# Hide all warning output.
warnings.showwarning = lambda *a, **k: None

# Dummy API key values for use in tests
api_key = 'fakeapikey'
api_secret = 'fakeapisecret'
client_id = 'fakeid'
client_secret = 'fakesecret'
access_token = 'fakeaccesstoken'
refresh_token = 'fakerefreshtoken'


class TestClient(unittest2.TestCase):
  def test_key_and_secret_required(self):
    with self.assertRaises(ValueError):
      Client(None, api_secret)
    with self.assertRaises(ValueError):
      Client(api_key, None)

  @hp.activate
  def test_response_handling(self):
    resp200 = lambda r, u, h: (200, h, '')
    resp400 = lambda r, u, h: (400, h, '')
    resp401 = lambda r, u, h: (401, h, '')
    hp.register_uri(hp.GET, re.compile('.*200$'), resp200)
    hp.register_uri(hp.GET, re.compile('.*400$'), resp400)
    hp.register_uri(hp.GET, re.compile('.*401$'), resp401)

    client = Client(api_key, api_secret)

    assert client._get('200').status_code == 200

    with self.assertRaises(APIError):
      client._get('400')
    with self.assertRaises(AuthenticationError):
      client._get('401')

  @hp.activate
  def test_base_api_uri_used_instead_of_default(self):
    # Requests to the default BASE_API_URI will noticeably fail by raising an
    # AssertionError. Requests to the new URL will respond HTTP 200.
    new_base_api_uri = 'http://peterdowns.com/api/v1/'

    # If any error is raised by the server, the test suite will never exit when
    # using Python 3. This strange technique is used to raise the errors
    # outside of the mocked server environment.
    errors_in_server = []

    def server_response(request, uri, headers):
      try:
        self.assertEqual(uri, new_base_api_uri)
      except AssertionError as e:
        errors_in_server.append(e)
      return (200, headers, "")

    hp.register_uri(hp.GET, Client.BASE_API_URI, body=server_response)
    hp.register_uri(hp.GET, new_base_api_uri, body=server_response)

    client2 = Client(api_key, api_secret, new_base_api_uri)
    self.assertEqual(client2._get().status_code, 200)

    client = Client(api_key, api_secret)
    with self.assertRaises(AssertionError):
      client._get()
      if errors_in_server: raise errors_in_server.pop()

  @hp.activate
  def test_get_authorization(self):
    data = {'meta': 'example', 'key': 'value'}

    def server_response(request, uri, headers):
      return (200, headers, json.dumps(data)) # Data coming from outer scope.

    client = Client(api_key, api_secret)
    hp.register_uri(
        hp.GET, re.compile('.*'), body=server_response)
    authorization = client.get_authorization()

    self.assertIsInstance(authorization, APIObject)
    for key, value in authorization.items():
      self.assertEqual(data.get(key), value)

  @hp.activate
  def test_get_account(self):
    def make_server_response(account_id):
      def server_response(request, uri, headers):
        self.assertTrue(uri.endswith(account_id), (uri, account_id))
        return (200, headers, json.dumps(data)) # Data coming from outer scope.
      return server_response

    # Check that client fetches primary account by default.
    client = Client(api_key, api_secret)
    hp.register_uri(
        hp.GET, re.compile('.*'), body=make_server_response('primary'))
    data = {'account': {'id': '54a710dd25dc9a311800003f'}}
    account = client.get_account()
    self.assertIsInstance(account, Account)

    # Check that client fetches specific account ID.
    hp.reset()
    account_id = 'fakeid'
    hp.register_uri(
        hp.GET, re.compile('.*'), body=make_server_response(account_id))
    account = client.get_account(account_id)
    self.assertIsInstance(account, Account)

    # Check that the client raises error on bad response format
    data = {'notaccount': {'foo': 'bar'}}
    with self.assertRaises(UnexpectedDataFormatError):
      account = client.get_account(account_id)

  @hp.activate
  def test_get_accounts(self):
    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps({
        'current_page': 1,
        'num_pages': 1,
        'total_count': 3,
        'accounts': [{'id': '54a710dd25dc9a311800003f'},
                     {'id': '54a710dd25dc9a311800003g'}],
      }))
    client = Client(api_key, api_secret)
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)
    response = client.get_accounts()
    self.assertIsInstance(response, APIObject)
    self.assertEqual(len(response.accounts), 2)
    for account in response.accounts:
      self.assertIsInstance(account, Account)

  @hp.activate
  def test_create_account(self):
    def server_response(request, uri, headers):
      try: request_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      account = request_data.get('account')
      assert isinstance(account, dict)
      name = account.get('name')
      assert isinstance(name, six.string_types)
      return (200, headers, json.dumps(data))

    client = Client(api_key, api_secret)
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    data = {'account': {'id': 'fakeid'}, 'success': False}
    with self.assertRaises(APIError):
     client.create_account('accountname')

    data = {'noaccountkey': True, 'success': True}
    with self.assertRaises(UnexpectedDataFormatError):
      client.create_account('accountname')

    data = {'account': {'id': 'fakeid'}, 'success': True}
    account = client.create_account('accountname')
    self.assertIsInstance(account, Account)

  @hp.activate
  def test_get_contacts(self):
    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps(data))

    client = Client(api_key, api_secret)
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {
        'contacts': [{'id': '1'}, {'id': '2'}],
        'current_page': 1,
        'num_pages': 1,
        'total_count': 2,
      }
    contacts = client.get_contacts()
    self.assertIsInstance(contacts, APIObject)
    self.assertEqual(contacts, data)

  @hp.activate
  def test_get_current_user(self):
    def server_response(request, uri, headers):
      self.assertTrue(uri.endswith('users/self'))
      self.assertEqual(request.body.decode(), '')
      return (200, headers, json.dumps(data))

    client = Client(api_key, api_secret)
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {'nouserkey': True}
    with self.assertRaises(UnexpectedDataFormatError):
      client.get_current_user()

    data = {'user': {'id': 'fakeid'}}
    user = client.get_current_user()
    self.assertIsInstance(user, User)

  @hp.activate
  def test_get_buy_and_sell_price(self):
    def server_response(request, uri, headers):
      try: request_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      self.assertEqual(request_data.get('qty'), quantity)
      self.assertEqual(request_data.get('currency'), currency)
      return (200, headers, json.dumps(data))

    client = Client(api_key, api_secret)
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    for func in (client.get_buy_price, client.get_sell_price):
      quantity, currency = (None, None)
      data = {
          'amount': '10.25',
          'currency': 'USD',
          'btc': {'amount': '1.0', 'currency': 'BTC'},
        }
      price = func()
      self.assertIsInstance(price, Money)
      self.assertEqual(price, data)

      quantity, currency = (12, 'USD')
      price = func(quantity, currency)
      self.assertIsInstance(price, Money)
      self.assertEqual(price, data)


  @hp.activate
  def test_get_spot_price(self):
    def server_response(request, uri, headers):
      try: request_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      self.assertEqual(request_data.get('currency'), currency)
      return (200, headers, json.dumps(data))

    client = Client(api_key, api_secret)
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    currency = None
    data = {'amount': '1.000', 'currency': 'BTC'}
    price = client.get_spot_price()
    self.assertIsInstance(price, Money)
    self.assertEqual(price, data)

    currency = 'USD'
    data = {'amount': '10.00', 'currency': 'USD'}
    price = client.get_spot_price(currency)
    self.assertIsInstance(price, Money)
    self.assertEqual(price, data)


  @hp.activate
  def test_get_supported_currencies(self):
    def server_response(request, uri, headers):
      self.assertEqual(request.body.decode(), '')
      return (200, headers, json.dumps(data))

    client = Client(api_key, api_secret)
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = [['Afghan Afghani (AFN)', 'AFN'],
            ['United States Dollar (USD)', 'USD']]
    currencies = client.get_supported_currencies()
    self.assertIsInstance(currencies, list)
    self.assertEqual(currencies, data)


  @hp.activate
  def test_get_exchange_rates(self):
    def server_response(request, uri, headers):
      self.assertEqual(request.body.decode(), '')
      return (200, headers, json.dumps(data))

    client = Client(api_key, api_secret)
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {'aed_to_btc': '0.027224',
            'btc_to_aed' : '36.73247'}
    rates = client.get_exchange_rates()
    self.assertIsInstance(rates, APIObject)
    self.assertEqual(rates, data)

  @hp.activate
  def test_create_user(self):
    def server_response(request, uri, headers):
      try: request_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      if isinstance(scopes, (list, tuple)):
        self.assertEqual(' '.join(scopes), request_data['user']['scopes'])
      elif isinstance(scopes, six.string_types):
        self.assertEqual(scopes, request_data['user']['scopes'])
      self.assertIsInstance(request_data.get('user'), dict)
      return (200, headers, json.dumps(data))

    client = Client(api_key, api_secret)
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    scopes = None
    data = {'success': False, 'errors': ['Email is not available']}
    with self.assertRaises(APIError):
      client.create_user('example@example.com', 'password')

    for scopes in (['a', 'b', 'c'], ('a', 'b', 'c'), 'a b c'):
      data = {'success': True, 'user': {'id': 'fakeid'}}
      client.create_user('example@example.com', 'password', scopes=scopes)

  @hp.activate
  def test_get_payment_methods(self):
    def server_response(request, uri, headers):
      self.assertEqual(request.body.decode(), '')
      return (200, headers, json.dumps(data))

    client = Client(api_key, api_secret)
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {
        'default_buy': '54a710de25dc9a311800006e',
        'default_sell': '54a710de25dc9a311800006e',
        'payment_methods': [{ 'payment_method': {'can_buy': True,
                              'can_sell': True,
                              'currency': 'USD',
                              'id': '54a710de25dc9a311800006e',
                              'name': 'Test Bank *****1111',
                              'type': 'ach_bank_account'}}]}

    methods = client.get_payment_methods()
    self.assertIsInstance(methods, APIObject)
    for method in methods.payment_methods:
      self.assertIsInstance(method, PaymentMethod)
    for method in methods[::]:
      self.assertIsInstance(method, PaymentMethod)

  @hp.activate
  def test_get_payment_method(self):
    def server_response(request, uri, headers):
      self.assertEqual(request.body.decode(), '')
      return (200, headers, json.dumps(data))

    client = Client(api_key, api_secret)
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {"payment_method": {
              "id": "530eb5b217cb34e07a000011",
              "name": "US Bank ****4567",
              "can_buy": True,
              "can_sell": True}}

    method = client.get_payment_method('id')
    self.assertIsInstance(method, PaymentMethod)

    data = {'missing_payment_method_key': True}
    with self.assertRaises(UnexpectedDataFormatError):
      client.get_payment_method('id')

    data = {'payment_method': 'wrong-type'}
    with self.assertRaises(UnexpectedDataFormatError):
      client.get_payment_method('id')


class TestOauthClient(unittest2.TestCase):
  @hp.activate
  def test_auth_succeeds_with_bytes_and_unicode(self):
    resp200 = lambda r, uh, h: (200, h, '')
    hp.register_uri(hp.GET, re.compile('.*'), resp200)

    api_key = 'key'
    api_secret = 'secret'
    self.assertIsInstance(api_key, six.text_type) # Unicode
    self.assertIsInstance(api_secret, six.text_type) # Unicode

    client = Client(api_key, api_secret)
    self.assertEqual(client._get().status_code, 200)

    api_key = api_key.encode('utf-8')
    api_secret = api_secret.encode('utf-8')
    self.assertIsInstance(api_key, six.binary_type) # Bytes
    self.assertIsInstance(api_secret, six.binary_type) # Bytes

    client = Client(api_key, api_secret)
    self.assertEqual(client._get().status_code, 200)

  @hp.activate
  def test_response_handling(self):
    resp200 = lambda r, u, h: (200, h, '')
    resp400 = lambda r, u, h: (400, h, '')
    def resp401_expired(request, uri, headers):
      headers.update({
          'www-authenticate': (
            'Bearer realm="Doorkeeper", '
            'error="invalid_token", '
            'error_description="The access token expired"')})
      return (401, headers, '')
    def resp401_invalid(request, uri, headers):
      headers.update({
          'www-authenticate': (
            'Bearer realm="Doorkeeper", '
            'error="invalid_token", '
            'error_description="The access token is invalid"')})
      return (401, headers, '')
    def resp401_generic(request, uri, headers):
      headers.update({
          'www-authenticate': (
            'Bearer realm="Doorkeeper", '
            'error="some_error", '
            'error_description="Some description"')})
      return (401, headers, '')
    def resp401_noheader(request, uri, headers):
      self.assertIsNone(headers.get('www-authenticate'))
      return (401, headers, '')
    resp402 = lambda r, u, h: (402, h, '')

    hp.register_uri(hp.GET, re.compile('.*200$'), resp200)
    hp.register_uri(hp.GET, re.compile('.*400$'), resp400)
    hp.register_uri(hp.GET, re.compile('.*401_expired$'), resp401_expired)
    hp.register_uri(hp.GET, re.compile('.*401_invalid$'), resp401_invalid)
    hp.register_uri(hp.GET, re.compile('.*401_generic$'), resp401_generic)
    hp.register_uri(hp.GET, re.compile('.*401_noheader$'), resp401_noheader)
    hp.register_uri(hp.GET, re.compile('.*402$'), resp402)

    client = OAuthClient(client_id, client_secret, access_token, refresh_token)
    assert client._get('200').status_code == 200
    with self.assertRaises(APIError):
      client._get('400')
    with self.assertRaises(AuthenticationError):
      client._get('401_generic')
    with self.assertRaises(InvalidAccessToken):
      client._get('401_invalid')
    with self.assertRaises(ExpiredAccessToken):
      client._get('401_expired')
    with self.assertRaises(AuthenticationError):
      client._get('401_noheader')
    with self.assertRaises(TwoFactorTokenRequired):
      client._get('402')

  @hp.activate
  def test_base_api_uri_used_instead_of_default(self):
    # Requests to the default BASE_API_URI will noticeably fail by raising an
    # AssertionError. Requests to the new URL will respond HTTP 200.
    new_base_api_uri = 'http://example.com/api/v1/'

    # If any error is raised by the server, the test suite will never exit when
    # using Python 3. This strange technique is used to raise the errors
    # outside of the mocked server environment.
    errors_in_server = []
    def server_response(request, uri, headers):
      try:
        self.assertEqual(uri, new_base_api_uri)
      except AssertionError as e:
        errors_in_server.append(e)
      return (200, headers, "")

    hp.register_uri(hp.GET, OAuthClient.BASE_API_URI, body=server_response)
    hp.register_uri(hp.GET, new_base_api_uri, body=server_response)

    client = OAuthClient(client_id, client_secret, access_token, refresh_token)
    with self.assertRaises(AssertionError):
      client._get()
      if errors_in_server: raise errors_in_server.pop()

    client2 = OAuthClient(
        client_id,
        client_secret,
        access_token,
        refresh_token,
        base_api_uri=new_base_api_uri)
    self.assertEqual(client2._get().status_code, 200)

  @hp.activate
  def test_token_endpoint_uri_used_instead_of_default(self):
    # Requests to the default BASE_API_URI will noticeably fail by raising an
    # AssertionError. Requests to the new URL will respond HTTP 200.
    new_token_endpoint_uri = 'http://example.com/oauth/token'

    # If any error is raised by the server, the test suite will never exit when
    # using Python 3. This strange technique is used to raise the errors
    # outside of the mocked server environment.
    errors_in_server = []

    def server_response(request, uri, headers):
      parsed_uri = urlparse(uri)
      parsed_reference = urlparse(new_token_endpoint_uri)
      try:
        self.assertEqual(parsed_uri.scheme, parsed_reference.scheme)
        self.assertEqual(parsed_uri.netloc, parsed_reference.netloc)
        self.assertEqual(parsed_uri.path, parsed_reference.path)
      except AssertionError as e:
        errors_in_server.append(e)
      response = {
          'access_token': 'newaccesstoken',
          'refresh_token': 'newrefreshtoken',
        }
      return (200, headers, json.dumps(response))
    hp.register_uri(hp.POST, OAuthClient.TOKEN_ENDPOINT_URI, body=server_response)
    hp.register_uri(hp.POST, new_token_endpoint_uri, body=server_response)

    client = OAuthClient(client_id, client_secret, access_token, refresh_token)
    with self.assertRaises(AssertionError):
      client.refresh()
      if errors_in_server: raise errors_in_server.pop()

    client2 = OAuthClient(
        client_id,
        client_secret,
        access_token,
        refresh_token,
        token_endpoint_uri=new_token_endpoint_uri)
    self.assertTrue(client2.refresh())

  @hp.activate
  def test_refresh(self):
    client = OAuthClient(client_id, client_secret, access_token, refresh_token)

    def server_response(request, uri, headers):
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.POST, client.TOKEN_ENDPOINT_URI, body=server_response)

    data = {
        'access_token': 'newaccesstoken',
        'refresh_token': 'newrefreshtoken',
      }
    self.assertNotEqual(client.access_token, data['access_token'])
    self.assertNotEqual(client.refresh_token, data['refresh_token'])
    client.refresh()
    self.assertEqual(client.access_token, data['access_token'])
    self.assertEqual(client.refresh_token, data['refresh_token'])

    def server_response(request, uri, headers):
      return (400, headers, '')
    hp.reset()
    hp.register_uri(hp.POST, client.TOKEN_ENDPOINT_URI, body=server_response)

    client.access_token = access_token
    client.refresh_token = refresh_token
    with self.assertRaises(TokenRefreshError):
      client.refresh()
    self.assertEqual(client.access_token, access_token)
    self.assertEqual(client.refresh_token, refresh_token)

  def test_oauth_details_required(self):
    with self.assertRaises(ValueError):
      OAuthClient(None, client_secret, access_token, refresh_token)
    with self.assertRaises(ValueError):
      OAuthClient(client_id, None, access_token, refresh_token)
    with self.assertRaises(ValueError):
      OAuthClient(client_id, client_secret, None, refresh_token)
    with self.assertRaises(ValueError):
      OAuthClient(client_id, client_secret, access_token, None)
