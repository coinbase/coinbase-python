# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import six


def new_api_object(client, obj, cls=None, **kwargs):
  if isinstance(obj, dict):
    if not cls:
      resource = obj.get('resource', None)
      cls = _resource_to_model.get(resource, None)
    if not cls:
      obj_keys = set(six.iterkeys(obj))
      for keys, model in six.iteritems(_obj_keys_to_model):
        if keys <= obj_keys:
          cls = model
          break
    cls = cls or APIObject
    result = cls(client, **kwargs)
    for k, v in six.iteritems(obj):
      result[k] = new_api_object(client, v)
    return result
  if isinstance(obj, list):
    return [new_api_object(client, v, cls) for v in obj]
  return obj


class APIObject(dict):
  """Generic class used to represent a JSON response from the Coinbase API.

  If you're a consumer of the API, you shouldn't be using this class directly.
  This exists to make it easier to consume our API by allowing dot-notation
  access to the responses, as well as automatically parsing the responses into
  the appropriate Python models.
  """
  __api_client = None
  __response = None
  __pagination = None
  __warnings = None

  def __init__(self, api_client, response=None, pagination=None, warnings=None):
    self.__api_client = api_client
    self.__response = response
    self.__pagination = pagination
    self.__warnings = warnings

  @property
  def api_client(self):
    return self.__api_client

  @property
  def response(self):
    return self.__response

  @property
  def warnings(self):
    return self.__warnings

  @property
  def pagination(self):
    return self.__pagination

  def refresh(self, **params):
    url = getattr(self, 'resource_path', None)
    if not url:
      raise ValueError("Unable to refresh: missing 'resource_path' attribute.")
    response = self.api_client._get(url, data=params)
    data = self.api_client._make_api_object(response, type(self))
    self.update(data)
    return data

  # The following three method definitions allow dot-notation access to member
  # objects for convenience.
  def __getattr__(self, *args, **kwargs):
    try:
      return dict.__getitem__(self, *args, **kwargs)
    except KeyError as key_error:
      attribute_error = AttributeError(*key_error.args)
      attribute_error.message = getattr(key_error, 'message', '')
      raise attribute_error

  def __delattr__(self, *args, **kwargs):
    try:
      return dict.__delitem__(self, *args, **kwargs)
    except KeyError as key_error:
      attribute_error = AttributeError(*key_error.args)
      attribute_error.message = getattr(key_error, 'message', '')
      raise attribute_error

  def __setattr__(self, key, value):
    # All attributes that start with '_' will not be accessible via item-getter
    # syntax, which means that they won't be included in conversion to a
    # vanilla dict, which means that APIObjects can be treated as equivalent to
    # dicts. This is nice because it allows direct JSON-serialization of any
    # APIObject.
    if key.startswith('_') or key in self.__dict__:
      return dict.__setattr__(self, key, value)
    return dict.__setitem__(self, key, value)

  # When an API response includes multiple items, allow direct accessing that
  # data instead of forcing additional attribute access. This works for
  # slicing and index reference only.
  def __getitem__(self, key):
    data = getattr(self, 'data', None)
    if isinstance(data, list) and isinstance(key, (int, slice)):
      return data[key]
    return dict.__getitem__(self, key)

  def __dir__(self): # pragma: no cover
    # This makes tab completion work in interactive shells like IPython for all
    # attributes, items, and methods.
    return list(self.keys())

  def __str__(self):
    try:
      return json.dumps(self, sort_keys=True, indent=2)
    except TypeError:
      return '(invalid JSON)'

  def __name__(self):
    return '<{} @ {}>'.format(type(self).__name__, hex(id(self))) # pragma: no cover

  def __repr__(self):
    return '{} {}'.format(self.__name__(), str(self)) # pragma: no cover


class Account(APIObject):
  def set_primary(self, **params):
    """https://developers.coinbase.com/api/v2#set-account-as-primary"""
    data = self.api_client.set_primary_account(self.id, **params)
    self.update(data)
    return data

  def modify(self, **params):
    """https://developers.coinbase.com/api#modify-an-account"""
    data = self.api_client.update_account(self.id, **params)
    self.update(data)
    return data

  def delete(self, **params):
    """https://developers.coinbase.com/api#delete-an-account"""
    return self.api_client.delete_account(self.id, **params)

  # Addresses API
  # -----------------------------------------------------------
  def get_addresses(self, **params):
    """https://developers.coinbase.com/api/v2#list-addresses"""
    return self.api_client.get_addresses(self.id, **params)

  def get_address(self, address_id, **params):
    """https://developers.coinbase.com/api/v2#show-addresss"""
    return self.api_client.get_address(self.id, address_id, **params)

  def get_address_transactions(self, address_id, **params):
    """https://developers.coinbase.com/api/v2#list-address39s-transactions"""
    return self.api_client.get_address_transactions(self.id, address_id, **params)

  def create_address(self, **params):
    """https://developers.coinbase.com/api/v2#show-addresss"""
    return self.api_client.create_address(self.id, **params)

  # Transactions API
  # -----------------------------------------------------------
  def get_transactions(self, **params):
    """https://developers.coinbase.com/api/v2#list-transactions"""
    return self.api_client.get_transactions(self.id, **params)

  def get_transaction(self, transaction_id, **params):
    """https://developers.coinbase.com/api/v2#show-a-transaction"""
    return self.api_client.get_transaction(self.id, transaction_id, **params)

  def send_money(self, **params):
    """https://developers.coinbase.com/api/v2#send-money"""
    return self.api_client.send_money(self.id, **params)

  def transfer_money(self, **params):
    """https://developers.coinbase.com/api/v2#transfer-money-between-accounts"""
    return self.api_client.transfer_money(self.id, **params)

  def request_money(self, **params):
    """https://developers.coinbase.com/api/v2#request-money"""
    return self.api_client.request_money(self.id, **params)

  # Reports API
  # -----------------------------------------------------------
  def get_reports(self, **params):
    """https://developers.coinbase.com/api/v2#list-all-reports"""
    return self.api_client.get_reports(**params)

  def get_report(self, report_id, **params):
    """https://developers.coinbase.com/api/v2#show-a-report"""
    return self.api_client.get_report(report_id, **params)

  def create_report(self, **params):
    """https://developers.coinbase.com/api/v2#generate-a-new-report"""
    return self.api_client.create_report(**params)

  # Buys API
  # -----------------------------------------------------------
  def get_buys(self, **params):
    """https://developers.coinbase.com/api/v2#list-buys"""
    return self.api_client.get_buys(self.id, **params)

  def get_buy(self, buy_id, **params):
    """https://developers.coinbase.com/api/v2#show-a-buy"""
    return self.api_client.get_buy(self.id, buy_id, **params)

  def buy(self, **params):
    """https://developers.coinbase.com/api/v2#buy-bitcoin"""
    return self.api_client.buy(self.id, **params)

  def commit_buy(self, buy_id, **params):
    """https://developers.coinbase.com/api/v2#commit-a-buy"""
    return self.api_client.commit_buy(self.id, buy_id, **params)

  # Sells API
  # -----------------------------------------------------------
  def get_sells(self, **params):
    """https://developers.coinbase.com/api/v2#list-sells"""
    return self.api_client.get_sells(self.id, **params)

  def get_sell(self, sell_id, **params):
    """https://developers.coinbase.com/api/v2#show-a-sell"""
    return self.api_client.get_sell(self.id, sell_id, **params)

  def sell(self, **params):
    """https://developers.coinbase.com/api/v2#sell-bitcoin"""
    return self.api_client.sell(self.id, **params)

  def commit_sell(self, sell_id, **params):
    """https://developers.coinbase.com/api/v2#commit-a-sell"""
    return self.api_client.commit_sell(self.id, sell_id, **params)

  # Deposits API
  # -----------------------------------------------------------
  def get_deposits(self, **params):
    """https://developers.coinbase.com/api/v2#list-deposits"""
    return self.api_client.get_deposits(self.id, **params)

  def get_deposit(self, deposit_id, **params):
    """https://developers.coinbase.com/api/v2#show-a-deposit"""
    return self.api_client.get_deposit(self.id, deposit_id, **params)

  def deposit(self, **params):
    """https://developers.coinbase.com/api/v2#deposit-funds"""
    return self.api_client.deposit(self.id, **params)

  def commit_deposit(self, deposit_id, **params):
    """https://developers.coinbase.com/api/v2#commit-a-deposit"""
    return self.api_client.commit_deposit(self.id, deposit_id, **params)

  # Withdrawals API
  # -----------------------------------------------------------
  def get_withdrawals(self, **params):
    """https://developers.coinbase.com/api/v2#list-withdrawals"""
    return self.api_client.get_withdrawals(self.id, **params)

  def get_withdrawal(self, withdrawal_id, **params):
    """https://developers.coinbase.com/api/v2#show-a-withdrawal"""
    return self.api_client.get_withdrawal(self.id, withdrawal_id, **params)

  def withdraw(self, **params):
    """https://developers.coinbase.com/api/v2#withdraw-funds"""
    return self.api_client.withdraw(self.id, **params)

  def commit_withdrawal(self, withdrawal_id, **params):
    """https://developers.coinbase.com/api/v2#commit-a-withdrawal"""
    return self.api_client.commit_withdrawal(self.id, withdrawal_id, **params)

class Notification(APIObject): pass

class Address(APIObject): pass


class Checkout(APIObject):
  def get_orders(self, **params):
    """https://developers.coinbase.com/api/v2#list-checkout39s-orders"""
    return self.api_client.get_checkout_orders(self.id, **params)

  def create_order(self, **params):
    """https://developers.coinbase.com/api/v2#create-a-new-order-for-a-checkout"""
    return self.api_client.create_checkout_order(self.id, **params)


class Merchant(APIObject): pass


class Money(APIObject):
  def __str__(self):
    currency_str = '%s %s' % (self.currency, self.amount)
    # Some API responses return mappings that look like Money objects (with
    # 'amount' and 'currency' keys) but with additional information. In those
    # cases, the string representation also includes a full dump of the keys of
    # the object.
    if set(dir(self)) > set(('amount', 'currency')):
      return '{} {}'.format(
          currency_str, json.dumps(self, sort_keys=True, indent=2))
    return currency_str


class Order(APIObject):
  def refund(self, **params):
    data = self.api_client.refund_order(self.id, **params)
    self.update(data)
    return data


class PaymentMethod(APIObject): pass


class Transaction(APIObject):
  def complete(self):
    """https://developers.coinbase.com/api/v2#complete-request-money"""
    response = self.api_client._post(self.resource_path, 'complete')
    return self.api_client._make_api_object(response, APIObject)

  def resend(self):
    """https://developers.coinbase.com/api/v2#re-send-request-money"""
    response = self.api_client._post(self.resource_path, 'resend')
    return self.api_client._make_api_object(response, APIObject)

  def cancel(self):
    """https://developers.coinbase.com/api/v2#cancel-request-money"""
    response = self.api_client._post(self.resource_path, 'cancel')
    return self.api_client._make_api_object(response, APIObject)


class Report(APIObject): pass


class Transfer(APIObject):
  def commit(self, **params):
    response = self.api_client._post(self.resource_path, 'commit')
    data = self.api_client._make_api_object(response, type(self))
    self.update(data)
    return data

class Buy(Transfer): pass
class Sell(Transfer): pass
class Deposit(Transfer): pass
class Withdrawal(Transfer): pass


class User(APIObject): pass


class CurrentUser(User):
  def modify(self, **params):
    """https://developers.coinbase.com/api/v2#update-current-user"""
    data = self.api_client.update_current_user(**params)
    self.update(data)
    return data


# The following dicts are used to automatically parse API responses into the
# appropriate Python models. See `new_api_object` for more details.
_resource_to_model = {
    'account': Account,
    'balance': Money,
    'buy': Buy,
    'checkout': Checkout,
    'deposit': Transfer,
    'merchant': Merchant,
    'notification': Notification,
    'order': Order,
    'payment_method': PaymentMethod,
    'report': Report,
    'sell': Sell,
    'transaction': Transaction,
    'transfer': Transfer,
    'user': User,
    'withdrawal': Withdrawal,
  }
_obj_keys_to_model = {
    frozenset(('amount', 'currency')): Money,
  }
