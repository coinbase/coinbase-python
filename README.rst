Coinbase
========

.. image:: https://pypip.in/version/coinbase/badge.svg?style=flat
    :target: https://pypi.python.org/pypi/coinbase

.. image:: https://img.shields.io/travis/coinbase/coinbase-python/master.svg?style=flat
    :target: https://travis-ci.org/coinbase/coinbase-python

.. image:: https://pypip.in/download/coinbase/badge.svg?style=flat
    :target: https://pypi.python.org/pypi/coinbase/

.. image:: https://pypip.in/wheel/blackhole/badge.svg?style=flat
    :target: https://pypi.python.org/pypi/coinbase/

.. image:: https://pypip.in/py_versions/coinbase/badge.svg?style=flat
    :target: https://pypi.python.org/pypi/coinbase/

.. image:: https://pypip.in/license/blackhole/badge.svg?style=flat
    :target: https://pypi.python.org/pypi/coinbase/

The official Python library for the `Coinbase API
<https://developers.coinbase.com/api>`_.

Features
--------

* Near-100% test coverage.
* Support for both `API Key + Secret
  <https://coinbase.com/docs/api/authentication#hmac>`_ and `OAuth 2
  <https://coinbase.com/docs/api/authentication#oauth2>`_ authentication.
* Convenient methods for making calls to the API - packs JSON for you!
* Automatic parsing of API responses into relevant Python objects.
* All objects have tab-completable methods and attributes when using
  `IPython <http://ipython.org>`_.


Installation
------------

`coinbase` is available on `PYPI <https://pypi.python.org/pypi/coinbase/>`_.
Install with ``pip``:

.. code:: bash

    pip install coinbase

or with ``easy_install``:

.. code:: bash

    easy_install coinbase

The library is currently tested against Python versions 2.6.9, 2.7.9, 3.2,
3.3.6, and 3.4.2.


Quick Start
-------------

The first thing you'll need to do is `sign up for coinbase
<https://coinbase.com>`_.

API Key + Secret
^^^^^^^^^^^^^^^^

If you're writing code for your own Coinbase account, `enable an API key
<https://coinbase.com/settings/api>`_. Next, create a ``Client`` object for
interacting with the API:

.. code:: python

    from coinbase.client import Client
    client = Client(api_key, api_secret)

OAuth2
^^^^^^

If you're writing code that will act on behalf of another user, start by
`creating a new OAuth 2 application <https://coinbase.com/oauth/applications>`_.
You will need to do some work to obtain OAuth credentials for your users; while
outside the scope of this document, please refer to our `OAuth 2 tutorial
<https://www.coinbase.com/docs/api/oauth_tutorial>`_ and `documentation
<https://www.coinbase.com/docs/api/authentication#oauth2>`_. Once you have
these credentials, create a client:

.. code:: python

    from coinbase.client import OAuthClient
    client = OAuthClient(client_id, client_secret, access_token, refresh_token)

Making API Calls
^^^^^^^^^^^^^^^^

With a `Client`, you can now make API calls. We've included some examples
below, but in general the library has Python classes for each of the objects
described in our `REST API documentation
<https://developers.coinbase.com/api>`_.  These classes each have methods for
making the relevant API calls; for instance,
``coinbase.model.Transaction.complete`` maps to `the "complete bitcoin request"
API endpoint <https://developers.coinbase.com/api#complete-bitcoin-request>`_.
The docstring of each method in the code references the endpoint it implements.
Each API method returns a ``dict`` subclass representing the JSON response from
the API, with some niceties like pretty-printing and attr-style item access
(``response.data`` is equiivalent to ``response['data']``).

**Listing available accounts**

.. code:: python

    accounts = client.get_accounts()

**Buying bitcoin**

.. code:: python

    wallet = client.get_account('54a710dd25dc9a311800003f')
    
    # Buy 1 BTC using the default payment method
    wallet.buy('1.0')

    # Buy 1 BTC using a specific payment method
    credit_card = client.get_payment_method('54a710de25dc9a311800006e')
    wallet.buy('1.0', payment_method_id=credit_card.id)


**Selling bitcoin**

.. code:: python

    wallet = client.get_account('54a710dd25dc9a311800003f')
    
    # Sell 1 BTC using the default payment method
    wallet.sell('1.0')

    # Sell 1 BTC using a specific payment method
    bank = client.get_payment_method('9aaa10de25dca28e2118001999')
    wallet.sell('1.0', payment_method_id=bank.id)


**Sending bitcoin**

.. code:: python

    wallet = client.get_account('54a710dd25dc9a311800003f')
    vault = wallet.get_account('54a710dd25dc9a3118000040')
    # Send 1 BTC from your wallet to vault
    tx = wallet.send_money(vault.id, '1')
    
    # Send 10 USD to someone by email address
    tx = wallet.send_money(
        'satoshi@example.com',
        amount_string='10.00',
        amount_currency_iso='USD')

**Requesting bitcoin**

.. code:: python

    wallet = client.get_account('54a710dd25dc9a311800003f')
    # Request 10 BTC from a client
    tx = wallet.request_money(
        'client@example.com',
        '10',
        notes='Contractor hours in January (website redesign for 10 BTC)')

    # Request $500 USD from a roommate
    tx = wallet.request_money(
        'roommate@example.com',
        amount_string='500.00',
        amount_currency_iso='USD',
        notes='Return for January 2015')


**Listing current transactions**

.. code:: python

    account = client.get_account()
    transactions = account.get_transactions()

**Checking bitcoin prices**

.. code:: python

    buy_data = client.get_buy_price()
    sell_data = client.get_sell_price()
    spot_data = client.get_spot_price()


Error Handling
^^^^^^^^^^^^^^

All errors occuring during interaction with the API will be raise as
exceptions.  These exceptions will be subclasses of
``coinbase.error.CoinbaseError``. When the error involves an API request and/or
response, the error will be a subclass of ``coinbase.error.APIError``, and
include ``request`` and ``response`` attributes with more information about the
failed interaction.

OAuth Access Token Refreshing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When using the ``coinbase.client.OAuthClient``, the access token being used
to authenticate you may expire. Should this happen, a ``coinbase.error.ExpiredAccessToken``
exception will be raised. The ``coinbase.client.OAuthClient`` provides a convenient
helper method for refreshing the access token:

.. code:: python

    new_token_data = oauth_client.refresh()

This method will update the values stored in the client and return a ``dict`` containing information from the token endpoint so that you can update your records.

.. code:: javascript

    {
      'access_token': '405237b48b0d8bddd24856c208103aa53df5bf3d8118ed459396bd1974a33dbf',
      'expires_in': 7200,
      'refresh_token': 'b96ad9e737d6109e62f29a69342a8e837863098774f83b759bbf46fb4bc493ed',
      'scope': 'merchant balance addresses buttons buy contacts orders sell transactions request transfer transfers user send',
      'token_type': 'bearer',
    }


Testing / Contributing
----------------------

Any and all contributions are welcome! The process is simple: fork this repo,
make your changes, run the test suite, and submit a pull request.  Tests are
run via `nosetest`. To run the tests, clone the repository and then:

.. code:: bash

    # Install the requirements
    pip install -r requirements.txt
    pip install -r test-requirements.txt
    
    # Run the tests for your current version of Python
    make tests

If you'd also like to generate an HTML coverage report (useful for figuring out
which lines of code are actually being tested), make sure the requirements are
installed and then run:

.. code:: bash

    make coverage

We use `tox <https://tox.readthedocs.org/en/latest/>`_ to run the test suite
against multiple versions of Python. You can `install tox
<http://tox.readthedocs.org/en/latest/install.html>`_ with ``pip`` or
``easy_install``:

.. code:: bash

    pip install tox
    easy_install tox

Tox requires the appropriate Python interpreters to run the tests in different
environments. We recommend using `pyenv
<https://github.com/yyuu/pyenv#installation>`_ for this. Once you've installed
the appropriate interpreters, running the tests in each environment is simple:

.. code:: bash

    tox
