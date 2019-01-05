# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import base64
import json
import os
import requests
import six
import warnings

from coinbase.wallet.auth import HMACAuth
from coinbase.wallet.auth import OAuth2Auth
from coinbase.wallet.compat import imap
from coinbase.wallet.compat import quote
from coinbase.wallet.compat import urljoin
from coinbase.wallet.error import build_api_error
from coinbase.wallet.model import APIObject
from coinbase.wallet.model import Account
from coinbase.wallet.model import Address
from coinbase.wallet.model import Buy
from coinbase.wallet.model import Checkout
from coinbase.wallet.model import CurrentUser
from coinbase.wallet.model import Deposit
from coinbase.wallet.model import Merchant
from coinbase.wallet.model import Notification
from coinbase.wallet.model import PaymentMethod
from coinbase.wallet.model import Order
from coinbase.wallet.model import Sell
from coinbase.wallet.model import Transaction
from coinbase.wallet.model import Report
from coinbase.wallet.model import User
from coinbase.wallet.model import Withdrawal
from coinbase.wallet.model import new_api_object
from coinbase.wallet.util import check_uri_security
from coinbase.wallet.util import encode_params

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

COINBASE_CRT_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), 'ca-coinbase.crt')

COINBASE_CALLBACK_PUBLIC_KEY_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), 'coinbase-callback.pub')


class Client(object):
    """API Client for the Coinbase API.

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

    BASE_API_URI = 'https://api.coinbase.com/'
    API_VERSION = '2016-02-18'

    cached_callback_public_key = None

    def __init__(self, api_key, api_secret, base_api_uri=None, api_version=None):
        if not api_key:
            raise ValueError('Missing `api_key`.')
        if not api_secret:
            raise ValueError('Missing `api_secret`.')

        # Allow passing in a different API base.
        self.BASE_API_URI = check_uri_security(base_api_uri or self.BASE_API_URI)

        self.API_VERSION = api_version or self.API_VERSION

        # Set up a requests session for interacting with the API.
        self.session = self._build_session(HMACAuth, api_key, api_secret, self.API_VERSION)

    def _build_session(self, auth_class, *args, **kwargs):
        """Internal helper for creating a requests `session` with the correct
        authentication handling.
        """
        session = requests.session()
        session.auth = auth_class(*args, **kwargs)
        session.headers.update({'CB-VERSION': self.API_VERSION,
                                'Accept': 'application/json',
                                'Content-Type': 'application/json',
                                'User-Agent': 'coinbase/python/2.0'})
        return session

    def _create_api_uri(self, *parts):
        """Internal helper for creating fully qualified endpoint URIs."""
        return urljoin(self.BASE_API_URI, '/'.join(imap(quote, parts)))

    def _request(self, method, *relative_path_parts, **kwargs):
        """Internal helper for creating HTTP requests to the Coinbase API.

        Raises an APIError if the response is not 20X. Otherwise, returns the
        response object. Not intended for direct use by API consumers.
        """
        uri = self._create_api_uri(*relative_path_parts)
        data = kwargs.get('data', None)
        if data and isinstance(data, dict):
            kwargs['data'] = encode_params(data)
        if self.VERIFY_SSL:
            kwargs.setdefault('verify', COINBASE_CRT_PATH)
        else:
            kwargs.setdefault('verify', False)
        kwargs.update(verify=self.VERIFY_SSL)
        response = getattr(self.session, method)(uri, **kwargs)
        return self._handle_response(response)

    def _handle_response(self, response):
        """Internal helper for handling API responses from the Coinbase server.

        Raises the appropriate exceptions when necessary; otherwise, returns the
        response.
        """
        if not str(response.status_code).startswith('2'):
            raise build_api_error(response)
        return response

    def _get(self, *args, **kwargs):
        """Get requests can be paginated, ensure we iterate through all the pages."""
        prev_data = kwargs.pop('prev_data', [])
        resp = self._request('get', *args, **kwargs)
        resp_content = resp._content
        if not resp_content:
            # No content so its obviously not paginated
            return resp

        # if resp._content is a bytes object, decode it so we can loads it as json
        if isinstance(resp_content, bytes):
            resp_content = resp_content.decode('utf-8')

        # Load the json so we can use the data as python objects
        content = json.loads(resp_content)
        if 'pagination' not in content:
            # Result is not paginated
            return resp

        page_info = content['pagination']
        if not page_info['next_uri']:
            # next_uri is None when the cursor has been iterated to the last element
            content['data'].extend(prev_data)
            # If resp._content was is a bytes object, only set it as a bytes object
            if isinstance(resp_content, bytes):
                resp._content = json.dumps(content).decode('utf-8')
            else:
                resp._content = json.dumps(content)
            return resp

        prev_data.extend(content['data'])
        next_page_id = page_info['next_uri'].split('=')[-1]
        kwargs.update({
            'prev_data': prev_data,
            'params': {'starting_after': next_page_id}
        })
        return self._get(*args, **kwargs)

    def _post(self, *args, **kwargs):
        return self._request('post', *args, **kwargs)

    def _put(self, *args, **kwargs):
        return self._request('put', *args, **kwargs)

    def _delete(self, *args, **kwargs):
        return self._request('delete', *args, **kwargs)

    def _make_api_object(self, response, model_type=None):
        blob = response.json()
        data = blob.get('data', None)
        # All valid responses have a "data" key.
        if data is None:
            raise build_api_error(response, blob)
        # Warn the user about each warning that was returned.
        warnings_data = blob.get('warnings', None)
        for warning_blob in warnings_data or []:
            message = "%s (%s)" % (
                warning_blob.get('message', ''),
                warning_blob.get('url', ''))
            warnings.warn(message, UserWarning)

        pagination = blob.get('pagination', None)
        kwargs = {
            'response': response,
            'pagination': pagination and new_api_object(None, pagination, APIObject),
            'warnings': warnings_data and new_api_object(None, warnings_data, APIObject)
        }
        if isinstance(data, dict):
            obj = new_api_object(self, data, model_type, **kwargs)
        else:
            obj = APIObject(self, **kwargs)
            obj.data = new_api_object(self, data, model_type)
        return obj

    # Data API
    # -----------------------------------------------------------
    def get_currencies(self, **params):
        """https://developers.coinbase.com/api/v2#currencies"""
        response = self._get('v2', 'currencies', params=params)
        return self._make_api_object(response, APIObject)

    def get_exchange_rates(self, **params):
        """https://developers.coinbase.com/api/v2#exchange-rates"""
        response = self._get('v2', 'exchange-rates', params=params)
        return self._make_api_object(response, APIObject)

    def get_buy_price(self, **params):
        """https://developers.coinbase.com/api/v2#get-buy-price"""
        currency_pair = params.get('currency_pair', 'BTC-USD')
        response = self._get('v2', 'prices', currency_pair, 'buy', params=params)
        return self._make_api_object(response, APIObject)

    def get_sell_price(self, **params):
        """https://developers.coinbase.com/api/v2#get-sell-price"""
        currency_pair = params.get('currency_pair', 'BTC-USD')
        response = self._get('v2', 'prices', currency_pair, 'sell', params=params)
        return self._make_api_object(response, APIObject)

    def get_spot_price(self, **params):
        """https://developers.coinbase.com/api/v2#get-spot-price"""
        currency_pair = params.get('currency_pair', 'BTC-USD')
        response = self._get('v2', 'prices', currency_pair, 'spot', params=params)
        return self._make_api_object(response, APIObject)

    def get_historic_prices(self, **params):
        """https://developers.coinbase.com/api/v2#get-historic-prices"""
        if 'currency_pair' in params:
            currency_pair = params['currency_pair']
        else:
            currency_pair = 'BTC-USD'
        response = self._get('v2', 'prices', currency_pair, 'historic', params=params)
        return self._make_api_object(response, APIObject)

    def get_time(self, **params):
        """https://developers.coinbase.com/api/v2#time"""
        response = self._get('v2', 'time', params=params)
        return self._make_api_object(response, APIObject)

    # User API
    # -----------------------------------------------------------
    def get_user(self, user_id, **params):
        """https://developers.coinbase.com/api/v2#show-a-user"""
        response = self._get('v2', 'users', user_id, params=params)
        return self._make_api_object(response, User)

    def get_current_user(self, **params):
        """https://developers.coinbase.com/api/v2#show-current-user"""
        response = self._get('v2', 'user', params=params)
        return self._make_api_object(response, CurrentUser)

    def get_auth_info(self, **params):
        """https://developers.coinbase.com/api/v2#show-authorization-information"""
        response = self._get('v2', 'user', 'auth', params=params)
        return self._make_api_object(response, APIObject)

    def update_current_user(self, **params):
        """https://developers.coinbase.com/api/v2#update-current-user"""
        response = self._put('v2', 'user', data=params)
        return self._make_api_object(response, CurrentUser)

    # Accounts API
    # -----------------------------------------------------------
    def get_accounts(self, **params):
        """https://developers.coinbase.com/api/v2#list-accounts"""
        response = self._get('v2', 'accounts', params=params)
        return self._make_api_object(response, Account)

    def get_account(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#show-an-account"""
        response = self._get('v2', 'accounts', account_id, params=params)
        return self._make_api_object(response, Account)

    def get_primary_account(self, **params):
        """https://developers.coinbase.com/api/v2#show-an-account"""
        return self.get_account('primary', **params)

    def create_account(self, **params):
        """https://developers.coinbase.com/api/v2#create-account"""
        response = self._post('v2', 'accounts', data=params)
        return self._make_api_object(response, Account)

    def set_primary_account(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#set-account-as-primary"""
        response = self._post('v2', 'accounts', account_id, 'primary', data=params)
        return self._make_api_object(response, Account)

    def update_account(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#update-account"""
        response = self._put('v2', 'accounts', account_id, data=params)
        return self._make_api_object(response, Account)

    def delete_account(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#delete-account"""
        self._delete('v2', 'accounts', account_id, data=params)
        return None

    # Notifications API
    # -----------------------------------------------------------
    def get_notifications(self, **params):
        """https://developers.coinbase.com/api/v2#list-notifications"""
        response = self._get('v2', 'notifications', params=params)
        return self._make_api_object(response, Notification)

    def get_notification(self, notification_id, **params):
        """https://developers.coinbase.com/api/v2#show-a-notification"""
        response = self._get('v2', 'notifications', notification_id, params=params)
        return self._make_api_object(response, Notification)

    # Addresses API
    # -----------------------------------------------------------
    def get_addresses(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#list-addresses"""
        response = self._get('v2', 'accounts', account_id, 'addresses', params=params)
        return self._make_api_object(response, Address)

    def get_address(self, account_id, address_id, **params):
        """https://developers.coinbase.com/api/v2#show-addresss"""
        response = self._get('v2', 'accounts', account_id, 'addresses', address_id, params=params)
        return self._make_api_object(response, Address)

    def get_address_transactions(self, account_id, address_id, **params):
        """https://developers.coinbase.com/api/v2#list-address39s-transactions"""
        response = self._get(
            'v2',
            'accounts',
            account_id,
            'addresses',
            address_id,
            'transactions',
            params=params)
        return self._make_api_object(response, Transaction)

    def create_address(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#create-address"""
        response = self._post('v2', 'accounts', account_id, 'addresses', data=params)
        return self._make_api_object(response, Address)

    # Transactions API
    # -----------------------------------------------------------
    def get_transactions(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#list-transactions"""
        response = self._get('v2', 'accounts', account_id, 'transactions', params=params)
        return self._make_api_object(response, Transaction)

    def get_transaction(self, account_id, transaction_id, **params):
        """https://developers.coinbase.com/api/v2#show-a-transaction"""
        response = self._get(
            'v2', 'accounts', account_id, 'transactions', transaction_id, params=params)
        return self._make_api_object(response, Transaction)

    def send_money(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#send-money"""
        for required in ['to', 'amount', 'currency']:
            if required not in params:
                raise ValueError("Missing required parameter: %s" % required)
        params['type'] = 'send'
        response = self._post('v2', 'accounts', account_id, 'transactions', data=params)
        return self._make_api_object(response, Transaction)

    def transfer_money(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#transfer-money-between-accounts"""
        for required in ['to', 'amount', 'currency']:
            if required not in params:
                raise ValueError("Missing required parameter: %s" % required)
        params['type'] = 'transfer'
        response = self._post('v2', 'accounts', account_id, 'transactions', data=params)
        return self._make_api_object(response, Transaction)

    def request_money(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#request-money"""
        for required in ['to', 'amount', 'currency']:
            if required not in params:
                raise ValueError("Missing required parameter: %s" % required)
        params['type'] = 'request'
        response = self._post('v2', 'accounts', account_id, 'transactions', data=params)
        return self._make_api_object(response, Transaction)

    def complete_request(self, account_id, request_id, **params):
        """https://developers.coinbase.com/api/v2#complete-request-money"""
        response = self._post(
            'v2', 'accounts', account_id, 'transactions', request_id,
            'complete', data=params)
        return self._make_api_object(response, APIObject)

    def resend_request(self, account_id, request_id, **params):
        """https://developers.coinbase.com/api/v2#re-send-request-money"""
        response = self._post(
            'v2', 'accounts', account_id, 'transactions', request_id, 'resend',
            data=params)
        return self._make_api_object(response, APIObject)

    def cancel_request(self, account_id, request_id, **params):
        """https://developers.coinbase.com/api/v2#cancel-request-money"""
        response = self._post(
            'v2', 'accounts', account_id, 'transactions', request_id, 'cancel',
            data=params)
        return self._make_api_object(response, APIObject)

    # Reports API
    # -----------------------------------------------------------
    def get_reports(self, **params):
        """https://developers.coinbase.com/api/v2#list-all-reports"""
        response = self._get('v2', 'reports', data=params)
        return self._make_api_object(response, Report)

    def get_report(self, report_id, **params):
        """https://developers.coinbase.com/api/v2#show-a-report"""
        response = self._get('v2', 'reports', report_id, data=params)
        return self._make_api_object(response, Report)

    def create_report(self, **params):
        """https://developers.coinbase.com/api/v2#generate-a-new-report"""
        if 'type' not in params and 'email' not in params:
            raise ValueError("Missing required parameter: 'type' or 'email'")
        response = self._post('v2', 'reports', data=params)
        return self._make_api_object(response, Report)

    # Buys API
    # -----------------------------------------------------------
    def get_buys(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#list-buys"""
        response = self._get('v2', 'accounts', account_id, 'buys', params=params)
        return self._make_api_object(response, Buy)

    def get_buy(self, account_id, buy_id, **params):
        """https://developers.coinbase.com/api/v2#show-a-buy"""
        response = self._get('v2', 'accounts', account_id, 'buys', buy_id, params=params)
        return self._make_api_object(response, Buy)

    def buy(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#buy-bitcoin"""
        if 'amount' not in params and 'total' not in params:
            raise ValueError("Missing required parameter: 'amount' or 'total'")
        for required in ['currency', 'payment_method']:
            if required not in params:
                raise ValueError("Missing required parameter: %s" % required)
        response = self._post('v2', 'accounts', account_id, 'buys', data=params)
        return self._make_api_object(response, Buy)

    def commit_buy(self, account_id, buy_id, **params):
        """https://developers.coinbase.com/api/v2#commit-a-buy"""
        response = self._post(
            'v2', 'accounts', account_id, 'buys', buy_id, 'commit', data=params)
        return self._make_api_object(response, Buy)

    # Sells API
    # -----------------------------------------------------------
    def get_sells(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#list-sells"""
        response = self._get('v2', 'accounts', account_id, 'sells', params=params)
        return self._make_api_object(response, Sell)

    def get_sell(self, account_id, sell_id, **params):
        """https://developers.coinbase.com/api/v2#show-a-sell"""
        response = self._get(
            'v2', 'accounts', account_id, 'sells', sell_id, params=params)
        return self._make_api_object(response, Sell)

    def sell(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#sell-bitcoin"""
        if 'amount' not in params and 'total' not in params:
            raise ValueError("Missing required parameter: 'amount' or 'total'")
        for required in ['currency']:
            if required not in params:
                raise ValueError("Missing required parameter: %s" % required)
        response = self._post('v2', 'accounts', account_id, 'sells', data=params)
        return self._make_api_object(response, Sell)

    def commit_sell(self, account_id, sell_id, **params):
        """https://developers.coinbase.com/api/v2#commit-a-sell"""
        response = self._post(
            'v2', 'accounts', account_id, 'sells', sell_id, 'commit', data=params)
        return self._make_api_object(response, Sell)

    # Deposits API
    # -----------------------------------------------------------
    def get_deposits(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#list-deposits"""
        response = self._get('v2', 'accounts', account_id, 'deposits', params=params)
        return self._make_api_object(response, Deposit)

    def get_deposit(self, account_id, deposit_id, **params):
        """https://developers.coinbase.com/api/v2#show-a-deposit"""
        response = self._get(
            'v2', 'accounts', account_id, 'deposits', deposit_id, params=params)
        return self._make_api_object(response, Deposit)

    def deposit(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#deposit-funds"""
        for required in ['payment_method', 'amount', 'currency']:
            if required not in params:
                raise ValueError("Missing required parameter: %s" % required)
        response = self._post('v2', 'accounts', account_id, 'deposits', data=params)
        return self._make_api_object(response, Deposit)

    def commit_deposit(self, account_id, deposit_id, **params):
        """https://developers.coinbase.com/api/v2#commit-a-deposit"""
        response = self._post(
            'v2', 'accounts', account_id, 'deposits', deposit_id, 'commit',
            data=params)
        return self._make_api_object(response, Deposit)

    # Withdrawals API
    # -----------------------------------------------------------
    def get_withdrawals(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#list-withdrawals"""
        response = self._get('v2', 'accounts', account_id, 'withdrawals', params=params)
        return self._make_api_object(response, Withdrawal)

    def get_withdrawal(self, account_id, withdrawal_id, **params):
        """https://developers.coinbase.com/api/v2#show-a-withdrawal"""
        response = self._get(
            'v2', 'accounts', account_id, 'withdrawals', withdrawal_id, params=params)
        return self._make_api_object(response, Withdrawal)

    def withdraw(self, account_id, **params):
        """https://developers.coinbase.com/api/v2#withdraw-funds"""
        for required in ['payment_method', 'amount', 'currency']:
            if required not in params:
                raise ValueError("Missing required parameter: %s" % required)
        response = self._post('v2', 'accounts', account_id, 'withdrawals', data=params)
        return self._make_api_object(response, Withdrawal)

    def commit_withdrawal(self, account_id, withdrawal_id, **params):
        """https://developers.coinbase.com/api/v2#commit-a-withdrawal"""
        response = self._post(
            'v2', 'accounts', account_id, 'withdrawals', withdrawal_id, 'commit',
            data=params)
        return self._make_api_object(response, Withdrawal)

    # Payment Methods API
    # -----------------------------------------------------------
    def get_payment_methods(self, **params):
        """https://developers.coinbase.com/api/v2#list-payment-methods"""
        response = self._get('v2', 'payment-methods', params=params)
        return self._make_api_object(response, PaymentMethod)

    def get_payment_method(self, payment_method_id, **params):
        """https://developers.coinbase.com/api/v2#show-a-payment-method"""
        response = self._get('v2', 'payment-methods', payment_method_id, params=params)
        return self._make_api_object(response, PaymentMethod)

    # Merchants API
    # -----------------------------------------------------------
    def get_merchant(self, merchant_id, **params):
        """https://developers.coinbase.com/api/v2#show-a-merchant"""
        response = self._get('v2', 'merchants', merchant_id, params=params)
        return self._make_api_object(response, Merchant)

    # Orders API
    # -----------------------------------------------------------
    def get_orders(self, **params):
        """https://developers.coinbase.com/api/v2#list-orders"""
        response = self._get('v2', 'orders', params=params)
        return self._make_api_object(response, Order)

    def get_order(self, order_id, **params):
        """https://developers.coinbase.com/api/v2#show-an-order"""
        response = self._get('v2', 'orders', order_id, params=params)
        return self._make_api_object(response, Order)

    def create_order(self, **params):
        """https://developers.coinbase.com/api/v2#create-an-order"""
        for required in ['amount', 'currency', 'name']:
            if required not in params:
                raise ValueError("Missing required parameter: %s" % required)
        response = self._post('v2', 'orders', data=params)
        return self._make_api_object(response, Order)

    def refund_order(self, order_id, **params):
        """https://developers.coinbase.com/api/v2#refund-an-order"""
        for required in ['currency']:
            if required not in params:
                raise ValueError("Missing required parameter: %s" % required)
        response = self._post('v2', 'orders', order_id, 'refund', data=params)
        return self._make_api_object(response, Order)

    # Checkouts API
    # -----------------------------------------------------------
    def get_checkouts(self, **params):
        """https://developers.coinbase.com/api/v2#list-checkouts"""
        response = self._get('v2', 'checkouts', params=params)
        return self._make_api_object(response, Checkout)

    def get_checkout(self, checkout_id, **params):
        """https://developers.coinbase.com/api/v2#show-a-checkout"""
        response = self._get('v2', 'checkouts', checkout_id, params=params)
        return self._make_api_object(response, Checkout)

    def create_checkout(self, **params):
        """https://developers.coinbase.com/api/v2#create-checkout"""
        for required in ['amount', 'currency', 'name']:
            if required not in params:
                raise ValueError("Missing required parameter: %s" % required)
        response = self._post('v2', 'checkouts', data=params)
        return self._make_api_object(response, Checkout)

    def get_checkout_orders(self, checkout_id, **params):
        """https://developers.coinbase.com/api/v2#list-checkout39s-orders"""
        response = self._get('v2', 'checkouts', checkout_id, 'orders', params=params)
        return self._make_api_object(response, Order)

    def create_checkout_order(self, checkout_id, **params):
        """https://developers.coinbase.com/api/v2#create-a-new-order-for-a-checkout"""
        response = self._post('v2', 'checkouts', checkout_id, 'orders', data=params)
        return self._make_api_object(response, Order)

    def verify_callback(self, body, signature):
        h = SHA256.new()
        h.update(body)
        key = Client.callback_public_key()
        verifier = PKCS1_v1_5.new(key)
        signature = bytes(signature, 'utf-8') if six.PY3 else bytes(signature)
        signature_buffer = base64.b64decode(signature)
        return verifier.verify(h, signature_buffer)

    @staticmethod
    def callback_public_key():
        if Client.cached_callback_public_key is None:
            f = open(COINBASE_CALLBACK_PUBLIC_KEY_PATH, 'r')
            Client.cached_callback_public_key = RSA.importKey(f.read())
        return Client.cached_callback_public_key


class OAuthClient(Client):
    def __init__(self, access_token, refresh_token, base_api_uri=None, api_version=None):
        if not access_token:
            raise ValueError("Missing `access_token`.")
        if not refresh_token:
            raise ValueError("Missing `refresh_token`.")

        self.access_token = access_token
        self.refresh_token = refresh_token

        # Allow passing in a different API base.
        self.BASE_API_URI = check_uri_security(base_api_uri or self.BASE_API_URI)

        self.API_VERSION = api_version or self.API_VERSION

        # Set up a requests session for interacting with the API.
        self.session = self._build_session(OAuth2Auth, lambda: self.access_token, self.API_VERSION)

    def revoke(self):
        """https://developers.coinbase.com/docs/wallet/coinbase-connect#revoking-an-access-token"""
        response = self._post('oauth', 'revoke', data={'token': self.access_token})
        return None

    def refresh(self):
        """Attempt to refresh the current access token / refresh token pair.

        If successful, the relevant attributes of this client will be updated
        automatically and the dict of token values and information given  by the
        Coinbase OAuth server will be returned to the caller.
        """
        params = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        response = self._post('oauth', 'token', params=params)
        response = self._handle_response(response)
        blob = response.json()
        self.access_token = blob.get('access_token', None)
        self.refresh_token = blob.get('refresh_token', None)
        if not (self.access_token and self.refresh_token):
            raise build_api_error(response, blob)
        return blob
