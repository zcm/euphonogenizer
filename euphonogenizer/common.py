#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function

import os
import stat
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
    try:
      sys.stdout.buffer.write(
          message.encode(sys.stdout.encoding, errors='replace'))
      print('', end=end)
    except AttributeError:
      print(message.encode(sys.stdout.encoding, errors='replace'), end=end)
  else:
    try:
      sys.stdout.buffer.write(message.encode('ascii', errors='replace'))
      print('', end=end)
    except AttributeError:
      print(message.encode('ascii', errors='replace'), end=end)

def unistr(s):
  if sys.version_info[0] < 3:
    return eval('unicode(s)')
  return str(s)

def write_with_override(filename, do_write, override=True):
  should_override = override

  try:
    should_override = override()
  except TypeError:
    pass

  try:
    do_write()
  except IOError:
    # This is probably due to the read-only flag being set, so check it.
    if should_override:
      if not os.access(filename, os.W_OK):
        # We will just clear the flag temporarily and then set it back.
        mode = os.stat(filename)[stat.ST_MODE]
        os.chmod(filename, stat.S_IWRITE)
        do_write()
        os.chmod(filename, mode)
      else:
        # Something else bad is happening then.
        raise
    else:
      # We're not going to force it. The file isn't writable, so skip it.
      raise
