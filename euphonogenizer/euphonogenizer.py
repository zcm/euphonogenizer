#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

import os
import shutil
import sys

import mtags
import titleformat

from args import args, parser
from common import dbg, err, unicwd, uniprint, unistr


# TODO(dremelofdeath): Make this whole block a single class.
titleformatter = titleformat.TitleFormatter(args.case_sensitive, args.magic)

unique_output = set()

def really_print_output(output):
  print(output.encode(sys.stdout.encoding, errors='replace'))

def print_output(output):
  if args.unique:
    if output not in unique_output:
      unique_output.add(output)
      really_print_output(output)
  else:
    really_print_output(output)

def is_static_pattern(pattern):
  formatted = titleformatter.format({}, pattern)
  return pattern == formatted

def list_mode_handle_track(track, **kwargs):
  formatted = titleformatter.format(track, args.display)
  if 'startswith' in kwargs:
    startswith = kwargs['startswith']
    if 'startswithstatic' not in kwargs or not kwargs['startswithstatic']:
      startswith = titleformatter.format(track, startswith)
    if formatted.startswith(startswith):
      print_output(formatted)
  elif 'equals' in kwargs:
    equals = kwargs['equals']
    if 'equalsstatic' not in kwargs or not kwargs['equalsstatic']:
      equals = titleformatter.format(track, equals)
    if formatted == equals:
      print_output(formatted)
  else:
    print_output(formatted)

def list_mode_handle_tags(dirpath, tags):
  startswith = False
  track_params = {}
  if args.startswith:
    track_params['startswith'] = args.startswith
    if is_static_pattern(args.startswith):
      track_params['startswithstatic'] = True
  elif args.equals:
    track_params['equals'] = args.equals
    if is_static_pattern(args.equals):
      track_params['equalsstatic'] = True
  for track in tags.tracks():
    list_mode_handle_track(track, **track_params)

def list_mode():
  return tags_for_each(list_mode_handle_tags)

def print_copy_info(src, dst):
  uniprint('%s ==> %s' % (src, dst))

def copy_mode_handle_track(dirpath, track, **kwargs):
  track_filename = unistr(track.get('@'))
  u_dirpath = unistr(dirpath)
  u_track_filename = unistr(track_filename)
  src = os.path.join(u_dirpath, u_track_filename)
  dst = titleformatter.format(track, args.to)
  print_copy_info(src, dst)

def copy_mode_handle_tags(dirpath, tags):
  for track in tags.tracks():
    copy_mode_handle_track(dirpath, track)

def copy_mode():
  return tags_for_each(copy_mode_handle_tags)

def tags_for_each(handler):
  for dirpath, dirnames, filenames in os.walk(unicwd()):
    for tagsfile in [each for each in filenames if each == args.tagsfile]:
      tags = mtags.TagsFile(os.path.join(dirpath, tagsfile))
      handler(dirpath, tags)

def main():
  if args.cmd == 'list':
    list_mode()
  elif args.cmd == 'copy':
    copy_mode()


if __name__ == '__main__':
  main()

