Coinbase
========

.. image:: https://img.shields.io/pypi/v/coinbase.svg
    :target: https://pypi.python.org/pypi/coinbase

.. image:: https://img.shields.io/travis/coinbase/coinbase-python/master.svg
    :target: https://travis-ci.org/coinbase/coinbase-python

.. image:: https://img.shields.io/pypi/wheel/coinbase.svg
    :target: https://pypi.python.org/pypi/coinbase/

.. image:: https://img.shields.io/pypi/pyversions/coinbase.svg
    :target: https://pypi.python.org/pypi/coinbase/

.. image:: https://img.shields.io/pypi/l/coinbase.svg
    :target: https://pypi.python.org/pypi/coinbase/

The official Python library for the `Coinbase API V2 <https://developers.coinbase.com/api/v2>`_.

*Important*: this library currently targets the API V2, and the OAuth client requires V2 permissions (i.e. ``wallet:accounts:read``).
If you're still using the API V1, please use `the old version of this library <https://pypi.python.org/pypi/coinbase/1.0.4>`_.

Features
--------

- Near-100% test coverage.
- Support for both `API Key + Secret <https://developers.coinbase.com/api/v2/#api-key>`_ and `OAuth 2 <https://developers.coinbase.com/api/v2/#oauth2-coinbase-connect>`_ authentication.
- Convenient methods for making calls to the API - packs JSON for you!
- Automatic parsing of API responses into relevant Python objects.
- All objects have tab-completable methods and attributes when using `IPython <http://ipython.org>`_.


Installation
------------

``coinbase`` is available on `PYPI <https://pypi.python.org/pypi/coinbase/>`_.
Install with ``pip``:

.. code:: bash

    pip install coinbase

or with ``easy_install``:

.. code:: bash

    easy_install coinbase

The library is currently tested against Python versions 2.7 and 3.4+.

Documentation
-------------

The first thing you'll need to do is `sign up with Coinbase <https://coinbase.com>`_.

API Key + Secret
^^^^^^^^^^^^^^^^

If you're writing code for your own Coinbase account, `enable an API key <https://coinbase.com/settings/api>`_.

Next, create a ``Client`` object for interacting with the API:

.. code:: python

    from coinbase.wallet.client import Client
    client = Client(api_key, api_secret)

OAuth2
^^^^^^

If you're writing code that will act on behalf of another user, start by `creating a new OAuth 2 application from the API settings page <https://coinbase.com/settings/api>`_.
You will need to do some work to obtain OAuth credentials for your users; while outside the scope of this document, please refer to our `OAuth 2 flow documentation <https://developers.coinbase.com/docs/wallet/coinbase-connect>`_.
Once you have these credentials (an ``access_token`` and ``refresh_token``), create a client:

.. code:: python

    from coinbase.wallet.client import OAuthClient
    client = OAuthClient(access_token, refresh_token)

Making API Calls
^^^^^^^^^^^^^^^^

Both the ``Client`` and ``OAuthClient`` support all of the same API calls.
We've included some examples below, but in general the library has Python classes for each of the objects described in our `REST API documentation <https://developers.coinbase.com/api/v2>`_.
These classes each have methods for making the relevant API calls; for instance, ``coinbase.wallet.model.Order.refund`` maps to `the "refund order" API endpoint <https://developers.coinbase.com/api/v2#refund-an-order>`_.
The docstring of each method in the code references the endpoint it implements.

Every method supports the passing of arbitrary parameters via keyword.
These keyword arguments will be sent directly to the relevant endpoint.
If a required parameter is not supplied, the relevant error will be raised.

Each API method returns an ``APIObject`` (a subclass of ``dict``) representing the JSON response from the API, with some niceties like pretty-printing and attr-style item access (``response.foo`` is equivalent to ``response['foo']``). All of the models are dumpable with JSON:

.. code:: python

    user = client.get_current_user()
    user_as_json_string = json.dumps(user)


And, when the response data is parsed into Python objects, the appropriate ``APIObject`` subclasses will be used automatically.
See the code in ``coinbase.wallet.model`` for all of the relevant classes, or the examples below.
API methods that return lists of objects (for instance, ``client.get_accounts()`` return ``APIObject`` instances with nice wrappers around the ``data`` of the response body. These objects support direct indexing and slicing of the list referenced by ``data``.

.. code:: python

    accounts = client.get_accounts()
    assert isinstance(accounts.data, list)
    assert accounts[0] is accounts.data[0]
    assert len(accounts[::]) == len(accounts.data)

But, the ``APIObject`` is not actually a list (it's a subclass of ``dict``) so you cannot iterate through the items of ``data`` directly.
Simple slicing and index access are provided to make common uses easier, but to access the actual list you must reference the ``data`` attribute.

Refreshing
""""""""""
All the objects returned by API methods are subclasses of the ``APIObject`` and support being "refreshed" from the server.
This will update their attributes and all nested data by making a fresh ``GET`` request to the relevant API endpoint:

.. code:: python

    accounts = client.get_accounts()
    # Create a new account via the web UI
    accounts.refresh()
    # Now, the new account is present in the list


Warnings
""""""""
The API V2 `will return relevant *warnings* along with the response data <https://developers.coinbase.com/api/v2#warnings>`_.
In a successful API response, any warnings will be present as a list on the returned ``APIObject``:

.. code:: python

    accounts = client.get_accounts()
    assert (accounts.warnings is None) or isinstance(accounts.warnings, list)

All warning messages will also be alerted using the `Python stdlib warnings module <https://docs.python.org/2/library/warnings.html>`_.

Pagination
""""""""""
Several of the API V2 endpoints `are paginated <https://developers.coinbase.com/api/v2#pagination>`_.
By default, only the first page of data is returned. All pagination data will be present under the ``pagination`` attribute of the returned ``APIObject``:

.. code:: python

    accounts = client.get_accounts()
    assert (accounts.pagination is None) or isinstance(accounts.pagination, dict)


Error Handling
^^^^^^^^^^^^^^

All errors occuring during interaction with the API will be raised as exceptions.
These exceptions will be subclasses of ``coinbase.wallet.error.CoinbaseError``.
When the error involves an API request and/or response, the error will be a subclass of ``coinbase.error.APIError``, and include ``request`` and ``response`` attributes with more information about the failed interaction.
For full details of error responses, please refer `to the relevant API documentation <https://developers.coinbase.com/api/v2#errors>`_.

=============================  ================
Error                          HTTP Status Code
=============================  ================
APIError                       *
TwoFactorRequiredError         402
ParamRequiredError             400
ValidationError                422
InvalidRequestError            400
PersonalDetailsRequiredError   400
AuthenticationError            401
UnverifiedEmailError           401
InvalidTokenError              401
RevokedTokenError              401
ExpiredTokenError              401
InvalidScopeError              403
NotFoundError                  404
RateLimitExceededError         429
InternalServerError            500
ServiceUnavailableError        503
=============================  ================


OAuth Client
^^^^^^^^^^^^

The OAuth client provides a few extra methods to refresh and revoke the access token.

.. code:: python

    # exchange the current access_token and refresh_token for a new pair
    oauth_client.refresh()

This method will update the values stored in the client and return a ``dict`` containing information from the token endpoint so that you can update your records.

.. code:: python

    # revoke the current access_token and refresh_token
    oauth_client.revoke()

*Protip*: You can test OAuth2 authentication easily with Developer Access Tokens which can be created `in your OAuth2 application settings <https://www.coinbase.com/settings/api>`_. These are short lived tokens which authenticate but don't require full OAuth2 handshake to obtain.

Two Factor Authentication
^^^^^^^^^^^^^^^^^^^^^^^^^
Sending money may require the user to supply a 2FA token `in certain situations <https://developers.coinbase.com/docs/wallet/coinbase-connect#two-factor-authentication>`_.
If this is the case, a ``TwoFactorRequiredError`` will be raised:

.. code:: python

    from coinbase.wallet.client import Client
    from coinbase.wallet.error import TwoFactorRequiredError

    client = Client(api_key, api_secret)
    account = client.get_primary_account()
    try:
      tx = account.send_money(to='test@test.com', amount='1', currency='BTC')
    except TwoFactorRequiredError:
      # Show 2FA dialog to user and collect 2FA token
      # two_factor_token = ...
      # Re-try call with the `two_factor_token` parameter
      tx = account.send_money(to='test@test.com', amount='1', currency='BTC', two_factor_token="123456")

`Notifications/Callbacks <https://developers.coinbase.com/docs/wallet/notifications>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Verify notification authenticity**

.. code:: python

    client.verify_callback(request.body, request.META['CB-SIGNATURE']) # true/false

Usage
-----
This is not intended to provide complete documentation of the API.
For more details, `please refer to the official documentation <https://developers.coinbase.com/api/v2>`_.
For more information on the included models and abstractions, please read the code – we've done our best to make it clean, commented, and understandable.

`Market Data <https://developers.coinbase.com/api/v2#data-api>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get supported native currencies**

.. code:: python

    client.get_currencies()

**Get exchange rates**

.. code:: python

    client.get_exchange_rates()

**Buy price**

.. code:: python

    client.get_buy_price(currency_pair = 'BTC-USD')

**Sell price**

.. code:: python

    client.get_sell_price(currency_pair = 'BTC-USD')

**Spot price**

.. code:: python

    client.get_spot_price(currency_pair = 'BTC-USD')

**Current server time**

.. code:: python

    client.get_time()

`Users <https://developers.coinbase.com/api/v2#users>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get authorization info**

.. code:: python

    client.get_auth_info()

**Get user**

.. code:: python

    client.get_user(user_id)

**Get current user**

.. code:: python

    client.get_current_user()

**Update current user**

.. code:: python

    client.update_current_user(name="New Name")
    # or
    current_user.modify(name="New Name")

`Accounts <https://developers.coinbase.com/api/v2#accounts>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get all accounts**

.. code:: python

    client.get_accounts()

**Get account**

.. code:: python

    client.get_account(account_id)

**Get primary account**

.. code:: python

    client.get_primary_account()

**Set account as primary**

.. code:: python

    client.set_primary_account(account_id)
    # or
    account.set_primary()

**Create a new bitcoin account**

.. code:: python

    client.create_account()

**Update an account**

.. code:: python

    client.update_account(account_id, name="New Name")
    # or
    account.modify(name="New Name")

**Delete an account**

.. code:: python

    client.delete_account(account_id)
    # or
    account.delete()

`Addresses <https://developers.coinbase.com/api/v2#addresses>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get receive addresses for an account**

.. code:: python

    client.get_addresses(account_id)
    # or
    account.get_addresses()

**Get a receive address**

.. code:: python

    client.get_address(account_id, address_id)
    # or
    account.get_address(address_id)

**Get transactions for an address**

.. code:: python

    client.get_address_transactions(account_id, address_id)
    # or
    account.get_address_transactions(address_id)

**Create a new receive address**

.. code:: python

    client.create_address(account_id)
    # or
    account.create_address(address_id)

`Transactions <https://developers.coinbase.com/api/v2#transactions>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get transactions**

.. code:: python

    client.get_transactions(account_id)
    # or
    account.get_transactions()

**Get a transaction**

.. code:: python

    client.get_transaction(account_id, transaction_id)
    # or
    account.get_transaction(transaction_id)

**Send money**

.. code:: python

    client.send_money(
        account_id,
        to="3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
        amount="1",
        currency="BTC")
    # or
    account.send_money(to="3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
                       amount="1",
                       currency="BTC")

**Transfer money**

.. code:: python

    client.transfer_money(
        account_id,
        to="<coinbase_account_id>",
        amount="1",
        currency="BTC")
    # or
    account.transfer_money(to="<coinbase_account_id>",
                           amount="1",
                           currency="BTC")

**Request money**

.. code:: python

    client.request_money(
        account_id,
        to="<email_address>",
        amount="1",
        currency="BTC")
    # or
    account.request_money(to="<email_address>",
                          amount="1",
                          currency="BTC")

**Resend request**

.. code:: python

    client.resend_request(account_id, request_id)

**Complete request**

.. code:: python

    client.complete_request(account_id, request_id)

**Cancel request**

.. code:: python

    client.cancel_request(account_id, request_id)

`Reports <https://developers.coinbase.com/api/v2#reports>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get all reports**

.. code:: python

    client.get_reports()

**Get report**

.. code:: python

    client.get_report(report_id)

**Create report**

.. code:: python

    client.create_report(type='transactions', email='sample@example.com')  # types can also be 'orders' or 'transfers'

`Buys <https://developers.coinbase.com/api/v2#buys>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get buys**

.. code:: python

    client.get_buys(account_id)
    # or
    account.get_buys()

**Get a buy**

.. code:: python

    client.get_buy(account_id, buy_id)
    # or
    account.get_buy(buy_id)

**Buy bitcoins**

.. code:: python

    client.buy(account_id, amount='1', currency='BTC')
    # or
    account.buy(amount='1', currency='BTC')

**Commit a buy**

You only need to do this if the initial buy was explicitly uncommitted.

.. code:: python

    buy = account.buy(amount='1', currency='BTC', commit=False)

    client.commit_buy(account_id, buy.id)
    # or
    account.commit_buy(buy.id)
    # or
    buy.commit()

`Sells <https://developers.coinbase.com/api/v2#sells>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get sells**

.. code:: python

    client.get_sells(account_id)
    # or
    account.get_sells()

**Get a sell**

.. code:: python

    client.get_sell(account_id, sell_id)
    # or
    account.get_sell(sell_id)

**Sell bitcoins**

.. code:: python

    client.sell(account_id, amount='1', currency='BTC')
    # or
    account.sell(amount='1', currency='BTC')

**Commit a sell**

You only need to do this if the initial sell was explicitly uncommitted.

.. code:: python

    sell = account.sell(amount='1', currency='BTC', commit=False)

    client.commit_sell(account_id, sell.id)
    # or
    account.commit_sell(sell.id)
    # or
    sell.commit()

`Deposits <https://developers.coinbase.com/api/v2#deposits>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get deposits**

.. code:: python

    client.get_deposits(account_id)
    # or
    account.get_deposits()

**Get a deposit**

.. code:: python

    client.get_deposit(account_id, deposit_id)
    # or
    account.get_deposit(deposit_id)

**Deposit money**

.. code:: python

    client.deposit(account_id, amount='1', currency='USD')
    # or
    account.deposit(amount='1', currency='USD')

**Commit a deposit**

You only need to do this if the initial deposit was explicitly uncommitted.

.. code:: python

    deposit = account.deposit(amount='1', currency='USD', commit=False)

    client.commit_deposit(account_id, deposit.id)
    # or
    account.commit_deposit(deposit.id)
    # or
    deposit.commit()

`Withdrawals <https://developers.coinbase.com/api/v2#withdrawals>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get withdrawals**

.. code:: python

    client.get_withdrawals(account_id)
    # or
    account.get_withdrawals()

**Get a withdrawal**

.. code:: python

    client.get_withdrawal(account_id, withdrawal_id)
    # or
    account.get_withdrawal(withdrawal_id)

**Withdraw money**

.. code:: python

    client.withdraw(account_id, amount='1', currency='USD')
    # or
    account.withdraw(amount='1', currency='USD')

**Commit a withdrawal**

You only need to do this if the initial withdrawal was explicitly uncommitted.

.. code:: python

    withdrawal = account.withdrawal(amount='1', currency='USD', commit=False)

    client.commit_withdrawal(account_id, withdrawal.id)
    # or
    account.commit_withdrawal(withdrawal.id)
    # or
    withdrawal.commit()

`Payment Methods <https://developers.coinbase.com/api/v2#payment-methods>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get payment methods**

.. code:: python

    client.get_payment_methods()

**Get a payment method**

.. code:: python

    client.get_payment_method(payment_method_id)

`Merchants <https://developers.coinbase.com/api/v2#merchants>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get a merchant**

.. code:: python

    client.get_merchant(merchant_id)

`Orders <https://developers.coinbase.com/api/v2#orders>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get orders**

.. code:: python

    client.get_orders()


**Get a order**

.. code:: python

    client.get_order(order_id)

**Create an order**

.. code:: python

    client.create_order(amount='1', currency='BTC', name='Order #1234')

**Refund an order**

.. code:: python

    client.refund_order(order_id)
    # or
    order = client.get_order(order_id)
    order.refund()


`Checkouts <https://developers.coinbase.com/api/v2#checkouts>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Get checkouts**

.. code:: python

    client.get_checkouts()

**Get a checkout**

.. code:: python

    client.get_checkout(checkout_id)

**Create a checkout**

.. code:: python

    client.create_checkout(amount='1', currency='BTC', name='Order #1234')

**Get a checkout's orders**

.. code:: python

    client.get_checkout_orders(checkout_id)
    # or
    checkout = client.get_checkout(checkout_id)
    checkout.get_orders()

**Create an order for a checkout**

.. code:: python

    client.create_checkout_order(checkout_id)
    # or
    checkout = client.get_checkout(checkout_id)
    checkout.create_order()

Testing / Contributing
----------------------

Any and all contributions are welcome!
The process is simple: fork this repo, make your changes, run the test suite, and submit a pull request.
Tests are run via `nosetest <https://nose.readthedocs.org/en/latest/>`_.
To run the tests, clone the repository and then:

.. code:: bash

    # Install the requirements
    pip install -r requirements.txt
    pip install -r test-requirements.txt

    # Run the tests for your current version of Python
    make tests

If you'd also like to generate an HTML coverage report (useful for figuring out which lines of code are actually being tested), make sure the requirements are installed and then run:

.. code:: bash

    make coverage

We use `tox <https://tox.readthedocs.org/en/latest/>`_ to run the test suite against multiple versions of Python.
You can `install tox <http://tox.readthedocs.org/en/latest/install.html>`_ with ``pip`` or ``easy_install``:

.. code:: bash

    pip install tox
    easy_install tox

Tox requires the appropriate Python interpreters to run the tests in different environments.
We recommend using `pyenv <https://github.com/yyuu/pyenv#installation>`_ for this.
Once you've installed the appropriate interpreters, running the tests in every environment is simple:

.. code:: bash

    tox

