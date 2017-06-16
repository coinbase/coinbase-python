# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import six
import unittest2
import warnings

import httpretty as hp

from coinbase.wallet.client import Client
from coinbase.wallet.model import APIObject
from coinbase.wallet.model import new_api_object
from coinbase.wallet.model import Account
from coinbase.wallet.model import Sell
from coinbase.wallet.model import CurrentUser
from coinbase.wallet.model import Deposit
from coinbase.wallet.model import Checkout
from coinbase.wallet.model import Order
from coinbase.wallet.model import Withdrawal
from coinbase.wallet.model import Buy
from coinbase.wallet.model import Address
from coinbase.wallet.model import Transaction
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
mock_item_updated = {
    'key1': 'val1-modified',
    'key2': 'val2-modified',
    'key3': 'newkey',
  }
mock_collection = [mock_item, mock_item]


class TestAPIObject(unittest2.TestCase):
  @mock_response(hp.GET, '/resource/foo', mock_item_updated)
  def test_refresh(self):
    client = Client(api_key, api_secret)
    obj = new_api_object(client, mock_item, APIObject)
    self.assertEqual(obj, mock_item)
    # Missing resource_path key results in ValueError
    with self.assertRaises(ValueError):
      obj.refresh()
    obj.resource_path = '/resource/foo'
    updated = obj.refresh()
    self.assertEqual(updated, mock_item_updated)
    # The updated version is returned, as well as being used to update the
    # object making the refresh()
    for key, value in six.iteritems(mock_item_updated):
      self.assertEqual(obj[key], value)
    # Keys not present originally will not be removed
    self.assertEqual(obj.resource_path, '/resource/foo')

  def test_dot_notation(self):
    client = Client(api_key, api_secret)
    obj = new_api_object(client, mock_item, APIObject)
    with self.assertRaises(AttributeError):
        obj.foo

mock_account = {
    'id': 'foo',
    'resource_path': '/v2/accounts/foo',
  }
mock_account_updated = {
    'id': 'foo',
    'resource_path': '/v2/accounts/foo',
    'newkey': 'present',
  }
class TestAccount(unittest2.TestCase):
  @mock_response(hp.POST, '/v2/accounts/foo/primary', mock_account_updated)
  def test_set_primary(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    data = account.set_primary()
    self.assertEqual(data, mock_account_updated)
    for key, value in six.iteritems(mock_account_updated):
      self.assertEqual(account[key], value)

  @mock_response(hp.PUT, '/v2/accounts/foo', mock_account_updated)
  def test_modify(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    data = account.modify(name='New Account Name')
    self.assertEqual(data, mock_account_updated)
    for key, value in six.iteritems(mock_account_updated):
      self.assertEqual(account[key], value)

  @mock_response(hp.DELETE, '/v2/accounts/foo', None)
  def test_delete(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    data = account.delete()
    self.assertIs(data, None)

  @mock_response(hp.GET, '/v2/accounts/foo/addresses', mock_collection)
  def test_get_addresses(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    addresses = account.get_addresses()
    self.assertIsInstance(addresses, APIObject)
    self.assertEqual(addresses.data, mock_collection)
    for address in addresses.data:
      self.assertIsInstance(address, Address)

  @mock_response(hp.GET, '/v2/accounts/foo/addresses/bar', mock_item)
  def test_get_address(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    address = account.get_address('bar')
    self.assertIsInstance(address, Address)
    self.assertEqual(address, mock_item)
    pass

  @mock_response(hp.GET, '/v2/accounts/foo/addresses/bar/transactions', mock_collection)
  def test_get_address_transactions(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    transactions = account.get_address_transactions('bar')
    self.assertIsInstance(transactions, APIObject)
    self.assertEqual(transactions.data, mock_collection)
    for transaction in transactions.data:
      self.assertIsInstance(transaction, Transaction)

  @mock_response(hp.POST, '/v2/accounts/foo/addresses', mock_item)
  def test_create_address(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    address = account.create_address()
    self.assertIsInstance(address, Address)
    self.assertEqual(address, mock_item)

  @mock_response(hp.GET, '/v2/accounts/foo/transactions', mock_collection)
  def test_get_transactions(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    transactions = account.get_transactions()
    self.assertIsInstance(transactions, APIObject)
    self.assertEqual(transactions.data, mock_collection)
    for transaction in transactions.data:
      self.assertIsInstance(transaction, Transaction)

  @mock_response(hp.GET, '/v2/accounts/foo/transactions/bar', mock_item)
  def test_get_transaction(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    transaction = account.get_transaction('bar')
    self.assertIsInstance(transaction, Transaction)
    self.assertEqual(transaction, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/transactions', mock_item)
  def test_send_money(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'to': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        transaction = account.send_money(**send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    transaction = account.send_money(**send_kwargs)
    self.assertIsInstance(transaction, Transaction)
    self.assertEqual(transaction, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/transactions', mock_item)
  def test_transfer_money(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'to': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        transaction = account.transfer_money(**send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    transaction = account.transfer_money(**send_kwargs)
    self.assertIsInstance(transaction, Transaction)
    self.assertEqual(transaction, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/transactions', mock_item)
  def test_request_money(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'to': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        transaction = account.request_money(**send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    transaction = account.request_money(**send_kwargs)
    self.assertIsInstance(transaction, Transaction)
    self.assertEqual(transaction, mock_item)

  @mock_response(hp.GET, '/v2/reports', mock_collection)
  def test_get_reports(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    reports = account.get_reports()
    self.assertIsInstance(reports, APIObject)
    self.assertEqual(reports.data, mock_collection)
    for report in reports.data:
      self.assertIsInstance(report, Report)

  @mock_response(hp.GET, '/v2/reports/testreportid', mock_item)
  def test_get_report(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    report = account.get_report('testreportid')
    self.assertIsInstance(report, Report)
    self.assertEqual(report, mock_item)

  @mock_response(hp.POST, '/v2/reports', mock_item)
  def test_create_report(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    report = account.create_report(
      type='transactions', email='example@coinbase.com'
    )
    self.assertIsInstance(report, APIObject)
    self.assertIsInstance(report, Report)
    self.assertEqual(report, mock_item)

  @mock_response(hp.GET, '/v2/accounts/foo/buys', mock_collection)
  def test_get_buys(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    buys = account.get_buys()
    self.assertIsInstance(buys, APIObject)
    self.assertEqual(buys.data, mock_collection)
    for buy in buys.data:
      self.assertIsInstance(buy, Buy)

  @mock_response(hp.GET, '/v2/accounts/foo/buys/bar', mock_item)
  def test_get_buy(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    buy = account.get_buy('bar')
    self.assertIsInstance(buy, Buy)
    self.assertEqual(buy, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/buys', mock_item)
  def test_buy(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    with self.assertRaises(ValueError):
      account.buy()
    for valid_kwargs in [{'amount': '1.0'}, {'total': '1.0'}]:
      buy = account.buy(**valid_kwargs)
      self.assertIsInstance(buy, Buy)
      self.assertEqual(buy, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/buys/bar/commit', mock_item)
  def test_commit_buy(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    buy = account.commit_buy('bar')
    self.assertIsInstance(buy, Buy)
    self.assertEqual(buy, mock_item)

  @mock_response(hp.GET, '/v2/accounts/foo/sells', mock_collection)
  def test_get_sells(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    sells = account.get_sells()
    self.assertIsInstance(sells, APIObject)
    self.assertEqual(sells.data, mock_collection)
    for sell in sells.data:
      self.assertIsInstance(sell, Sell)

  @mock_response(hp.GET, '/v2/accounts/foo/sells/bar', mock_item)
  def test_get_sell(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    sell = account.get_sell('bar')
    self.assertIsInstance(sell, Sell)
    self.assertEqual(sell, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/sells', mock_item)
  def test_sell(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    with self.assertRaises(ValueError):
      account.sell()
    for valid_kwargs in [{'amount': '1.0'}, {'total': '1.0'}]:
      sell = account.sell(**valid_kwargs)
      self.assertIsInstance(sell, Sell)
      self.assertEqual(sell, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/sells/bar/commit', mock_item)
  def test_commit_sell(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    sell = account.commit_sell('bar')
    self.assertIsInstance(sell, Sell)
    self.assertEqual(sell, mock_item)

  @mock_response(hp.GET, '/v2/accounts/foo/deposits', mock_collection)
  def test_get_deposits(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    deposits = account.get_deposits()
    self.assertIsInstance(deposits, APIObject)
    self.assertEqual(deposits.data, mock_collection)
    for deposit in deposits.data:
      self.assertIsInstance(deposit, Deposit)

  @mock_response(hp.GET, '/v2/accounts/foo/deposits/bar', mock_item)
  def test_get_deposit(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    deposit = account.get_deposit('bar')
    self.assertIsInstance(deposit, Deposit)
    self.assertEqual(deposit, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/deposits', mock_item)
  def test_deposit(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'payment_method': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        account.deposit(**send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    deposit = account.deposit(**send_kwargs)
    self.assertIsInstance(deposit, Deposit)
    self.assertEqual(deposit, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/deposits/bar/commit', mock_item)
  def test_commit_deposit(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    deposit = account.commit_deposit('bar')
    self.assertIsInstance(deposit, Deposit)
    self.assertEqual(deposit, mock_item)

  @mock_response(hp.GET, '/v2/accounts/foo/withdrawals', mock_collection)
  def test_get_withdrawals(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    withdrawals = account.get_withdrawals()
    self.assertIsInstance(withdrawals, APIObject)
    self.assertEqual(withdrawals.data, mock_collection)
    for withdrawal in withdrawals.data:
      self.assertIsInstance(withdrawal, Withdrawal)

  @mock_response(hp.GET, '/v2/accounts/foo/withdrawals/bar', mock_item)
  def test_get_withdrawal(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    withdrawal = account.get_withdrawal('bar')
    self.assertIsInstance(withdrawal, Withdrawal)
    self.assertEqual(withdrawal, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/withdrawals', mock_item)
  def test_withdraw(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'payment_method': 'bar', 'amount': '1.0', 'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        account.withdraw(**send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    withdrawal = account.withdraw(**send_kwargs)
    self.assertIsInstance(withdrawal, Withdrawal)
    self.assertEqual(withdrawal, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/withdrawals/bar/commit', mock_item)
  def test_commit_withdrawal(self):
    client = Client(api_key, api_secret)
    account = new_api_object(client, mock_account, Account)
    withdrawal = account.commit_withdrawal('bar')
    self.assertIsInstance(withdrawal, Withdrawal)
    self.assertEqual(withdrawal, mock_item)



mock_checkout = {
    'id': 'foo',
    'resource_path': '/v2/checkouts/foo',
  }
class TestCheckout(unittest2.TestCase):
  @mock_response(hp.GET, '/v2/checkouts/foo/orders', mock_collection)
  def test_get_orders(self):
    client = Client(api_key, api_secret)
    checkout = new_api_object(client, mock_checkout, Checkout)
    orders = checkout.get_orders()
    self.assertIsInstance(orders, APIObject)
    self.assertEqual(orders.data, mock_collection)
    for order in orders.data:
      self.assertIsInstance(order, Order)

  @mock_response(hp.POST, '/v2/checkouts/foo/orders', mock_item)
  def test_create_order(self):
    client = Client(api_key, api_secret)
    checkout = new_api_object(client, mock_checkout, Checkout)
    order = checkout.create_order()
    self.assertIsInstance(order, Order)
    self.assertEqual(order, mock_item)


mock_order = {
    'id': 'foo',
    'resource_path': '/v2/orders/foo',
  }
class TestOrder(unittest2.TestCase):
  @mock_response(hp.POST, '/v2/orders/foo/refund', mock_item)
  def test_refund(self):
    client = Client(api_key, api_secret)
    order = new_api_object(client, mock_order, Order)
    # Start with none of the required arguments, and slowly make requests with
    # an additional required argument, expecting failure until all arguments
    # are present.
    send_kwargs = {}
    required_kwargs = {'currency': 'USD'}
    while required_kwargs:
      with self.assertRaises(ValueError):
        order.refund(**send_kwargs)
      for key in required_kwargs:
        send_kwargs[key] = required_kwargs.pop(key)
        break
    order = order.refund(**send_kwargs)
    self.assertIsInstance(order, Order)
    self.assertEqual(order, mock_item)


mock_transaction = {
    'id': 'bar',
    'resource_path': '/v2/accounts/foo/transactions/bar',
  }
class TestTransaction(unittest2.TestCase):
  @mock_response(hp.POST, '/v2/accounts/foo/transactions/bar/complete', mock_item)
  def test_complete(self):
    client = Client(api_key, api_secret)
    transaction = new_api_object(client, mock_transaction, Transaction)
    response = transaction.complete()
    self.assertIsInstance(response, APIObject)
    self.assertEqual(response, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/transactions/bar/resend', mock_item)
  def test_resend(self):
    client = Client(api_key, api_secret)
    transaction = new_api_object(client, mock_transaction, Transaction)
    response = transaction.resend()
    self.assertIsInstance(response, APIObject)
    self.assertEqual(response, mock_item)

  @mock_response(hp.POST, '/v2/accounts/foo/transactions/bar/cancel', mock_item)
  def test_cancel(self):
    client = Client(api_key, api_secret)
    transaction = new_api_object(client, mock_transaction, Transaction)
    response = transaction.cancel()
    self.assertIsInstance(response, APIObject)
    self.assertEqual(response, mock_item)


mock_buy = {
    'id': 'bar',
    'resource_path': '/v2/accounts/foo/buys/bar',
  }
mock_buy_updated = {
    'id': 'bar',
    'resource_path': '/v2/accounts/foo/buys/bar',
    'updated': True,
  }
class TestBuy(unittest2.TestCase):
  @mock_response(hp.POST, '/v2/accounts/foo/buys/bar/commit', mock_buy_updated)
  def test_commit(self):
    client = Client(api_key, api_secret)
    buy = new_api_object(client, mock_buy, Buy)
    buy2 = buy.commit()
    self.assertIsInstance(buy2, Buy)
    self.assertEqual(buy2, mock_buy_updated)
    for key, value in six.iteritems(mock_buy_updated):
      self.assertEqual(buy[key], value)


mock_sell = {
    'id': 'bar',
    'resource_path': '/v2/accounts/foo/sells/bar',
  }
mock_sell_updated = {
    'id': 'bar',
    'resource_path': '/v2/accounts/foo/sells/bar',
    'updated': True,
  }

class TestSell(unittest2.TestCase):
  @mock_response(hp.POST, '/v2/accounts/foo/sells/bar/commit', mock_sell_updated)
  def test_commit(self):
    client = Client(api_key, api_secret)
    sell = new_api_object(client, mock_sell, Sell)
    sell2 = sell.commit()
    self.assertIsInstance(sell2, Sell)
    self.assertEqual(sell2, mock_sell_updated)
    for key, value in six.iteritems(mock_sell_updated):
      self.assertEqual(sell[key], value)


mock_deposit = {
    'id': 'bar',
    'resource_path': '/v2/accounts/foo/deposits/bar',
  }
mock_deposit_updated = {
    'id': 'bar',
    'resource_path': '/v2/accounts/foo/deposits/bar',
    'updated': True,
  }
class TestDeposit(unittest2.TestCase):
  @mock_response(hp.POST, '/v2/accounts/foo/deposits/bar/commit', mock_deposit_updated)
  def test_commit(self):
    client = Client(api_key, api_secret)
    deposit = new_api_object(client, mock_deposit, Deposit)
    deposit2 = deposit.commit()
    self.assertIsInstance(deposit2, Deposit)
    self.assertEqual(deposit2, mock_deposit_updated)
    for key, value in six.iteritems(mock_deposit_updated):
      self.assertEqual(deposit[key], value)


mock_withdrawal = {
    'id': 'bar',
    'resource_path': '/v2/accounts/foo/withdrawals/bar',
  }
mock_withdrawal_updated = {
    'id': 'bar',
    'resource_path': '/v2/accounts/foo/withdrawals/bar',
    'updated': True,
  }
class TestWithdrawal(unittest2.TestCase):
  @mock_response(hp.POST, '/v2/accounts/foo/withdrawals/bar/commit', mock_withdrawal_updated)
  def test_commit(self):
    client = Client(api_key, api_secret)
    withdrawal = new_api_object(client, mock_withdrawal, Withdrawal)
    withdrawal2 = withdrawal.commit()
    self.assertIsInstance(withdrawal2, Withdrawal)
    self.assertEqual(withdrawal2, mock_withdrawal_updated)
    for key, value in six.iteritems(mock_withdrawal_updated):
      self.assertEqual(withdrawal[key], value)
    pass


class TestCurrentUser(unittest2.TestCase):
  @mock_response(hp.PUT, '/v2/user', mock_item_updated)
  def test_modify(self):
    client = Client(api_key, api_secret)
    user = new_api_object(client, mock_item, CurrentUser)
    user2 = user.modify(name='New Name')
    self.assertIsInstance(user2, CurrentUser)
    self.assertEqual(user2, mock_item_updated)
    for key, value in six.iteritems(mock_item_updated):
      self.assertEqual(user[key], value)
