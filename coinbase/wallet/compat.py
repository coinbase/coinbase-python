# coding: utf-8
import six
if six.PY2:
    from itertools import imap
    from urllib import quote
    from urlparse import urljoin, urlsplit
    from urlparse import urlparse
elif six.PY3:
    imap = map
    from urllib.parse import quote
    from urllib.parse import urljoin, urlsplit
    from urllib.parse import urlparse
