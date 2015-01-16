# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import six
from functools import partial

from coinbase.compat import imap
from coinbase.error import APIError
from coinbase.error import UnexpectedDataFormatError
from coinbase.error import build_api_error
from coinbase.util import encode_params
from coinbase.util import unnest

# TODO(peter): it would be annoying to have to fetch an entire Account object
# in order to fetch transactions for a given account. All models should be
# fetchable directly from the Client object.
class APIObject(dict):
  """Generic class used to represent a JSON response from the Coinbase API.

  If you're a consumer of the API, you shouldn't be using this class directly.
  This exists to make it easier to consume our API by allowing dot-notation
  access to the responses, as well as automatically parsing the responses into
  the appropriate Python models.
  """
  def __init__(self, api_client, account=None, paged_key=None):
    self.__api_client = api_client
    self.__account = account
    self.__paged_key = paged_key

  def load(self, value, key=None, store=True, account=None, **kwargs):
    # It's useful to keep track of account objects because the API doesn't
    # include this information.
    if account is None:
      account = self.account

    if isinstance(value, dict):
      # API responses may included JSON representations of the API models.
      # When this is the case, they are automatically transformed into more
      # specific model objects. The key of the JSON representation is used to
      # determine which model.
      model_class = _key_to_model.get(key, None)
      # Some API endpoints directly return the JSON representation of one of
      # our models. In this case, that model class is returned instead of a
      # generic APIObject. The keys of the API response are used to determine
      # which model is being returned. If the model cannot be determined from
      # the keys, which happens when the response does not directly represent a
      # model (for instance, such as when it includes pagination information),
      # the result will be a generic APIObject.
      if not model_class and isinstance(value, dict):
        obj_keys = set(six.iterkeys(value))
        for keys, model in six.iteritems(_obj_keys_to_model):
          if keys <= obj_keys:
            model_class = model
            break
      # If the response doesn't match a particular object, use a generic type.
      model_class = model_class or APIObject

      # Some API endpoint responses are nested in such a way that provides no
      # benefit to the user. If necessary, this unnests the response.
      unnester = _unnesters.get(key, None)
      if unnester:
        value = unnester(value)

      # Move the key-value pairs of the current value being loaded to the
      # appropriate APIObject or subclass.
      instance = model_class(self.api_client, account=account, **kwargs)
      for k, v in six.iteritems(value):
        instance.load(value=v, key=k, store=True, account=account, **kwargs)
      value = instance

    elif isinstance(value, list):
      # If the value to be loaded is a list, then load each object within it.
      # `store` is set to `False` so that the result is accessible to the
      # current context, which is responsible for storing the result.
      value = list(imap(
          partial(self.load, key=key, store=False, account=account, **kwargs),
          value))

    # If store == False, then the value should be returned to the calling
    # context.  If key == None, then value is the top-most API object, which
    # should be returned to the calling code. If they are both true,`value`
    # should be stored in the current context under `key`.
    if store and key:
      self[key] = value
      return None
    return value


  @property
  def api_client(self):
    """Provide access to the underlying `Client` for user convenience."""
    return self.__api_client

  @property
  def account(self):
    """Provide access to the related `Account` for user convenience."""
    return self.__account

  # The following three method definitions allow dot-notation access to member
  # objects for convenience.
  def __getattr__(self, *args, **kwargs):
    try:
      return dict.__getitem__(self, *args, **kwargs)
    except KeyError as key_error:
      attribute_error = AttributeError(*key_error.args)
      attribute_error.message = key_error.message
      raise attribute_error

  def __delattr__(self, *args, **kwargs):
    try:
      return dict.__delitem__(self, *args, **kwargs)
    except KeyError as key_error:
      attribute_error = AttributeError(*key_error.args)
      attribute_error.message = key_error.message
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

  # When an API response includes page details in addition to the requested
  # data, allow slicing directly into that data instead of forcing additional
  # attribute access.
  def __getitem__(self, key):
    if self.__paged_key and isinstance(key, (int, slice)):
      return self[self.__paged_key][key]
    return dict.__getitem__(self, key)

  def __dir__(self):
    # This makes tab completion work in interactive shells like IPython for all
    # attributes, items, and methods.
    return list(self.keys()) # pragma: no cover

  def __str__(self):
    try:
      return json.dumps(self, sort_keys=True, indent=2)
    except TypeError:
      return '(invalid JSON)'

  def __name__(self):
    return '<{0} @ {1}>'.format(type(self).__name__, hex(id(self))) # pragma: no cover

  def __repr__(self):
    return '{0} {1}'.format(self.__name__(), str(self)) # pragma: no cover


class Account(APIObject):
  @property
  def account(self):
    return self

  def delete(self):
    """https://developers.coinbase.com/api#delete-an-account"""
    response = self.api_client._delete('accounts', self.id)
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Account deletion failed')

  def set_primary(self):
    """https://developers.coinbase.com/api#set-account-as-primary"""
    response = self.api_client._post('accounts', self.id, 'primary')
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Account could not be set as primary')
    self.primary = True

  def modify(self, new_name=None):
    """https://developers.coinbase.com/api#modify-an-account"""
    data = encode_params({
        'account': {
          'name': new_name,
        },
      })
    response = self.api_client._put('accounts', self.id, data=data)
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Account update failed')

    account = api_obj.get('account', None)
    if not isinstance(account, Account):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    self.update(account)

  def get_balance(self):
    """https://developers.coinbase.com/api#get-account39s-balance"""
    response = self.api_client._get('accounts', self.id, 'balance')
    return self.load(response.json())

  def get_address(self):
    """https://developers.coinbase.com/api#get-account39s-bitcoin-address"""
    response = self.api_client._get('accounts', self.id, 'address')
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Failed to fetch account address')
    if not isinstance(api_obj, Address):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return api_obj

  def get_addresses(self, page=None, limit=None, query=None):
    """https://developers.coinbase.com/api#list-bitcoin-addresses"""
    data = encode_params({
        'account_id': self.id,
        'limit': limit,
        'page': page,
        'query': query,
      })
    response = self.api_client._get('addresses', data=data)
    return self.load(response.json(), paged_key='addresses')

  def create_address(self, label=None, callback_url=None):
    """https://developers.coinbase.com/api#create-a-new-bitcoin-address-for-an-account"""
    data = encode_params({
        'address': {
          'label': label,
          'callback_url': callback_url,
        },
      })
    response = self.api_client._post(
        'accounts', self.id, 'address', data=data)
    address = self.load(response.json())
    if not address.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Address creation failed')
    if not isinstance(address, Address):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return address

  def get_transactions(self, page=None, limit=None):
    """https://developers.coinbase.com/api#list-transactions"""
    data = encode_params({
        'account_id': self.id,
        'limit': limit,
        'page': page,
      })
    response = self.api_client._get('transactions', data=data)
    return self.load(response.json(), paged_key='transactions')

  def get_transaction(self, transaction_id):
    """https://developers.coinbase.com/api#show-a-transaction"""
    data = encode_params({'account_id': self.id})
    response = self.api_client._get(
        'transactions', transaction_id, data=data)
    api_obj = self.load(response.json())
    transaction = api_obj.get('transaction', None)
    if not isinstance(transaction, Transaction):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return transaction

  def transfer_money(
      self, to_account_id, amount=None, amount_string=None,
      amount_currency_iso=None, notes=None, user_fee=None, referrer_id=None,
      idem=None, instant_buy=None, order_id=None):
    """https://developers.coinbase.com/api#transfer-money-between-accounts"""
    if (not (amount or (amount_string and amount_currency_iso)) or
        (amount and (amount_string or amount_currency_iso))):
      raise ValueError(
          'Must supply either `amount` OR `amount_string` and '
          '`amount_currency_iso`')
    data = encode_params({
        'account_id': self.id,
        'transaction': {
          'amount': amount,
          'amount_currency_iso': amount_currency_iso,
          'amount_string': amount_string,
          'idem': idem,
          'instant_buy': instant_buy,
          'notes': notes,
          'order_id': order_id,
          'referrer_id': referrer_id,
          'to': to_account_id,
          'user_fee': user_fee,
        },
      })
    response = self.api_client._post(
        'transactions', 'transfer_money', data=data)
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Failed to send money')
    transaction = api_obj.get('transaction', None)
    if not isinstance(transaction, Transaction):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return transaction

  def send_money(
      self, to_btc_address, amount=None, amount_string=None,
      amount_currency_iso=None, notes=None, user_fee=None, referrer_id=None,
      idem=None, instant_buy=None, order_id=None, two_factor_token=None):
    """https://developers.coinbase.com/api#send-money"""
    if (not (amount or (amount_string and amount_currency_iso)) or
        (amount and (amount_string or amount_currency_iso))):
      raise ValueError(
          'Must supply either `amount` OR `amount_string` and '
          '`amount_currency_iso`')

    data = encode_params({
        'account_id': self.id,
        'transaction': {
          'amount': amount,
          'amount_currency_iso': amount_currency_iso,
          'amount_string': amount_string,
          'idem': idem,
          'instant_buy': instant_buy,
          'notes': notes,
          'order_id': order_id,
          'referrer_id': referrer_id,
          'to': to_btc_address,
          'user_fee': user_fee,
        },
      })
    headers = {'CB-2FA-Token': two_factor_token} if two_factor_token else None
    response = self.api_client._post(
        'transactions', 'send_money', data=data, headers=headers)
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Failed to send money')
    transaction = api_obj.get('transaction', None)
    if not isinstance(transaction, Transaction):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return transaction

  def request_money(
      self, from_email_address, amount=None, amount_string=None,
      amount_currency_iso=None, notes=None):
    """https://developers.coinbase.com/api#request-bitcoin"""
    if (not (amount or (amount_string and amount_currency_iso)) or
        (amount and (amount_string or amount_currency_iso))):
      raise ValueError(
          'Must supply either `amount` OR `amount_string` and '
          '`amount_currency_iso`')
    data = encode_params({
        'account_id': self.id,
        'transaction': {
          'amount': amount,
          'amount_currency_iso': amount_currency_iso,
          'amount_string': amount_string,
          'notes': notes,
          'from': from_email_address,
        },
      })
    response = self.api_client._post(
        'transactions', 'request_money', data=data)
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Failed to request money')
    transaction = api_obj.get('transaction', None)
    if not isinstance(transaction, Transaction):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return transaction

  def get_transfer(self, transfer_id):
    """https://developers.coinbase.com/api#show-a-transfer"""
    data = encode_params({'account_id': self.id})
    response = self.api_client._get('transfers', transfer_id, data=data)
    api_obj = self.load(response.json())
    transfer = api_obj.get('transfer', None)
    if not isinstance(transfer, Transfer):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return transfer

  def get_transfers(self, page=None, limit=None):
    """https://developers.coinbase.com/api#list-buy-and-sell-history"""
    data = encode_params({
        'account_id': self.id,
        'limit': limit,
        'page': page,
      })
    response = self.api_client._get('transfers', data=data)
    return self.load(response.json(), paged_key='transfers')

  def get_button(self, code_or_custom):
    """https://developers.coinbase.com/api#show-a-button"""
    response = self.api_client._get('buttons', code_or_custom)
    api_obj = self.load(response.json())
    button = api_obj.get('button', None)
    if not isinstance(button, Button):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return button

  def create_button(self, name, price_string, price_currency_iso, type=None,
      subscription=None, repeat=None, style=None, text=None, description=None,
      custom=None, custom_secure=None, callback_url=None, success_url=None,
      cancel_url=None, info_url=None, auto_redirect=None,
      auto_redirect_success=None, auto_redirect_cancel=None,
      variable_price=None, include_address=None, include_email=None,
      choose_price=None, price_1=None, price_2=None, price_3=None,
      price_4=None, price_5=None):
    """https://developers.coinbase.com/api#create-a-new-payment-button-page-or-iframe"""
    data = encode_params({
        'account_id': self.id,
        'button': {
          'name': name,
          'price_string': price_string,
          'price_currency_iso': price_currency_iso,
          'type': type,
          'subscription': subscription,
          'repeat': repeat,
          'style': style,
          'text': text,
          'description': description,
          'custom': custom,
          'custom_secure': custom_secure,
          'callback_url': callback_url,
          'success_url': success_url,
          'cancel_url': cancel_url,
          'info_url': info_url,
          'auto_redirect': auto_redirect,
          'auto_redirect_success': auto_redirect_success,
          'auto_redirect_cancel': auto_redirect_cancel,
          'variable_price': variable_price,
          'include_address': include_address,
          'include_email': include_email,
          'choose_price': choose_price,
          'price_1': price_1,
          'price_2': price_2,
          'price_3': price_3,
          'price_4': price_4,
          'price_5': price_5,
        },
      })
    response = self.api_client._post('buttons', data=data)
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Failed to create button')
    button = api_obj.get('button', None)
    if not isinstance(button, Button):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return button

  def get_orders(self, page=None, limit=None):
    """https://developers.coinbase.com/api#list-orders"""
    data = encode_params({
        'account_id': self.id,
        'limit': limit,
        'page': page,
      })
    response = self.api_client._get('orders', data=data)
    return self.load(response.json(), paged_key='orders')

  def get_order(self, id_or_custom):
    """https://developers.coinbase.com/api#show-an-order"""
    data = encode_params({'account_id': self.id})
    response = self.api_client._get('orders', id_or_custom, data=data)
    api_obj = self.load(response.json())
    order = api_obj.get('order', None)
    if not isinstance(order, Order):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return order

  def create_order(self, name, price_string, price_currency_iso, type=None,
      subscription=None, repeat=None, style=None, text=None, description=None,
      custom=None, custom_secure=None, callback_url=None, success_url=None,
      cancel_url=None, info_url=None, auto_redirect=None,
      auto_redirect_success=None, auto_redirect_cancel=None,
      variable_price=None, include_address=None, include_email=None,
      choose_price=None, price_1=None, price_2=None, price_3=None,
      price_4=None, price_5=None):
    data = encode_params({
        'account_id': self.id,
        'button': {
          'name': name,
          'price_string': price_string,
          'price_currency_iso': price_currency_iso,
          'type': type,
          'subscription': subscription,
          'repeat': repeat,
          'style': style,
          'text': text,
          'description': description,
          'custom': custom,
          'custom_secure': custom_secure,
          'callback_url': callback_url,
          'success_url': success_url,
          'cancel_url': cancel_url,
          'info_url': info_url,
          'auto_redirect': auto_redirect,
          'auto_redirect_success': auto_redirect_success,
          'auto_redirect_cancel': auto_redirect_cancel,
          'variable_price': variable_price,
          'include_address': include_address,
          'include_email': include_email,
          'choose_price': choose_price,
          'price_1': price_1,
          'price_2': price_2,
          'price_3': price_3,
          'price_4': price_4,
          'price_5': price_5,
        },
      })
    response = self.api_client._post('orders', data=data)
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Failed to create order')
    order = api_obj.get('order', None)
    if not isinstance(order, Order):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return order

  def buy(self, qty, currency=None, agree_btc_amount_varies=None, commit=None,
      payment_method_id=None):
    """https://developers.coinbase.com/api#buys"""
    data = encode_params({
      'account_id': self.id,
      'qty': qty,
      'currency': currency,
      'agree_btc_amount_varies': agree_btc_amount_varies,
      'commit': commit,
      'payment_method_id': payment_method_id,
    })
    response = self.api_client._post('buys', data=data)
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Failed to buy bitcoin')
    transfer = api_obj.get('transfer', None)
    if not isinstance(transfer, Transfer):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return transfer

  def sell(self, qty, currency=None, agree_btc_amount_varies=None, commit=None,
      payment_method_id=None):
    """https://developers.coinbase.com/api#sells"""
    data = encode_params({
      'account_id': self.id,
      'qty': qty,
      'currency': currency,
      'agree_btc_amount_varies': agree_btc_amount_varies,
      'commit': commit,
      'payment_method_id': payment_method_id,
    })
    response = self.api_client._post('sells', data=data)
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Failed to buy bitcoin')
    transfer = api_obj.get('transfer', None)
    if not isinstance(transfer, Transfer):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return transfer




class Address(APIObject): pass


class Button(APIObject):
  def get_orders(self, page=None, limit=None):
    """https://developers.coinbase.com/api#list-orders-for-a-button"""
    data = encode_params({
        'account_id': self.account and self.account.id,
        'page': page,
        'limit': limit,
      })
    # Buttons included as attributes on Order objects have an 'id' attribute,
    # but not a 'code' attribute. Buttons fetched directly from the
    # `get_button` API have a 'code' attribute, but not a 'id' attribute.
    identifier = getattr(self, 'id', None) or getattr(self, 'code', None)
    response = self.api_client._get('buttons', identifier, 'orders', data=data)
    return self.load(response.json(), paged_key='orders')

  def create_order(self):
    """https://developers.coinbase.com/api#create-an-order-for-a-button"""
    response = self.api_client._post('buttons', self.code, 'create_order')
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Failed to create order')
    order = api_obj.get('order', None)
    if not isinstance(order, Order):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return order


class Contact(APIObject): pass


class Money(APIObject):
  def __str__(self):
    currency_str = '%s %s' % (self.currency, self.amount)
    # Some API responses return mappings that look like Money objects (with
    # 'amount' and 'currency' keys) but with additional information. In those
    # cases, the string representation also includes a full dump of the keys of
    # the object.
    if set(dir(self)) > set(('amount', 'currency')):
      return '{0} {1}'.format(
          currency_str, json.dumps(self, sort_keys=True, indent=2))
    return currency_str


class Order(APIObject):
  def refund(self, refund_iso_code, mispayment_id=None,
      external_refund_address=None, instant_buy=None):
    """https://developers.coinbase.com/api#refund-an-order"""
    data = encode_params({
        'order': {
          'refund_iso_code': refund_iso_code,
          'external_refund_address': external_refund_address,
          'mispayment_id': mispayment_id,
          'instant_buy': instant_buy,
        },
      })
    response = self.api_client._post('orders', self.id, 'refund', data=data)
    api_obj = self.load(response.json())
    order = api_obj.get('order', None)
    if not isinstance(order, Order):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return order


class PaymentMethod(APIObject): pass


class Transaction(APIObject):
  def resend(self):
    """https://developers.coinbase.com/api#resend-bitcoin-request"""
    data = encode_params({
        'account_id': self.account and self.account.id,
      })
    response = self.api_client._put(
        'transactions', self.id, 'resend_request', data=data)
    api_obj = self.load(response.json())
    success = api_obj.get('success', False)
    if not success:
      raise build_api_error(
          APIError,
          response,
          'Failed to resend transaction')
    return success

  def complete(self):
    """https://developers.coinbase.com/api#complete-bitcoin-request"""
    data = encode_params({'account_id': self.account and self.account.id})
    response = self.api_client._put(
        'transactions', self.id, 'complete_request', data=data)
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'Failed to complete transaction')
    transaction = api_obj.get('transaction', None)
    if not isinstance(transaction, Transaction):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return transaction

  def cancel(self):
    """https://developers.coinbase.com/api#cancel-bitcoin-request"""
    data = encode_params({'account_id': self.account and self.account.id})
    response = self.api_client._delete(
        'transactions', self.id, 'cancel_request', data=data)
    api_obj = self.load(response.json())
    success = api_obj.get('success', False)
    if not success:
      raise build_api_error(
          APIError,
          response,
          'Failed to resend transaction')
    return success


class Transfer(APIObject):
  def commit(self):
    """https://developers.coinbase.com/api#start-a-transfer-that-is-in-the-created-state"""
    data = encode_params({
      'account_id': self.account and self.account.id,
    })
    response = self.api_client._post('transfers', self.id, 'commit', data=data)
    api_obj = self.load(response.json())
    success = api_obj.get('success', False)
    if not success:
      raise build_api_error(
          APIError,
          response,
          'Failed to commit transfer')
    transfer = api_obj.get('transfer', None)
    if not isinstance(transfer, Transfer):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    return transfer




class User(APIObject):
  def modify(self, name=None, native_currency=None, time_zone=None):
    """https://developers.coinbase.com/api#modify-current-user"""
    if not (name or native_currency or time_zone):
      raise ValueError('Must supply at least one field to be modified.')

    data = encode_params({
        'user': {
          'name': name,
          'native_currency': native_currency,
          'time_zone': time_zone,
        },
      })
    response = self.api_client._put('users', self.id, data=data)
    api_obj = self.load(response.json())
    if not api_obj.get('success', False):
      raise build_api_error(
          APIError,
          response,
          'User update failed')
    user = api_obj.get('user', None)
    if not isinstance(user, User):
      raise build_api_error(
          UnexpectedDataFormatError,
          response,
          'Could not parse API response')
    self.update(user)


# The following dicts are used to automatically parse API responses into the
# appropriate Python models. See `APIObject.load` for more details.
_unnesters = {
    'addresses': unnest('address'),
    'orders': unnest('order'),
    'payment_methods': unnest('payment_method'),
    'transactions': unnest('transaction'),
    'transfers': unnest('transfer'),
  }
_key_to_model = {
    'account': Account,
    'accounts': Account,
    'addresses': Address,
    'balance': Money,
    'button': Button,
    'buttons': Button,
    'contact': Contact,
    'contacts': Contact,
    'current_user': User,
    'native_balance': Money,
    'order': Order,
    'orders': Order,
    'payment_method': PaymentMethod,
    'payment_methods': PaymentMethod,
    'recipient': User,
    'sender': User,
    'transaction': Transaction,
    'transactions': Transaction,
    'transfer': Transfer,
    'transfers': Transfer,
    'user': User,
  }
_obj_keys_to_model = {
    frozenset(('address', 'callback_url', 'label')): Address,
    frozenset(('amount', 'currency')): Money,
  }
