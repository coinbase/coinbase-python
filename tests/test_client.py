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

from coinbase.wallet.client import Client
from coinbase.wallet.client import OAuthClient
from coinbase.wallet.error import APIError
from coinbase.wallet.error import AuthenticationError
from coinbase.wallet.error import InvalidTokenError
from coinbase.wallet.error import TwoFactorRequiredError
from coinbase.wallet.error import ExpiredTokenError
from coinbase.wallet.error import RevokedTokenError
from coinbase.wallet.model import APIObject
from coinbase.wallet.model import Account
from coinbase.wallet.model import Merchant
from coinbase.wallet.model import Checkout
from coinbase.wallet.model import Address
from coinbase.wallet.model import Order
from coinbase.wallet.model import Buy
from coinbase.wallet.model import CurrentUser
from coinbase.wallet.model import Deposit
from coinbase.wallet.model import PaymentMethod
from coinbase.wallet.model import Sell
from coinbase.wallet.model import Transaction
from coinbase.wallet.model import User
from coinbase.wallet.model import Withdrawal
from coinbase.wallet.model import Report
from tests.helpers import mock_response


# Hide all warning output.
warnings.showwarning = lambda *a, **k: None

# Dummy API key values for use in tests
api_key = 'fakeapikey'
api_secret = 'fakeapisecret'
client_id = 'fakeid'
client_secret = 'fakesecret'
access_token = 'fakeaccesstoken'
refresh_token = 'fakerefreshtoken'

mock_item = {'key1': 'val1', 'key2': 'val2'}
mock_collection = [mock_item, mock_item]


class TestClient(unittest2.TestCase):
  def test_key_and_secret_required(self):
    with self.assertRaises(ValueError):
      Client(None, api_secret)
    with self.assertRaises(ValueError):
      Client(api_key, None)

  @mock_response(hp.GET, 'test', {})
  def test_auth_succeeds_with_bytes_and_unicode(self):
    api_key = 'key'
    api_secret = 'secret'
    self.assertIsInstance(api_key, six.text_type) # Unicode
    self.assertIsInstance(api_secret, six.text_type) # Unicode

    client = Client(api_key, api_secret)
    self.assertEqual(client._get('test').status_code, 200)

    api_key = api_key.encode('utf-8')
    api_secret = api_secret.encode('utf-8')
    self.assertIsInstance(api_key, six.binary_type) # Bytes
    self.assertIsInstance(api_secret, six.binary_type) # Bytes

    client = Client(api_key, api_secret)
    self.assertEqual(client._get('test').status_code, 200)

  @hp.activate
  def test_request_includes_auth_headers(self):
    client = Client(api_key, api_secret)
    def server_response(request, uri, response_headers):
      keys = [
          'CB-VERSION', 'CB-ACCESS-KEY', 'CB-ACCESS-SIGN',
          'CB-ACCESS-TIMESTAMP', 'Accept', 'Content-Type', 'User-Agent']
      for key in keys:
        self.assertIn(key, request.headers)
        self.assertNotEqual(request.headers[key], '')
      return 200, response_headers, '{}'
    hp.register_uri(hp.GET, re.compile('.*test$'), server_response)
    self.assertEqual(client._get('test').status_code, 200)

  @hp.activate
  def test_response_handling(self):
    client = Client(api_key, api_secret)
    # Check that 2XX responses always return the response
    error_response = {
        'errors': [{
          'id': 'fakeid',
          'message': 'some error message',
        }],
        'data': mock_item,
      }
    error_str = json.dumps(error_response)
    for code in [200, 201, 204]:
      hp.register_uri(
          hp.GET,
          re.compile('.*' + str(code) + '$'),
          lambda r, u, h: (code, h, error_str))
      response = client._get(str(code))
      self.assertEqual(response.status_code, code)

    # Check that when the error data is in the response, that's what is used.
    import coinbase.wallet.error
    for eid, eclass in six.iteritems(
        coinbase.wallet.error._error_id_to_class):
      error_response = {
        'errors': [{
          'id': eid,
          'message': 'some message',
        }],
        'data': mock_item,
      }
      error_str = json.dumps(error_response)
      hp.reset()
      hp.register_uri(
          hp.GET,
          re.compile('.*test$'),
          lambda r, u, h: (400, h, error_str))
      with self.assertRaises(eclass):
        client._get('test')

    # Check that when the error data is missing, the status code is used
    # instead.
    error_response = {'data': mock_item}
    for code, eclass in six.iteritems(
        coinbase.wallet.error._status_code_to_class):
      hp.reset()
      hp.register_uri(
          hp.GET,
          re.compile('.*test$'),
          lambda r, u, h: (code, h, json.dumps(error_response)))
      with self.assertRaises(eclass):
        client._get('test')

    # Check that when the response code / error id is unrecognized, a generic
    # APIError is returned
    hp.reset()
    hp.register_uri(hp.GET, re.compile('.*test$'), lambda r, u, h: (418, h, '{}'))
    with self.assertRaises(APIError):
      client._get('test')

  @hp.activate
  def test_request_helper_automatically_encodes_data(self):
    client = Client(api_key, api_secret)
    def server_response(request, uri, headers):
      self.assertIsInstance(request.body, six.binary_type)
      return 200, headers, '{}'
    hp.register_uri(hp.POST, re.compile('.*foo$'), server_response)
    self.assertEqual(client._post('foo', data={'name': 'example'}).status_code, 200)

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

    hp.register_uri(hp.GET, Client.BASE_API_URI, body=server_response)
    hp.register_uri(hp.GET, new_base_api_uri, body=server_response)

    client2 = Client(api_key, api_secret, new_base_api_uri)
    self.assertEqual(client2._get().status_code, 200)

    client = Client(api_key, api_secret)
    with self.assertRaises(AssertionError):
      client._get()
      if errors_in_server: raise errors_in_server.pop()


  @mock_response(hp.GET, '/v2/currencies', mock_collection, warnings=[{'message':'foo','url':'bar'}])
  def test_get_currencies(self):
    client = Client(api_key, api_secret)
    currencies = client.get_currencies()
    self.assertIsInstance(currencies, APIObject)
    self.assertEqual(currencies.data, mock_collection)

  @mock_response(hp.GET, '/v2/exchange-rates', mock_collection)
  def test_get_exchange_rates(self):
    client = Client(api_key, api_secret)
    exchange_rates = client.get_exchange_rates()
    self.assertIsInstance(exchange_rates, APIObject)
    self.assertEqual(exchange_rates.data, mock_collection)

  @mock_response(hp.GET, '/v2/prices/BTC-USD/buy', mock_item)
  def test_get_buy_price(self):
    client = Client(api_key, api_secret)
    buy_price = client.get_buy_price()
    self.assertIsInstance(buy_price, APIObject)
    self.assertEqual(buy_price, mock_item)

  @mock_response(hp.GET, '/v2/prices/BTC-USD/sell', mock_item)
  def test_get_sell_price(self):
    client = Client(api_key, api_secret)
    sell_price = client.get_sell_price()
    self.assertIsInstance(sell_price, APIObject)
    self.assertEqual(sell_price, mock_item)

  @mock_response(hp.GET, '/v2/prices/BTC-USD/spot', mock_item)
  def test_get_spot_price(self):
    client = Client(api_key, api_secret)
    spot_price = client.get_spot_price()
    self.assertIsInstance(spot_price, APIObject)
    self.assertEqual(spot_price, mock_item)

  @mock_response(hp.GET, '/v2/prices/BTC-USD/historic', mock_item)
  def test_get_historic_prices(self):
    client = Client(api_key, api_secret)
    historic_prices = client.get_historic_prices(currency_pair='BTC-USD')
    self.assertIsInstance(historic_prices, APIObject)
    self.assertEqual(historic_prices, mock_item)

  @mock_response(hp.GET, '/v2/time', mock_item)
  def test_get_time(self):
    client = Client(api_key, api_secret)
    server_time = client.get_time()
    self.assertIsInstance(server_time, APIObject)
    self.assertEqual(server_time, mock_item)

  @mock_response(hp.GET, '/v2/users/foo', mock_item)
  def test_get_user(self):
    client = Client(api_key, api_secret)
    user = client.get_user('foo')
    self.assertIsInstance(user, User)
    self.assertEqual(user, mock_item)

  @mock_response(hp.GET, '/v2/user', mock_item)
  def test_get_current_user(self):
    client = Client(api_key, api_secret)
    user = client.get_current_user()
    self.assertIsInstance(user, CurrentUser)
    self.assertEqual(user, mock_item)

  @mock_response(hp.GET, '/v2/user/auth', mock_item)
  def test_get_auth_info(self):
    client = Client(api_key, api_secret)
    info = client.get_auth_info()
    self.assertIsInstance(info, APIObject)
    self.assertEqual(info, mock_item)

  @mock_response(hp.PUT, '/v2/user', mock_item)
  def test_update_current_user(self):
    client = Client(api_key, api_secret)
    user = client.update_current_user(name='New Name')
    self.assertIsInstance(user, CurrentUser)
    self.assertEqual(user, mock_item)

  @mock_response(hp.GET, '/v2/accounts', mock_collection)
  def test_get_accounts(self):
    client = Client(api_key, api_secret)
    accounts = client.get_accounts()
    self.assertIsInstance(accounts, APIObject)
    self.assertEqual(accounts.data, mock_collection)
    for account in accounts.data:
      self.assertIsInstance(account, Account)

  @mock_response(hp.GET, '/v2/accounts/foo', mock_item)
  def test_get_account(self):
    client = Client(api_key, api_secret)
    account = client.get_account('foo')
    self.assertIsInstance(account, Account)
    self.assertEqual(account, mock_item)

  @mock_response(hp.GET, '/v2/accounts/primary', mock_item)
  def test_get_primary_account(self):
    client = Client(api_key, api_secret)
    account = client.get_primary_account()
    self.assertIsInstance(account, Account)
    self.assertEqual(account, mock_item)

  @mock_response(hp.POST, '/v2/accounts', mock_item)
  def test_create_account(self):
    client = Client(api_key, api_secret)
    account = client.create_account()
    self.assertIsInstance(account, Account)
    self.assertEqual(account, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/primary', mock_item)
  def test_set_primary_account(self):
    client = Client(api_key, api_secret)
    account = client.set_primary_account('foo')
    self.assertIsInstance(account, Account)
    self.assertEqual(account, mock_item)

  @mock_response(hp.PUT, '/v2/accounts/foo', mock_item)
  def test_update_account(self):
    client = Client(api_key, api_secret)
    account = client.update_account('foo', name='New Account Name')
    self.assertIsInstance(account, Account)
    self.assertEqual(account, mock_item)

  @mock_response(hp.DELETE, '/v2/accounts/foo', None)
  def test_delete_account(self):
    client = Client(api_key, api_secret)
    account = client.delete_account('foo')
    self.assertIs(account, None)

  @mock_response(hp.GET, '/v2/accounts/foo/addresses', mock_collection)
  def test_get_addresses(self):
    client = Client(api_key, api_secret)
    addresses = client.get_addresses('foo')
    self.assertIsInstance(addresses, APIObject)
    self.assertEqual(addresses.data, mock_collection)
    for address in addresses.data:
      self.assertIsInstance(address, Address)

  @mock_response(hp.GET, '/v2/accounts/foo/addresses/bar', mock_item)
  def test_get_address(self):
    client = Client(api_key, api_secret)
    address = client.get_address('foo', 'bar')
    self.assertIsInstance(address, Address)
    self.assertEqual(address, mock_item)

  @mock_response(hp.GET, '/v2/accounts/foo/addresses/bar/transactions', mock_collection)
  def test_get_address_transactions(self):
    client = Client(api_key, api_secret)
    transactions = client.get_address_transactions('foo', 'bar')
    self.assertIsInstance(transactions, APIObject)
    self.assertEqual(transactions.data, mock_collection)
    for transaction in transactions.data:
      self.assertIsInstance(transaction, Transaction)

  @mock_response(hp.POST, '/v2/accounts/foo/addresses', mock_item)
  def test_create_address(self):
    client = Client(api_key, api_secret)
    address = client.create_address('foo')
    self.assertIsInstance(address, Address)
    self.assertEqual(address, mock_item)

  @mock_response(hp.GET, '/v2/accounts/foo/transactions', mock_collection)
  def test_get_transactions(self):
    client = Client(api_key, api_secret)
    transactions = client.get_transactions('foo')
    self.assertIsInstance(transactions, APIObject)
    self.assertEqual(transactions.data, mock_collection)
    for transaction in transactions.data:
      self.assertIsInstance(transaction, Transaction)

  @mock_response(hp.GET, '/v2/accounts/foo/transactions/bar', mock_item)
  def test_get_transaction(self):
    client = Client(api_key, api_secret)
    transaction = client.get_transaction('foo', 'bar')
    self.assertIsInstance(transaction, Transaction)
    self.assertEqual(transaction, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/transactions', mock_item)
  def test_send_money(self):
    client = Client(api_key, api_secret)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'to': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        transaction = client.send_money('foo', **send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    transaction = client.send_money('foo', **send_kwargs)
    self.assertIsInstance(transaction, Transaction)
    self.assertEqual(transaction, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/transactions', mock_item)
  def test_transfer_money(self):
    client = Client(api_key, api_secret)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'to': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        transaction = client.transfer_money('foo', **send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    transaction = client.transfer_money('foo', **send_kwargs)
    self.assertIsInstance(transaction, Transaction)
    self.assertEqual(transaction, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/transactions', mock_item)
  def test_request_money(self):
    client = Client(api_key, api_secret)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'to': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        transaction = client.request_money('foo', **send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    transaction = client.request_money('foo', **send_kwargs)
    self.assertIsInstance(transaction, Transaction)
    self.assertEqual(transaction, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/transactions/bar/complete', mock_item)
  def test_complete_request(self):
    client = Client(api_key, api_secret)
    response = client.complete_request('foo', 'bar')
    self.assertIsInstance(response, APIObject)
    self.assertEqual(response, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/transactions/bar/resend', mock_item)
  def test_resend_request(self):
    client = Client(api_key, api_secret)
    response = client.resend_request('foo', 'bar')
    self.assertIsInstance(response, APIObject)
    self.assertEqual(response, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/transactions/bar/cancel', mock_item)
  def test_cancel_request(self):
    client = Client(api_key, api_secret)
    response = client.cancel_request('foo', 'bar')
    self.assertIsInstance(response, APIObject)
    self.assertEqual(response, mock_item)

  @mock_response(hp.GET, '/v2/reports', mock_collection)
  def test_get_reports(self):
    client = Client(api_key, api_secret)
    reports = client.get_reports()
    self.assertIsInstance(reports, APIObject)
    self.assertEqual(reports.data, mock_collection)
    for report in reports.data:
      self.assertIsInstance(report, Report)

  @mock_response(hp.GET, '/v2/reports/testreportid', mock_item)
  def test_get_report(self):
    client = Client(api_key, api_secret)
    report = client.get_report('testreportid')
    self.assertIsInstance(report, Report)
    self.assertEqual(report, mock_item)

  @mock_response(hp.POST, '/v2/reports', mock_item)
  def test_create_report(self):
    client = Client(api_key, api_secret)
    report = client.create_report(
      email='example@coinbase.com', type='transactions'
    )
    self.assertIsInstance(report, APIObject)
    self.assertIsInstance(report, Report)
    self.assertEqual(report, mock_item)

  @mock_response(hp.GET, '/v2/accounts/foo/buys', mock_collection)
  def test_get_buys(self):
    client = Client(api_key, api_secret)
    buys = client.get_buys('foo')
    self.assertIsInstance(buys, APIObject)
    self.assertEqual(buys.data, mock_collection)
    for buy in buys.data:
      self.assertIsInstance(buy, Buy)

  @mock_response(hp.GET, '/v2/accounts/foo/buys/bar', mock_item)
  def test_get_buy(self):
    client = Client(api_key, api_secret)
    buy = client.get_buy('foo', 'bar')
    self.assertIsInstance(buy, Buy)
    self.assertEqual(buy, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/buys', mock_item)
  def test_buy(self):
    client = Client(api_key, api_secret)
    with self.assertRaises(ValueError):
      client.buy('foo')
    for valid_kwargs in [{'amount': '1.0'}, {'total': '1.0'}]:
      buy = client.buy('foo', **valid_kwargs)
      self.assertIsInstance(buy, Buy)
      self.assertEqual(buy, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/buys/bar/commit', mock_item)
  def test_commit_buy(self):
    client = Client(api_key, api_secret)
    buy = client.commit_buy('foo', 'bar')
    self.assertIsInstance(buy, Buy)
    self.assertEqual(buy, mock_item)

  @mock_response(hp.GET, '/v2/accounts/foo/sells', mock_collection)
  def test_get_sells(self):
    client = Client(api_key, api_secret)
    sells = client.get_sells('foo')
    self.assertIsInstance(sells, APIObject)
    self.assertEqual(sells.data, mock_collection)
    for sell in sells.data:
      self.assertIsInstance(sell, Sell)

  @mock_response(hp.GET, '/v2/accounts/foo/sells/bar', mock_item)
  def test_get_sell(self):
    client = Client(api_key, api_secret)
    sell = client.get_sell('foo', 'bar')
    self.assertIsInstance(sell, Sell)
    self.assertEqual(sell, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/sells', mock_item)
  def test_sell(self):
    client = Client(api_key, api_secret)
    with self.assertRaises(ValueError):
      client.sell('foo')
    for valid_kwargs in [{'amount': '1.0'}, {'total': '1.0'}]:
      sell = client.sell('foo', **valid_kwargs)
      self.assertIsInstance(sell, Sell)
      self.assertEqual(sell, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/sells/bar/commit', mock_item)
  def test_commit_sell(self):
    client = Client(api_key, api_secret)
    sell = client.commit_sell('foo', 'bar')
    self.assertIsInstance(sell, Sell)
    self.assertEqual(sell, mock_item)

  @mock_response(hp.GET, '/v2/accounts/foo/deposits', mock_collection)
  def test_get_deposits(self):
    client = Client(api_key, api_secret)
    deposits = client.get_deposits('foo')
    self.assertIsInstance(deposits, APIObject)
    self.assertEqual(deposits.data, mock_collection)
    for deposit in deposits.data:
      self.assertIsInstance(deposit, Deposit)

  @mock_response(hp.GET, '/v2/accounts/foo/deposits/bar', mock_item)
  def test_get_deposit(self):
    client = Client(api_key, api_secret)
    deposit = client.get_deposit('foo', 'bar')
    self.assertIsInstance(deposit, Deposit)
    self.assertEqual(deposit, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/deposits', mock_item)
  def test_deposit(self):
    client = Client(api_key, api_secret)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'payment_method': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        client.deposit('foo', **send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    deposit = client.deposit('foo', **send_kwargs)
    self.assertIsInstance(deposit, Deposit)
    self.assertEqual(deposit, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/deposits/bar/commit', mock_item)
  def test_commit_deposit(self):
    client = Client(api_key, api_secret)
    deposit = client.commit_deposit('foo', 'bar')
    self.assertIsInstance(deposit, Deposit)
    self.assertEqual(deposit, mock_item)

  @mock_response(hp.GET, '/v2/accounts/foo/withdrawals', mock_collection)
  def test_get_withdrawals(self):
    client = Client(api_key, api_secret)
    withdrawals = client.get_withdrawals('foo')
    self.assertIsInstance(withdrawals, APIObject)
    self.assertEqual(withdrawals.data, mock_collection)
    for withdrawal in withdrawals.data:
      self.assertIsInstance(withdrawal, Withdrawal)

  @mock_response(hp.GET, '/v2/accounts/foo/withdrawals/bar', mock_item)
  def test_get_withdrawal(self):
    client = Client(api_key, api_secret)
    withdrawal = client.get_withdrawal('foo', 'bar')
    self.assertIsInstance(withdrawal, Withdrawal)
    self.assertEqual(withdrawal, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/withdrawals', mock_item)
  def test_withdraw(self):
    client = Client(api_key, api_secret)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'payment_method': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        client.withdraw('foo', **send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    withdrawal = client.withdraw('foo', **send_kwargs)
    self.assertIsInstance(withdrawal, Withdrawal)
    self.assertEqual(withdrawal, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/withdrawals/bar/commit', mock_item)
  def test_commit_withdrawal(self):
    client = Client(api_key, api_secret)
    withdrawal = client.commit_withdrawal('foo', 'bar')
    self.assertIsInstance(withdrawal, Withdrawal)
    self.assertEqual(withdrawal, mock_item)

  @mock_response(hp.GET, '/v2/payment-methods', mock_collection)
  def test_get_payment_methods(self):
    client = Client(api_key, api_secret)
    payment_methods = client.get_payment_methods()
    self.assertIsInstance(payment_methods, APIObject)
    self.assertEqual(payment_methods.data, mock_collection)
    for payment_method in payment_methods.data:
      self.assertIsInstance(payment_method, PaymentMethod)

  @mock_response(hp.GET, '/v2/payment-methods/foo', mock_item)
  def test_get_payment_method(self):
    client = Client(api_key, api_secret)
    payment_method = client.get_payment_method('foo')
    self.assertIsInstance(payment_method, PaymentMethod)
    self.assertEqual(payment_method, mock_item)

  @mock_response(hp.GET, '/v2/merchants/foo', mock_item)
  def test_get_merchant(self):
    client = Client(api_key, api_secret)
    merchant = client.get_merchant('foo')
    self.assertIsInstance(merchant, Merchant)
    self.assertEqual(merchant, mock_item)

  @mock_response(hp.GET, '/v2/orders', mock_collection)
  def test_get_orders(self):
    client = Client(api_key, api_secret)
    orders = client.get_orders()
    self.assertIsInstance(orders, APIObject)
    self.assertEqual(orders.data, mock_collection)
    for order in orders.data:
      self.assertIsInstance(order, Order)

  @mock_response(hp.GET, '/v2/orders/foo', mock_item)
  def test_get_order(self):
    client = Client(api_key, api_secret)
    order = client.get_order('foo')
    self.assertIsInstance(order, Order)
    self.assertEqual(order, mock_item)

  @mock_response(hp.POST, '/v2/orders', mock_item)
  def test_create_order(self):
    client = Client(api_key, api_secret)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'name': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        client.create_order(**send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    order = client.create_order(**send_kwargs)
    self.assertIsInstance(order, Order)
    self.assertEqual(order, mock_item)

  @mock_response(hp.POST, '/v2/orders/foo/refund', mock_item)
  def test_refund_order(self):
    client = Client(api_key, api_secret)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        client.refund_order('foo', **send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    order = client.refund_order('foo', **send_kwargs)
    self.assertIsInstance(order, Order)
    self.assertEqual(order, mock_item)

  @mock_response(hp.GET, '/v2/checkouts', mock_collection)
  def test_get_checkouts(self):
    client = Client(api_key, api_secret)
    checkouts = client.get_checkouts()
    self.assertIsInstance(checkouts, APIObject)
    self.assertEqual(checkouts.data, mock_collection)
    for checkout in checkouts.data:
      self.assertIsInstance(checkout, Checkout)

  @mock_response(hp.GET, '/v2/checkouts/foo', mock_item)
  def test_get_checkout(self):
    client = Client(api_key, api_secret)
    checkout = client.get_checkout('foo')
    self.assertIsInstance(checkout, Checkout)
    self.assertEqual(checkout, mock_item)

  @mock_response(hp.POST, '/v2/checkouts', mock_item)
  def test_create_checkout(self):
    client = Client(api_key, api_secret)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'name': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        client.create_checkout(**send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    checkout = client.create_checkout(**send_kwargs)
    self.assertIsInstance(checkout, Checkout)
    self.assertEqual(checkout, mock_item)

  @mock_response(hp.GET, '/v2/checkouts/foo/orders', mock_collection)
  def test_get_checkout_orders(self):
    client = Client(api_key, api_secret)
    orders = client.get_checkout_orders('foo')
    self.assertIsInstance(orders, APIObject)
    self.assertEqual(orders.data, mock_collection)
    for order in orders.data:
      self.assertIsInstance(order, Order)

  @mock_response(hp.POST, '/v2/checkouts/foo/orders', mock_item)
  def test_create_checkout_order(self):
    client = Client(api_key, api_secret)
    order = client.create_checkout_order('foo')
    self.assertIsInstance(order, Order)
    self.assertEqual(order, mock_item)

  def test_callback_verification(self):
    client = Client(api_key, api_secret)
    signature = "6yQRl17CNj5YSHSpF+tLjb0vVsNVEv021Tyy1bTVEQ69SWlmhwmJYuMc7jiDyeW9TLy4vRqSh4g4YEyN8eoQIM57pMoNw6Lw6Oudubqwp+E3cKtLFxW0l18db3Z/vhxn5BScAutHWwT/XrmkCNaHyCsvOOGMekwrNO7mxX9QIx21FBaEejJeviSYrF8bG6MbmFEs2VGKSybf9YrElR8BxxNe/uNfCXN3P5tO8MgR5wlL3Kr4yq8e6i4WWJgD08IVTnrSnoZR6v8JkPA+fn7I0M6cy0Xzw3BRMJAvdQB97wkobu97gFqJFKsOH2u/JR1S/UNP26vL0mzuAVuKAUwlRn0SUhWEAgcM3X0UCtWLYfCIb5QqrSHwlp7lwOkVnFt329Mrpjy+jAfYYSRqzIsw4ZsRRVauy/v3CvmjPI9sUKiJ5l1FSgkpK2lkjhFgKB3WaYZWy9ZfIAI9bDyG8vSTT7IDurlUhyTweDqVNlYUsO6jaUa4KmSpg1o9eIeHxm0XBQ2c0Lv/T39KNc/VOAi1LBfPiQYMXD1e/8VuPPBTDGgzOMD3i334ppSr36+8YtApAn3D36Hr9jqAfFrugM7uPecjCGuleWsHFyNnJErT0/amIt24Nh1GoiESEq42o7Co4wZieKZ+/yeAlIUErJzK41ACVGmTnGoDUwEBXxADOdA="
    body = '{"order":{"id":null,"created_at":null,"status":"completed","event":null,"total_btc":{"cents":100000000,"currency_iso":"BTC"},"total_native":{"cents":1000,"currency_iso":"USD"},"total_payout":{"cents":1000,"currency_iso":"USD"},"custom":"123456789","receive_address":"mzVoQenSY6RTBgBUcpSBTBAvUMNgGWxgJn","button":{"type":"buy_now","name":"Test Item","description":null,"id":null},"transaction":{"id":"53bdfe4d091c0d74a7000003","hash":"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b","confirmations":0}}}'.encode('utf-8')
    self.assertTrue(client.verify_callback(body, signature))

  def test_callback_verification_failure(self):
    client = Client(api_key, api_secret)
    signature = "6yQRl17CNj5YSHSpF+tLjb0vVsNVEv021Tyy1bTVEQ69SWlmhwmJYuMc7jiDyeW9TLy4vRqSh4g4YEyN8eoQIM57pMoNw6Lw6Oudubqwp+E3cKtLFxW0l18db3Z/vhxn5BScAutHWwT/XrmkCNaHyCsvOOGMekwrNO7mxX9QIx21FBaEejJeviSYrF8bG6MbmFEs2VGKSybf9YrElR8BxxNe/uNfCXN3P5tO8MgR5wlL3Kr4yq8e6i4WWJgD08IVTnrSnoZR6v8JkPA+fn7I0M6cy0Xzw3BRMJAvdQB97wkobu97gFqJFKsOH2u/JR1S/UNP26vL0mzuAVuKAUwlRn0SUhWEAgcM3X0UCtWLYfCIb5QqrSHwlp7lwOkVnFt329Mrpjy+jAfYYSRqzIsw4ZsRRVauy/v3CvmjPI9sUKiJ5l1FSgkpK2lkjhFgKB3WaYZWy9ZfIAI9bDyG8vSTT7IDurlUhyTweDqVNlYUsO6jaUa4KmSpg1o9eIeHxm0XBQ2c0Lv/T39KNc/VOAi1LBfPiQYMXD1e/8VuPPBTDGgzOMD3i334ppSr36+8YtApAn3D36Hr9jqAfFrugM7uPecjCGuleWsHFyNnJErT0/amIt24Nh1GoiESEq42o7Co4wZieKZ+/yeAlIUErJzK41ACVGmTnGoDUwEBXxADOdA="
    body = '{"order":{"id":null,"created_at":null,"status":"completed","event":null,"total_btc":{"cents":1000000000,"currency_iso":"BTC"},"total_native":{"cents":1000,"currency_iso":"USD"},"total_payout":{"cents":1000,"currency_iso":"USD"},"custom":"123456789","receive_address":"mzVoQenSY6RTBgBUcpSBTBAvUMNgGWxgJn","button":{"type":"buy_now","name":"Test Item","description":null,"id":null},"transaction":{"id":"53bdfe4d091c0d74a7000003","hash":"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b","confirmations":0}}}'.encode('utf-8')
    self.assertFalse(client.verify_callback(body, signature))

class TestOauthClient(unittest2.TestCase):
  def test_oauth_details_required(self):
    with self.assertRaises(ValueError):
      OAuthClient(None, refresh_token)
    with self.assertRaises(ValueError):
      OAuthClient(access_token, None)
    client = OAuthClient(access_token, refresh_token)

  @hp.activate
  def test_refresh(self):
    # Requests to the default BASE_API_URI will noticeably fail by raising an
    # AssertionError. Requests to the new URL will respond HTTP 200.
    new_api_base = 'http://example.com/'

    # If any error is raised by the server, the test suite will never exit when
    # using Python 3. This strange technique is used to raise the errors
    # outside of the mocked server environment.
    errors_in_server = []

    server_response_data = {
        'access_token': 'newaccesstoken',
        'refresh_token': 'newrefreshtoken',
      }
    def server_response(request, uri, headers):
      parsed_uri = urlparse(uri)
      parsed_reference = urlparse(new_api_base)
      try:
        self.assertEqual(parsed_uri.scheme, parsed_reference.scheme)
        self.assertEqual(parsed_uri.netloc, parsed_reference.netloc)
        self.assertEqual(parsed_uri.path, parsed_reference.path)
      except AssertionError as e:
        errors_in_server.append(e)
      return (200, headers, json.dumps(server_response_data))
    hp.register_uri(hp.POST, OAuthClient.BASE_API_URI + 'oauth/token', body=server_response)
    hp.register_uri(hp.POST, new_api_base + 'oauth/token', body=server_response)

    client = OAuthClient(access_token, refresh_token)
    with self.assertRaises(AssertionError):
      client.refresh()
      if errors_in_server: raise errors_in_server.pop()

    client2 = OAuthClient(
        access_token,
        refresh_token,
        base_api_uri=new_api_base)
    self.assertEqual(client2.refresh(), server_response_data)

    # If the response does not include both an access token and refresh token,
    # an exception will be raised.
    server_response_data = {'access_token': 'someaccesstoken'}
    with self.assertRaises(APIError):
      client2.refresh()
    server_response_data = {'refresh_token': 'somerefreshtoken'}
    with self.assertRaises(APIError):
      client2.refresh()

  @mock_response(hp.POST, '/oauth/revoke', mock_item)
  def test_revoke(self):
    client = OAuthClient(access_token, refresh_token)
    response = client.revoke()
    self.assertIs(response, None)

  @hp.activate
  def test_response_handling(self):
    resp200 = lambda r, u, h: (200, h, '{}')
    resp400 = lambda r, u, h: (400, h, '{}')
    header_template = (
        'Bearer realm="Doorkeeper" error="{error}" error_description="{message}"')
    def resp401_revoked(request, uri, headers):
      error_data = {
          'error': 'revoked_token',
          'message': 'The access token has been revoked',
        }
      headers.update({'www-authenticate': header_template.format(**error_data)})
      return (401, headers, json.dumps(error_data))
    def resp401_expired(request, uri, headers):
      error_data = {
          'error': 'expired_token',
          'message': 'The access token expired',
        }
      headers.update({'www-authenticate': header_template.format(**error_data)})
      return (401, headers, json.dumps(error_data))
    def resp401_invalid(request, uri, headers):
      error_data = {
          'error': 'invalid_token',
          'message': 'The access token is invalid',
        }
      headers.update({'www-authenticate': header_template.format(**error_data)})
      return (401, headers, json.dumps(error_data))
    def resp401_generic(request, uri, headers):
      error_data = {
          'error': 'some_error',
          'message': 'Some description',
        }
      headers.update({'www-authenticate': header_template.format(**error_data)})
      return (401, headers, json.dumps(error_data))
    def resp401_nobody(request, uri, headers):
      return (401, headers, '{}')
    resp402 = lambda r, u, h: (402, h, '{}')

    hp.register_uri(hp.GET, re.compile('.*200$'), resp200)
    hp.register_uri(hp.GET, re.compile('.*400$'), resp400)
    hp.register_uri(hp.GET, re.compile('.*401_expired$'), resp401_expired)
    hp.register_uri(hp.GET, re.compile('.*401_revoked$'), resp401_revoked)
    hp.register_uri(hp.GET, re.compile('.*401_invalid$'), resp401_invalid)
    hp.register_uri(hp.GET, re.compile('.*401_generic$'), resp401_generic)
    hp.register_uri(hp.GET, re.compile('.*401_nobody$'), resp401_nobody)
    hp.register_uri(hp.GET, re.compile('.*402$'), resp402)

    client = OAuthClient(access_token, refresh_token)
    self.assertEqual(client._get('200').status_code, 200)
    with self.assertRaises(APIError):
      client._get('400')
    with self.assertRaises(AuthenticationError):
      client._get('401_generic')
    with self.assertRaises(InvalidTokenError):
      client._get('401_invalid')
    with self.assertRaises(ExpiredTokenError):
      client._get('401_expired')
    with self.assertRaises(RevokedTokenError):
      client._get('401_revoked')
    with self.assertRaises(AuthenticationError):
      client._get('401_nobody')
    with self.assertRaises(TwoFactorRequiredError):
      client._get('402')

