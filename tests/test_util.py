# coding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest2

from coinbase.wallet.util import clean_params

class TestUtils(unittest2.TestCase):
  def test_clean_params(self):
    input = {
        'none': None,
        'int': 1,
        'float': 2.0,
        'bool': True,
        'nested': {
          'none': None,
          'int': 1,
          'float': 2.0,
          'bool': False,
        },
      }

    self.assertEqual(clean_params(input), {
      'int': 1,
      'float': 2.0,
      'bool': True,
      'nested': {
        'int': 1,
        'float': 2.0,
        'bool': False,
      },
    })
    self.assertEqual(clean_params(input, drop_nones=False), {
      'none': None,
      'int': 1,
      'float': 2.0,
      'bool': 1,
      'nested': {
        'none': None,
        'int': 1,
        'float': 2.0,
        'bool': 0,
      },
    })
    self.assertEqual(clean_params(input, recursive=False), {
      'int': 1,
      'float': 2.0,
      'bool': 1,
      'nested': {
        'none': None,
        'int': 1,
        'float': 2.0,
        'bool': 0,
      },
    })
