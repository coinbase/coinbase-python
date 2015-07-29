# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import copy
import json
import six
import unittest2
import warnings

from coinbase.wallet.model import APIObject
from coinbase.wallet.model import new_api_object


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
    'resource': 'foo',
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

class TestNewApiObject(unittest2.TestCase):
  def test_new_api_object(self):
    api_client = lambda x: x
    obj = new_api_object(api_client, simple_data)
    self.assertIsInstance(obj, APIObject)
    self.assertIsNone(obj.response)
    self.assertIsNone(obj.pagination)
    self.assertIsNone(obj.warnings)

    response = lambda x: x
    pagination = lambda x: x
    warnings = lambda x: x
    obj = new_api_object(
        api_client, simple_data, response=response, pagination=pagination,
        warnings=warnings)
    self.assertIs(obj.response, response)
    self.assertIs(obj.pagination, pagination)
    self.assertIs(obj.warnings, warnings)

  def test_new_api_object_uses_cls_if_available(self):
    api_client = lambda x: x
    class Foo(APIObject): pass
    obj = new_api_object(api_client, simple_data, cls=Foo)
    self.assertIsInstance(obj, Foo)
    self.assertNotIsInstance(obj.obj, Foo)

  def test_new_api_object_guesses_based_on_resource_field(self):
    api_client = lambda x: x
    class Foo(APIObject): pass
    import coinbase.wallet.model
    # Preserve the inital values so that they can be restored after modifying
    # them for this test; otherwise, the modified versions will persist for
    # other tests.
    original = coinbase.wallet.model._resource_to_model
    coinbase.wallet.model._resource_to_model = {
        'foo': Foo,
      }
    obj = new_api_object(api_client, simple_data)
    self.assertIsInstance(obj, Foo)
    coinbase.wallet.model._resource_to_model = original

  def test_new_api_object_guesses_based_on_keys(self):
    api_client = lambda x: x
    class Foo(APIObject): pass
    import coinbase.wallet.model
    # Preserve the inital values so that they can be restored after modifying
    # them for this test; otherwise, the modified versions will persist for
    # other tests.
    original = coinbase.wallet.model._obj_keys_to_model
    coinbase.wallet.model._obj_keys_to_model = {
        frozenset(('str', 'foo')): Foo,
      }
    simple_obj = new_api_object(api_client, simple_data)
    self.assertIsInstance(simple_obj, Foo)
    self.assertIsInstance(simple_obj['obj'], Foo)
    for obj in simple_obj['list_of_objs']:
      self.assertNotIsInstance(obj, Foo)
    coinbase.wallet.model._obj_keys_to_model = original

  def test_new_api_object_transforms_types_appropriately(self):
    api_client = lambda x: x
    simple_obj = new_api_object(api_client, simple_data)

    # Check root level for dict -> APIObject transformation.
    self.assertIsInstance(simple_data['obj'], dict)
    self.assertIsInstance(simple_obj['obj'], APIObject)

    # Check the second level for dict -> APIObject transformation.
    self.assertIsInstance(simple_data['obj']['obj'], dict)
    self.assertIsInstance(simple_obj['obj']['obj'], APIObject)

    # Check lists for dict -> APIObject transformation
    self.assertIsInstance(simple_data['list_of_objs'], list)
    self.assertIsInstance(simple_obj['list_of_objs'], list)
    for item in simple_data['list_of_objs']:
      self.assertIsInstance(item, dict)
    for item in simple_obj['list_of_objs']:
      self.assertIsInstance(item, APIObject)

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

  def test_new_api_object_preserves_api_client(self):
    api_client = lambda x: x
    simple_obj = new_api_object(api_client, simple_data)
    # Check that all sub API objects have the same API client as the root.
    self.assertIs(simple_obj.api_client, api_client)
    self.assertIs(simple_obj['obj'].api_client, api_client)
    for thing in simple_obj['list_of_objs']:
      self.assertIs(thing.api_client, api_client)

  def test_attr_access(self):
    api_client = lambda x: x
    # Every key in the object should be accessible by attribute access.
    simple_obj = new_api_object(api_client, simple_data)
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
    data_obj = new_api_object(None, data)
    assert hasattr(data_obj, 'refresh')
    assert 'refresh' not in data_obj
    with self.assertRaises(KeyError):
      data_obj['refresh']

    # Setting attributes that begin with a '_' are not available via __getitem__
    data_obj._test = True
    self.assertEqual(getattr(data_obj, '_test', None), True)
    self.assertEqual(data_obj.get('_test', None), None)

    # Setting attribuets that don't begin with a '_' are available via __getitem__
    data_obj.test = True
    self.assertEqual(getattr(data_obj, 'test', None), True)
    self.assertEqual(data_obj.get('test', None), True)


  def test_json_serialization(self):
    api_client = lambda x: x
    simple_obj = new_api_object(api_client, simple_data)

    # APIObjects should be equivalent to the dicts from which they were loaded.
    self.assertEqual(simple_obj, simple_data)

    # APIObjects should be JSON-serializable; the serialized version should be
    # identical to the serialized version of the data from which the object
    # was originally created.
    json_data = json.dumps(simple_data, sort_keys=True)
    json_obj = json.dumps(simple_obj, sort_keys=True)
    self.assertEqual(json_data, json_obj)

    # Two APIObjects created from the same data should be equivalent.
    simple_obj2 = new_api_object(api_client, simple_data)
    self.assertEqual(simple_obj, simple_obj2)

    # When an object is unserializable, it should still be convertible to a
    # string.
    from decimal import Decimal
    broken_obj = new_api_object(api_client, {'cost': Decimal('12.0')})
    self.assertTrue(str(broken_obj).endswith('(invalid JSON)'))

  def test_paged_data_value(self):
    api_client = lambda x: x
    # When the 'data' attribute is a list, slicing and indexing the APIObject
    # looks into the list.
    data = copy.copy(simple_data)
    data['data'] = data.pop('list_of_objs')
    simple_obj = new_api_object(api_client, data)
    print(simple_obj)

    self.assertEqual(simple_obj[0], simple_obj['data'][0])
    self.assertEqual(simple_obj[::], simple_obj['data'])
    self.assertEqual(simple_obj[::-1], simple_obj['data'][::-1])

    simple_obj2 = new_api_object(api_client, simple_data)
    with self.assertRaises(KeyError):
      simple_obj2[0]
