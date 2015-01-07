#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys


progname = 'euphonogenizer'


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

def uniprint(message):
  print(message.encode(sys.stdout.encoding, errors='replace'))

def unistr(s):
  if sys.version_info[0] < 3:
    return eval('unicode(s)')
  return str(s)

