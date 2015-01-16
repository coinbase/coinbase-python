# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import six
import unittest2
import warnings

from coinbase.model import APIObject


# Dummy API key values for use in tests
api_key = 'fakeapikey'
api_secret = 'fakeapisecret'

# Hide all warning output.
warnings.showwarning = lambda *a, **k: None

simple_data = {
    'str': 'bar',
    'foo': 'bar',
    'int': 21,
    'float': 21.0,
    'bool': False,
    'none': None,
    'list': [1, 2, 3],
    'obj': {
      'str': 'bar1',
      'foo': 'bar',
      'obj': {
        'str': 'bar2',
      },
    },
    'list_of_objs': [
      {'str': 'one'},
      {'str': 'two'},
      {'str': 'three'},
    ],
  }

class TestApiObject(unittest2.TestCase):
  def test_load_returns_api_object(self):
    api_client = lambda x: x
    root = APIObject(api_client)
    obj = root.load(simple_data)
    self.assertIsInstance(obj, APIObject)

  def test_load_transforms_types_appropriately(self):
    api_client = lambda x: x
    root = APIObject(api_client)
    simple_obj = root.load(simple_data)

    # Check root level for dict -> APIObject transformation.
    self.assertIsInstance(simple_data['obj'], dict)
    self.assertIsInstance(simple_obj['obj'], APIObject)

    # Check the second level for dict -> APIObject transformation.
    self.assertIsInstance(simple_data['obj']['obj'], dict)
    self.assertIsInstance(simple_obj['obj']['obj'], APIObject)

    # Check lists for dict -> APIObject transformation
    self.assertIsInstance(simple_data['list_of_objs'], list)
    assert all(map(lambda obj: isinstance(obj, dict),
                   simple_data['list_of_objs']))
    self.assertIsInstance(simple_obj['list_of_objs'], list)
    assert all(map(lambda obj: isinstance(obj, APIObject),
                   simple_obj['list_of_objs']))

    # Check that non-dict/list values are left the same.
    self.assertIsInstance(simple_data['str'], six.string_types)
    self.assertIsInstance(simple_obj['str'], six.string_types)

    self.assertIsInstance(simple_data['int'], int)
    self.assertIsInstance(simple_obj['int'], int)
    self.assertIsInstance(simple_data['float'], float)
    self.assertIsInstance(simple_obj['float'], float)
    self.assertIsInstance(simple_data['bool'], bool)
    self.assertIsInstance(simple_obj['bool'], bool)
    self.assertIsNone(simple_data['none'])
    self.assertIsNone(simple_obj['none'])

  def test_load_preserves_api_client(self):
    api_client = lambda x: x

    # Check that the property works as expected.
    root = APIObject(api_client)
    self.assertIs(root.api_client, api_client)

    # Check that all API objects created by the root have the same API client
    # as the root.
    simple_obj = root.load(simple_data)
    assert simple_obj.api_client is api_client
    assert simple_obj['obj'].api_client is api_client
    assert all(map(lambda obj: obj.api_client is api_client,
                   simple_obj['list_of_objs']))

    # Check that all API objects created by objects created by the root have
    # the same API client as the root.
    test_obj = simple_obj.load({'foo': 'bar'})
    assert test_obj.api_client is api_client


  def test_load_preserves_account(self):
    api_client = lambda x: x
    account = lambda y: y

    # Check that the property works as expected.
    root = APIObject(api_client, account=account)
    assert root.account is account

    # Check that all API objects created by the root have the same account as
    # the root.
    simple_obj = root.load(simple_data)
    assert simple_obj.account is account
    assert simple_obj['obj'].account is account
    assert all(map(lambda obj: obj.account is account,
                   simple_obj['list_of_objs']))

    # Check that all API objects created by objects created by the root have
    # the same account as the root.
    test_obj = simple_obj.load({'foo': 'bar'})
    assert test_obj.account is account

  def test_attr_access(self):
    api_client = lambda x: x
    root = APIObject(api_client)

    # Every key in the object should be accessible by attribute access.
    simple_obj = root.load(simple_data)
    for key, value in simple_obj.items():
      assert (key in simple_obj) and hasattr(simple_obj, key)
      assert getattr(simple_obj, key) is simple_obj[key]

    # If a key is not in the object, it should not be accessible by attribute
    # access. It should raise AttributeError when access is attempted by
    # attribute instead of by key.
    broken_key = 'notindata'
    assert broken_key not in simple_obj
    assert not hasattr(simple_obj, broken_key)
    with self.assertRaises(KeyError):
      simple_obj[broken_key]
    with self.assertRaises(AttributeError):
      getattr(simple_obj, broken_key)
    with self.assertRaises(KeyError):
      del simple_obj[broken_key]
    with self.assertRaises(AttributeError):
      delattr(simple_obj, broken_key)

    # Methods on the object should not be accessible via key.
    data = {'foo': 'bar'}
    data_obj = root.load(data)
    assert hasattr(data_obj, 'load')
    assert 'load' not in data_obj
    with self.assertRaises(KeyError):
      data_obj['load']


  def test_json_serialization(self):
    api_client = lambda x: x
    root = APIObject(api_client)
    simple_obj = root.load(simple_data)

    # APIObjects should be equivalent to the dicts from which they were loaded.
    self.assertEqual(simple_obj, simple_data)

    # APIObjects should be JSON-serializable; the serialized version should be
    # identical to the serialized version of the data from which the object
    # was originally created.
    json_data = json.dumps(simple_data, sort_keys=True)
    json_obj = json.dumps(simple_obj, sort_keys=True)
    self.assertEqual(json_data, json_obj)

    # Two APIObjects created from the same data should be equivalent.
    simple_obj2 = root.load(simple_data)
    self.assertEqual(simple_obj, simple_obj2)

    # When an object is unserializable, it should still be convertible to a
    # string.
    from decimal import Decimal
    broken_obj = root.load({'cost': Decimal('12.0')})
    self.assertTrue(str(broken_obj).endswith('(invalid JSON)'))


  def test_paged_key(self):
    api_client = lambda x: x
    root = APIObject(api_client)
    simple_obj = root.load(simple_data, paged_key='list_of_objs')

    self.assertEqual(simple_obj[0], simple_obj['list_of_objs'][0])
    self.assertEqual(simple_obj[::], simple_obj['list_of_objs'])
    self.assertEqual(simple_obj[::-1], simple_obj['list_of_objs'][::-1])

    simple_obj2 = root.load(simple_data, paged_key='key_does_not_exist')
    with self.assertRaises(KeyError):
      simple_obj2[0]

    simple_obj3 = root.load(simple_data)
    with self.assertRaises(KeyError):
      simple_obj3[0]

  def test_model_lookup(self):
    import coinbase.model
    class DummyModel(APIObject): pass
    api_client = lambda x: x
    root = APIObject(api_client)

    # Preserve the inital values so that they can be restored after modifying
    # them for this test; otherwise, the modified versions will persist for
    # other tests.
    obj_keys_to_model = coinbase.model._obj_keys_to_model
    key_to_model = coinbase.model._key_to_model

    # Check to make sure that key lookup works.
    coinbase.model._obj_keys_to_model = {}
    coinbase.model._key_to_model = {
        'obj': DummyModel,
        'list_of_objs': DummyModel,
      }
    simple_obj = root.load(simple_data)
    self.assertIsInstance(simple_obj['obj'], DummyModel)
    for obj in simple_obj['list_of_objs']:
      self.assertIsInstance(obj, DummyModel)

    coinbase.model._key_to_model = {}
    coinbase.model._obj_keys_to_model = {
        frozenset(('str', 'foo')): DummyModel,
      }
    simple_obj = root.load(simple_data)
    self.assertIsInstance(simple_obj, DummyModel)
    self.assertIsInstance(simple_obj['obj'], DummyModel)
    for obj in simple_obj['list_of_objs']:
      self.assertNotIsInstance(obj, DummyModel)

    # Restore original values.
    coinbase.model._obj_keys_to_model = obj_keys_to_model
    coinbase.model._key_to_model = key_to_model
