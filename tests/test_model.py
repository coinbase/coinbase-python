# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import re
import unittest2
import warnings

import httpretty as hp

from coinbase.client import Client
from coinbase.client import OAuthClient
from coinbase.error import APIError
from coinbase.error import TwoFactorTokenRequired
from coinbase.error import UnexpectedDataFormatError
from coinbase.model import APIObject
from coinbase.model import Account
from coinbase.model import Address
from coinbase.model import Button
from coinbase.model import Money
from coinbase.model import Order
from coinbase.model import Transaction
from coinbase.model import Transfer


# Hide all warning output.
warnings.showwarning = lambda *a, **k: None

# Dummy API key values for use in tests
api_key = 'fakeapikey'
api_secret = 'fakeapisecret'
client_id = 'fakeid'
client_secret = 'fakesecret'
access_token = 'fakeaccesstoken'
refresh_token = 'fakerefreshtoken'


class TestAccount(unittest2.TestCase):
  @hp.activate
  def test_delete(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    def server_response(request, uri, headers):
      self.assertTrue(uri.endswith(account.id))
      self.assertEqual(request.body.decode(), '')
      return (200, headers, json.dumps(data))

    hp.register_uri(hp.DELETE, re.compile('.*'), body=server_response)
    data = {'success': False}
    with self.assertRaises(APIError):
      account.delete()

    data = {'success': True}
    self.assertIsNone(account.delete())

  @hp.activate
  def test_set_primary(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    account.primary = None

    def server_response(request, uri, headers):
      self.assertTrue(uri.endswith('%s/primary' % account.id))
      self.assertEqual(request.body.decode(), '')
      return (200, headers, json.dumps(data))

    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)
    data = {'success': False}
    with self.assertRaises(APIError):
      account.set_primary()
    self.assertIsNone(account.primary) # Primary status should not have changed.

    data = {'success': True}
    account.set_primary()
    self.assertTrue(account.primary) # Primary status should have changed.

  @hp.activate
  def test_modify(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    account.name = initial_name = 'Wallet'

    def server_response(request, uri, headers):
      self.assertTrue(uri.endswith(account.id))
      try: request_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      name = request_data.get('account', {}).get('name')
      assert name == new_name
      return (200, headers, json.dumps(data))

    new_name = 'Vault'
    data = {'success': False, 'account': {'name': new_name}}
    hp.register_uri(hp.PUT, re.compile('.*'), body=server_response)
    with self.assertRaises(APIError):
      account.modify(new_name)
    self.assertEqual(account.name, initial_name)

    data = {'success': True, 'account': {'name': new_name}}
    account.modify(new_name)
    self.assertEqual(account.name, new_name)

    data = {'success': True, 'account': 'nottherighttype'}
    with self.assertRaises(UnexpectedDataFormatError):
      account.modify(new_name)

  @hp.activate
  def test_get_balance(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    account.balance = initial_balance = lambda: None # Initial value

    def server_response(request, uri, headers):
      self.assertTrue(uri.endswith('%s/balance' % account.id))
      self.assertEqual(request.body.decode(), '')
      return (200, headers, json.dumps(data))

    data = {'currency': 'USD', 'amount': '10.00'}
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)
    balance = account.get_balance()
    self.assertIsInstance(balance, Money)
    # Fetching the current balance should not modify the balance attribute on
    # the Account object.
    self.assertEqual(account.balance, initial_balance)

  @hp.activate
  def test_get_address(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    def server_response(request, uri, headers):
      self.assertTrue(uri.endswith('%s/address' % account.id))
      self.assertEqual(request.body.decode(), '')
      return (200, headers, json.dumps(data))

    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {'address': 'a',
            'callback_url': None,
            'label': None,
            'success': False}
    with self.assertRaises(APIError):
      account.get_address()

    data = {'badkey': 'bar',
            'success': True}
    with self.assertRaises(UnexpectedDataFormatError):
      account.get_address()

    data = {'address': 'a',
            'callback_url': None,
            'label': None,
            'success': True}
    address = account.get_address()
    self.assertIsInstance(address, Address)

  @hp.activate
  def test_get_addresses(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      data = {
          'total_count': 3,
          'current_page': 1,
          'num_pages': 1,
          'addresses': [
            {'address': {
              'label': '',
              'address': 'foo',
              'callback_url': '',
              'id': '1'
            }},
            {'address': {
              'label': '',
              'address': 'foo',
              'callback_url': '',
              'id': '2'
            }},
            {'address': {
              'label': '',
              'address': 'foo',
              'callback_url': '',
              'id': '3'
            }},
          ],
        }
      return (200, headers, json.dumps(data))

    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)
    response = account.get_addresses()
    self.assertIsInstance(response, APIObject)
    self.assertEqual(len(response.addresses), 3)
    for address in response.addresses:
      self.assertIsInstance(address, Address)

  @hp.activate
  def test_create_address(self):
    def server_response(request, uri, headers):
      try: request_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      address = request_data.get('address')
      assert isinstance(address, dict)
      if label is not None:
        assert address.get('label') == label
      if callback_url is not None:
        assert address.get('callback_url') == callback_url
      return (200, headers, json.dumps(data))

    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    label, callback_url = ('label', 'http://example.com/')
    data = {'success': False,
            'address': 'foo',
            'label': label,
            'callback_url': callback_url}
    with self.assertRaises(APIError):
     account.create_address(label, callback_url)

    label, callback_url = ('label', 'http://example.com/')
    data = {'success': True, 'arbkey': 'bar'}
    with self.assertRaises(UnexpectedDataFormatError):
     account.create_address(label, callback_url)

    label, callback_url = ('label', 'http://example.com/')
    data = {'success': True,
            'address': 'foo',
            'label': label,
            'callback_url': callback_url}
    address = account.create_address(label, callback_url)
    self.assertIsInstance(address, Address)

    label, callback_url = (None, None)
    data = {'success': True,
            'address': 'foo',
            'label': label,
            'callback_url': callback_url}
    address = account.create_address()
    self.assertIsInstance(address, Address)

  @hp.activate
  def test_get_transactions(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      data = {
          'total_count': 3,
          'current_page': 1,
          'num_pages': 1,
          'transactions': [
            {'transaction': {'id': '1'}},
            {'transaction': {'id': '2'}},
            {'transaction': {'id': '3'}},
          ],
        }
      return (200, headers, json.dumps(data))

    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)
    response = account.get_transactions()
    self.assertIsInstance(response, APIObject)
    self.assertEqual(len(response.transactions), 3)
    for transaction in response.transactions:
      self.assertIsInstance(transaction, Transaction)

  @hp.activate
  def test_get_transaction(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps(data))

    transaction_id = 'faketransactionid'
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {'missing_transaction_key': True}
    with self.assertRaises(UnexpectedDataFormatError):
      account.get_transaction(transaction_id)

    data = {'transaction': 'not-the-right-type'}
    with self.assertRaises(UnexpectedDataFormatError):
      account.get_transaction(transaction_id)

    data = {'transaction': {'id': '1'}}
    transaction = account.get_transaction(transaction_id)
    self.assertIsInstance(transaction, Transaction)

  @hp.activate
  def test_transfer_money(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    base_kwargs = {
        'to_account_id': 'fake-account-id',
        'amount': '12.0 BTC',
      }
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(amount=None, amount_string=None, amount_currency_iso=None)
      account.transfer_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(
          amount='12.0', amount_string=None, amount_currency_iso='USD')
      account.transfer_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(
          amount='12.0', amount_string='12.0', amount_currency_iso=None)
      account.transfer_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(
          amount='12.0', amount_string='12.0', amount_currency_iso='USD')
      account.transfer_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(amount=None, amount_string=None, amount_currency_iso='USD')
      account.transfer_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(amount=None, amount_string='12.0', amount_currency_iso=None)
      account.transfer_money(**kwargs)

    def server_response(request, uri, headers):
      try: req = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      tx_data = req.get('transaction')
      self.assertIsInstance(tx_data, dict)
      self.assertEqual(len(tx_data), len(kwargs))
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    with self.assertRaises(APIError):
      data = {'success': False, 'transaction': {'id': '1'}}
      kwargs = base_kwargs.copy()
      account.transfer_money(**kwargs)
    with self.assertRaises(UnexpectedDataFormatError):
      data = {'success': True, 'transaction': 'wrong-type'}
      kwargs = base_kwargs.copy()
      account.transfer_money(**kwargs)
    with self.assertRaises(UnexpectedDataFormatError):
      data = {'success': True, 'missing-transaction-key': True}
      kwargs = base_kwargs.copy()
      account.transfer_money(**kwargs)

    data = {'success': True, 'transaction': {'id': '1'}}
    kwargs = base_kwargs.copy()
    tx = account.transfer_money(**kwargs)
    self.assertIsInstance(tx, Transaction)

  @hp.activate
  def test_send_money(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    base_kwargs = {
        'to_btc_address': 'some-btc-address',
        'amount': '12.0 BTC',
      }
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(amount=None, amount_string=None, amount_currency_iso=None)
      account.send_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(
          amount='12.0', amount_string=None, amount_currency_iso='USD')
      account.send_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(
          amount='12.0', amount_string='12.0', amount_currency_iso=None)
      account.send_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(
          amount='12.0', amount_string='12.0', amount_currency_iso='USD')
      account.send_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(amount=None, amount_string=None, amount_currency_iso='USD')
      account.send_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(amount=None, amount_string='12.0', amount_currency_iso=None)
      account.send_money(**kwargs)

    def server_response(request, uri, headers):
      try: req = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      tx_data = req.get('transaction')
      self.assertIsInstance(tx_data, dict)
      self.assertEqual(len(tx_data), len(kwargs))
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    with self.assertRaises(APIError):
      data = {'success': False, 'transaction': {'id': '1'}}
      kwargs = base_kwargs.copy()
      account.send_money(**kwargs)
    with self.assertRaises(UnexpectedDataFormatError):
      data = {'success': True, 'transaction': 'wrong-type'}
      kwargs = base_kwargs.copy()
      account.send_money(**kwargs)
    with self.assertRaises(UnexpectedDataFormatError):
      data = {'success': True, 'missing-transaction-key': True}
      kwargs = base_kwargs.copy()
      account.send_money(**kwargs)

    data = {'success': True, 'transaction': {'id': '1'}}
    kwargs = base_kwargs.copy()
    tx = account.send_money(**kwargs)
    self.assertIsInstance(tx, Transaction)

    oauth_account = Account(
        OAuthClient(client_id, client_secret, access_token, refresh_token))
    oauth_account.id = 'fakeaccountid'

    hp.reset()
    def server_response(request, uri, headers):
      try: req = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      tx_data = req.get('transaction')
      self.assertIsInstance(tx_data, dict)
      if two_factor_token:
        self.assertEqual(request.headers.get('CB-2FA-Token'), two_factor_token)
        self.assertIsNone(tx_data.get('CB-2FA-Token'))
        return (200, headers, json.dumps(data))
      return (402, headers, '')
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    kwargs = base_kwargs.copy()
    kwargs['two_factor_token'] = two_factor_token = None
    with self.assertRaises(TwoFactorTokenRequired):
      oauth_account.send_money(**kwargs)

    kwargs['two_factor_token'] = two_factor_token = 'sometoken'
    tx = oauth_account.send_money(**kwargs)
    self.assertIsInstance(tx, Transaction)

  @hp.activate
  def test_request_money(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    base_kwargs = {
        'from_email_address': 'some-btc-address',
        'amount': '12.0 BTC',
      }
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(amount=None, amount_string=None, amount_currency_iso=None)
      account.request_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(
          amount='12.0', amount_string=None, amount_currency_iso='USD')
      account.request_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(
          amount='12.0', amount_string='12.0', amount_currency_iso=None)
      account.request_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(
          amount='12.0', amount_string='12.0', amount_currency_iso='USD')
      account.request_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(amount=None, amount_string=None, amount_currency_iso='USD')
      account.request_money(**kwargs)
    with self.assertRaises(ValueError):
      kwargs = base_kwargs.copy()
      kwargs.update(amount=None, amount_string='12.0', amount_currency_iso=None)
      account.request_money(**kwargs)

    def server_response(request, uri, headers):
      try: req = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      tx_data = req.get('transaction')
      self.assertIsInstance(tx_data, dict)
      self.assertEqual(len(tx_data), len(kwargs))
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    with self.assertRaises(APIError):
      data = {'success': False, 'transaction': {'id': '1'}}
      kwargs = base_kwargs.copy()
      account.request_money(**kwargs)
    with self.assertRaises(UnexpectedDataFormatError):
      data = {'success': True, 'transaction': 'wrong-type'}
      kwargs = base_kwargs.copy()
      account.request_money(**kwargs)
    with self.assertRaises(UnexpectedDataFormatError):
      data = {'success': True, 'missing-transaction-key': True}
      kwargs = base_kwargs.copy()
      account.request_money(**kwargs)

    data = {'success': True, 'transaction': {'id': '1'}}
    kwargs = base_kwargs.copy()
    tx = account.request_money(**kwargs)
    self.assertIsInstance(tx, Transaction)

  @hp.activate
  def test_get_transfers(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps(data))

    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {
        'total_count': 3,
        'current_page': 1,
        'num_pages': 1,
        'transfers': [
          {'transfer': {'id': '1'}},
          {'transfer': {'id': '2'}},
          {'transfer': {'id': '3'}},
        ],
      }
    response = account.get_transfers()
    self.assertIsInstance(response, APIObject)
    self.assertEqual(len(response.transfers), 3)
    for transfer in response.transfers:
      self.assertIsInstance(transfer, Transfer)

  @hp.activate
  def test_get_transfer(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps(data))

    transfer_id = 'faketransferid'
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {'missing_transfer_key': True}
    with self.assertRaises(UnexpectedDataFormatError):
      account.get_transfer(transfer_id)

    data = {'transfer': 'not-the-right-type'}
    with self.assertRaises(UnexpectedDataFormatError):
      account.get_transfer(transfer_id)

    data = {'transfer': {'id': '1'}}
    transfer = account.get_transfer(transfer_id)
    self.assertIsInstance(transfer, Transfer)

  @hp.activate
  def test_get_button(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    button_code = 'fakebuttoncode'

    def server_response(request, uri, headers):
      self.assertEqual(request.body.decode(), '')
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {'button': 'not-the-right-type'}
    with self.assertRaises(UnexpectedDataFormatError):
      account.get_button(button_code)

    data = {'missing-button-key': True}
    with self.assertRaises(UnexpectedDataFormatError):
      account.get_button(button_code)

    data = {'button': {'code': button_code}}
    button = account.get_button(button_code)
    self.assertIsInstance(button, Button)

    data = {'badkey': 'bar',
            'success': True}
    with self.assertRaises(UnexpectedDataFormatError):
      account.get_address()

    data = {'address': 'a',
            'callback_url': None,
            'label': None,
            'success': True}
    address = account.get_address()
    self.assertIsInstance(address, Address)

  @hp.activate
  def test_create_button(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    def server_response(request, uri, headers):
      try: request_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      button_data = request_data.get('button')
      self.assertIsInstance(button_data, dict)
      for key in ['name', 'price_string', 'price_currency_iso']:
        self.assertTrue(key in button_data)
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    name = 'b-name'
    price_string = 'b-price'
    price_currency_iso = 'BTC'
    with self.assertRaises(APIError):
     data = {
         'success': False,
         'button': {
           'name': name,
           'price_string': price_string,
           'price_currency_iso': price_currency_iso,

         },
       }
     account.create_button(name, price_string, price_currency_iso)

    with self.assertRaises(UnexpectedDataFormatError):
     data = {'success': True, 'button': 'wrong-type'}
     account.create_button(name, price_string, price_currency_iso)

    with self.assertRaises(UnexpectedDataFormatError):
     data = {'success': True, 'missing-button-key': True}
     account.create_button(name, price_string, price_currency_iso)

    data = {
        'success': True,
        'button': {
          'name': name,
          'price_string': price_string,
          'price_currency_iso': price_currency_iso,

        },
      }
    button = account.create_button(name, price_string, price_currency_iso)
    self.assertIsInstance(button, Button)

  @hp.activate
  def test_get_orders(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {
        'total_count': 3,
        'current_page': 1,
        'num_pages': 1,
        'orders': [
          {'order': {'id': '1'}},
          {'order': {'id': '2'}},
          {'order': {'id': '3'}},
        ],
      }
    response = account.get_orders()
    self.assertIsInstance(response, APIObject)
    self.assertEqual(len(response.orders), 3)
    for order in response.orders:
      self.assertIsInstance(order, Order)

  @hp.activate
  def test_get_order(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps(data))

    order_id = 'fakeorderid'
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {'missing_order_key': True}
    with self.assertRaises(UnexpectedDataFormatError):
      account.get_order(order_id)

    data = {'order': 'not-the-right-type'}
    with self.assertRaises(UnexpectedDataFormatError):
      account.get_order(order_id)

    data = {'order': {'id': '1'}}
    order = account.get_order(order_id)
    self.assertIsInstance(order, Order)

  @hp.activate
  def test_create_order(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    def server_response(request, uri, headers):
      try: request_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      button_data = request_data.get('button')
      self.assertIsInstance(button_data, dict)
      for key in ['name', 'price_string', 'price_currency_iso']:
        self.assertTrue(key in button_data)
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    name = 'b-name'
    price_string = 'b-price'
    price_currency_iso = 'BTC'
    with self.assertRaises(APIError):
     data = {
         'success': False,
         'order': {
           'name': name,
           'price_string': price_string,
           'price_currency_iso': price_currency_iso,

         },
       }
     account.create_order(name, price_string, price_currency_iso)

    with self.assertRaises(UnexpectedDataFormatError):
     data = {'success': True, 'order': 'wrong-type'}
     account.create_order(name, price_string, price_currency_iso)

    with self.assertRaises(UnexpectedDataFormatError):
     data = {'success': True, 'missing-order-key': True}
     account.create_order(name, price_string, price_currency_iso)

    data = {
        'success': True,
        'order': {
          'name': name,
          'price_string': price_string,
          'price_currency_iso': price_currency_iso,

        },
      }
    order = account.create_order(name, price_string, price_currency_iso)
    self.assertIsInstance(order, Order)

  @hp.activate
  def test_buy(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    def server_response(request, uri, headers):
      try: request_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      self.assertEqual(request_data.get('account_id'), account.id)
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    with self.assertRaises(APIError):
     data = {'success': False, 'transfer': {'id': 'transferid'}}
     account.buy('1.0')

    with self.assertRaises(UnexpectedDataFormatError):
     data = {'success': True, 'transfer': 'wrong-type'}
     account.buy('1.0')

    with self.assertRaises(UnexpectedDataFormatError):
     data = {'success': True, 'missing-transfer-key': True}
     account.buy('1.0')

    data = {'success': True, 'transfer': {'id': 'transferid'}}
    transfer = account.buy('1.0')
    self.assertIsInstance(transfer, Transfer)

  @hp.activate
  def test_sell(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'

    def server_response(request, uri, headers):
      try: request_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      self.assertEqual(request_data.get('account_id'), account.id)
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    with self.assertRaises(APIError):
     data = {'success': False, 'transfer': {'id': 'transferid'}}
     account.sell('1.0')

    with self.assertRaises(UnexpectedDataFormatError):
     data = {'success': True, 'transfer': 'wrong-type'}
     account.sell('1.0')

    with self.assertRaises(UnexpectedDataFormatError):
     data = {'success': True, 'missing-transfer-key': True}
     account.sell('1.0')

    data = {'success': True, 'transfer': {'id': 'transferid'}}
    transfer = account.sell('1.0')
    self.assertIsInstance(transfer, Transfer)



class TestButton(unittest2.TestCase):
  @hp.activate
  def test_get_orders(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    initial_name = 'name'
    initial_price_string = '12.0'
    initial_price_currency_iso = 'USD'

    button = account.load({
      'button': {
        'id': '1',
        'name': initial_name,
        'price_string': initial_price_string,
        'price_currency_iso': initial_price_currency_iso,
        'code': 'buttoncode',
      },
    }).button

    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.GET, re.compile('.*'), body=server_response)

    data = {
        'total_count': 3,
        'current_page': 1,
        'num_pages': 1,
        'orders': [
          {'order': {'id': '1'}},
          {'order': {'id': '2'}},
          {'order': {'id': '3'}},
        ],
      }
    response = button.get_orders()
    self.assertIsInstance(response, APIObject)
    self.assertEqual(len(response.orders), 3)
    for order in response.orders:
      self.assertIsInstance(order, Order)

  @hp.activate
  def test_create_order(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    initial_name = 'name'
    initial_price_string = '12.0'
    initial_price_currency_iso = 'USD'

    button = account.load({
      'button': {
        'id': '1',
        'name': initial_name,
        'price_string': initial_price_string,
        'price_currency_iso': initial_price_currency_iso,
        'code': 'buttoncode',
      },
    }).button

    def server_response(request, uri, headers):
      self.assertEqual(request.body.decode(), '')
      return (200, headers, json.dumps(data))

    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    name = 'b-name'
    price_string = 'b-price'
    price_currency_iso = 'BTC'
    with self.assertRaises(APIError):
     data = {
         'success': False,
         'order': {
           'name': name,
           'price_string': price_string,
           'price_currency_iso': price_currency_iso,

         },
       }
     button.create_order()

    with self.assertRaises(UnexpectedDataFormatError):
     data = {'success': True, 'order': 'wrong-type'}
     button.create_order()

    with self.assertRaises(UnexpectedDataFormatError):
     data = {'success': True, 'missing-order-key': True}
     button.create_order()

    data = {
        'success': True,
        'order': {
          'name': name,
          'price_string': price_string,
          'price_currency_iso': price_currency_iso,

        },
      }
    order = button.create_order()
    self.assertIsInstance(order, Order)


class TestMoney(unittest2.TestCase):
  def test_str_representation(self):
    money = APIObject(None).load({
      'amount': '12.0',
      'currency': 'BTC',
    })
    self.assertIsInstance(money, Money)
    self.assertTrue(str(money).endswith('BTC 12.0'))

    money2 = APIObject(None).load({
      'amount': '12.0',
      'currency': 'BTC',
      'foo': 'Bar',
    })
    self.assertIsInstance(money2, Money)
    self.assertTrue(str(money2).endswith('}'))


class TestOrder(unittest2.TestCase):
  @hp.activate
  def test_refund(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    order = account.load({
      'order': {
        'id': '1',
        'custom': 'custom',
        'button': {
          'id': 'fakeid',
          'code': 'acode'
        },
      },
    }).order
    def server_response(request, uri, headers):
      try: req_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      order_data = req_data.get('order')
      self.assertIsInstance(order_data, dict)
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    with self.assertRaises(UnexpectedDataFormatError):
      data = {'order': 'wrong-type'}
      order.refund('USD')
    with self.assertRaises(UnexpectedDataFormatError):
      data = {'missing-order-key': True}
      order.refund('USD')

    data = {'order': {'id': '1'}}
    refunded = order.refund('USD')
    self.assertEqual(refunded, data['order'])
    self.assertIsInstance(refunded, Order)


class TestTransaction(unittest2.TestCase):
  @hp.activate
  def test_resend(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    transaction = account.load({'transaction': {'id': '1' }}).transaction

    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.PUT, re.compile('.*'), body=server_response)

    with self.assertRaises(APIError):
      data = {'success': False}
      transaction.resend()

    data = {'success': True}
    self.assertTrue(transaction.resend())

  @hp.activate
  def test_complete(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    transaction = account.load({'transaction': {'id': '1' }}).transaction

    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.PUT, re.compile('.*'), body=server_response)

    with self.assertRaises(APIError):
      data = {'success': False, 'transaction': {'id': '1'}}
      transaction.complete()
    with self.assertRaises(UnexpectedDataFormatError):
      data = {'success': True, 'transaction': 'wrong-type'}
      transaction.complete()
    with self.assertRaises(UnexpectedDataFormatError):
      data = {'success': True, 'missing-transaction-key': True}
      transaction.complete()

    data = {'success': True, 'transaction': {'id': '1'}}
    tx = transaction.complete()
    self.assertIsInstance(tx, Transaction)

  @hp.activate
  def test_cancel(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    transaction = account.load({'transaction': {'id': '1' }}).transaction

    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.DELETE, re.compile('.*'), body=server_response)

    with self.assertRaises(APIError):
      data = {'success': False}
      transaction.cancel()

    data = {'success': True}
    self.assertTrue(transaction.cancel())


class TestTransfer(unittest2.TestCase):
  @hp.activate
  def test_commit(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    transfer = account.load({'transfer': {'id': '1' }}).transfer

    def server_response(request, uri, headers):
      try: json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.POST, re.compile('.*'), body=server_response)

    with self.assertRaises(APIError):
      data = {'success': False, 'transfer': {'id': '1'}}
      transfer.commit()
    with self.assertRaises(UnexpectedDataFormatError):
      data = {'success': True, 'transfer': 'wrong-type'}
      transfer.commit()
    with self.assertRaises(UnexpectedDataFormatError):
      data = {'success': True, 'missing-transfer-key': True}
      transfer.commit()

    data = {'success': True, 'transfer': {'id': '1'}}
    tx = transfer.commit()
    self.assertIsInstance(tx, Transfer)

class TestUser(unittest2.TestCase):
  @hp.activate
  def test_modify(self):
    account = Account(Client(api_key, api_secret))
    account.id = 'fakeaccountid'
    initial_native_currency = 'USD',
    initial_time_zone = 'Pacific Time (US & Canada)'
    initial_name = 'Test User'
    user = account.load({
      'user': {
        'id': '1',
        'name': initial_name,
        'native_currency': initial_native_currency,
        'time_zone': initial_time_zone,
      },
    }).user

    with self.assertRaises(ValueError):
      user.modify()

    def server_response(request, uri, headers):
      self.assertTrue(uri.endswith(user.id))
      try: request_data = json.loads(request.body.decode())
      except ValueError: raise AssertionError("request body was malformed.")
      user_data = request_data.get('user')
      self.assertIsInstance(user_data, dict)
      return (200, headers, json.dumps(data))
    hp.register_uri(hp.PUT, re.compile('.*'), body=server_response)

    with self.assertRaises(APIError):
      new_name = 'Fake Name'
      data = {
          'success': False,
          'user': {
            'id': user.id,
            'name': new_name,
            'native_currency': initial_native_currency,
            'time_zone': initial_time_zone,
          },
        }
      user.modify(name=new_name)
    self.assertEqual(user.name, initial_name)
    self.assertEqual(user.native_currency, initial_native_currency)
    self.assertEqual(user.time_zone, initial_time_zone)

    with self.assertRaises(UnexpectedDataFormatError):
      new_name = 'Fake Name'
      data = {'success': True, 'user': 'wrong-type'}
      user.modify(name=new_name)
    self.assertEqual(user.name, initial_name)
    self.assertEqual(user.native_currency, initial_native_currency)
    self.assertEqual(user.time_zone, initial_time_zone)

    with self.assertRaises(UnexpectedDataFormatError):
      new_name = 'Fake Name'
      data = {'success': True, 'missing-user-key': True}
      user.modify(name=new_name)
    self.assertEqual(user.name, initial_name)
    self.assertEqual(user.native_currency, initial_native_currency)
    self.assertEqual(user.time_zone, initial_time_zone)

    new_name = 'Fake Name'
    new_native_currency = 'CAD'
    new_time_zone = 'Eastern'
    data = {
        'success': True,
        'user': {
          'id': user.id,
          'name': new_name,
          'native_currency': new_native_currency,
          'time_zone': new_time_zone,
        },
      }
    user.modify(name=new_name,
                time_zone=new_time_zone,
                native_currency=new_native_currency)
    self.assertEqual(user.name, new_name)
    self.assertEqual(user.native_currency, new_native_currency)
    self.assertEqual(user.time_zone, new_time_zone)
