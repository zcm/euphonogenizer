#!/usr/bin/python
# -*- coding: utf-8 -*-

import os

import mtags
import titleformat

from args import args
from common import dbg


# TODO(dremelofdeath): Make this whole block a single class.
titleformatter = titleformat.TitleFormatter(args.case_sensitive)


def handle_track(track, printtrack):
  if 'ARTIST' in track and 'TITLE' in track:
    print(titleformatter.format(printtrack, args.pattern))


def handle_tags(dirpath, tags):
  print(dirpath + ':')
  for track, printable_track in tags.both_tracks():
    handle_track(track, printable_track)


def main():
  for dirpath, dirnames, filenames in os.walk(os.getcwd()):
    for tagsfile in [each for each in filenames if each == args.tagsfile]:
      tags = mtags.TagsFile(os.path.join(dirpath, tagsfile))
      handle_tags(dirpath, tags)


# vim:ts=2:sw=2:et:ai
