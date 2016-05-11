#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function

import os
import sys


progname = 'euphonogenizer'

def compat_iteritems(obj):
  try:
    return obj.iteritems()
  except AttributeError:
    return obj.items()

def dbg(message, depth=0):
  output = '[dbg] ' + ' ' * depth * 2 + message
  uniprint(output)

def err(message):
  output = progname + ': error: ' + message
  uniprint(output)

def unicwd():
  if sys.version_info[0] < 3:
    return eval('os.getcwdu()')
  return os.getcwd()

def uniprint(message, end=None):
  if end is None:
    end = os.linesep

  if sys.stdout.encoding:
    sys.stdout.buffer.write(
            message.encode(sys.stdout.encoding, errors='replace'))
  else:
    sys.stdout.buffer.write(message.encode('ascii', errors='replace'))

  print('', end=end)

def unistr(s):
  if sys.version_info[0] < 3:
    return eval('unicode(s)')
  return str(s)

