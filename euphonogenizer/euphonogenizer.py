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


class LimitReachedException(Exception):
  pass


class TrackCommand:
  def __init__(self):
    self.records_processed = 0

  def handle_tags(self, dirpath, tags):
    pass

  def run(self):
    try:
      self.records_processed = 0
      for dirpath, dirnames, filenames in os.walk(unicwd()):
        for tagsfile in [each for each in filenames if each == args.tagsfile]:
          tags = mtags.TagsFile(os.path.join(dirpath, tagsfile))
          self.handle_tags(dirpath, tags)
    except LimitReachedException:
      pass


class ListCommand(TrackCommand):
  def handle_track(self, track, **kwargs):
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
    elif 'contains' in kwargs:
      contains = kwargs['contains']
      if 'containsstatic' not in kwargs or not kwargs['contains']:
        contains = titleformatter.format(track, contains)
      if contains in formatted:
        print_output(formatted)
    else:
      print_output(formatted)

  def handle_tags(self, dirpath, tags):
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
    elif args.contains:
      track_params['contains'] = args.contains
      if is_static_pattern(args.contains):
        track_params['containsstatic'] = True
    for track in tags.tracks():
      if self.records_processed == args.limit:
        raise LimitReachedException()
      self.handle_track(track, **track_params)
      self.records_processed += 1


class CopyCommand(TrackCommand):
  def handle_track(self, dirpath, track, **kwargs):
    track_filename = unistr(track.get('@'))
    u_dirpath = unistr(dirpath)
    u_track_filename = unistr(track_filename)
    src = os.path.join(u_dirpath, u_track_filename)
    dst = titleformatter.format(track, args.to)
    if os.path.isfile(dst):
      uniprint('file already exists: ' + dst)
    else:
      uniprint(dst)
      if not args.dry_run:
        if os.path.isfile(src):
          try:
            dirname = os.path.dirname(dst)
            os.makedirs(dirname)
          except OSError:
            pass
          shutil.copy2(src, dst)

  def handle_tags(self, dirpath, tags):
    for track in tags.tracks():
      if self.records_processed == args.limit:
        raise LimitReachedException()
      self.handle_track(dirpath, track)
      self.records_processed += 1


def main():
  if args.cmd == 'list':
    ListCommand().run()
  elif args.cmd == 'copy':
    CopyCommand().run()


if __name__ == '__main__':
  main()

