#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys


def dbg(message, depth=0):
  output = '[dbg] ' + ' ' * depth * 2 + message
  print(output.encode(sys.stdout.encoding, errors='replace'))

def unistr(s):
  if sys.version_info[0] < 3:
    return eval('unicode(s)')
  return str(s)

