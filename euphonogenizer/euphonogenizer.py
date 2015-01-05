#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

import os

import mtags
import titleformat

from args import args, parser
from common import dbg


# TODO(dremelofdeath): Make this whole block a single class.
titleformatter = titleformat.TitleFormatter(args.case_sensitive, args.magic)


def list_mode_handle_track(track, printtrack):
  print(titleformatter.format(printtrack, args.display))


def list_mode_handle_tags(dirpath, tags):
  for track, printable_track in tags.both_tracks():
    list_mode_handle_track(track, printable_track)

def list_mode():
  for dirpath, dirnames, filenames in os.walk(os.getcwd()):
    for tagsfile in [each for each in filenames if each == args.tagsfile]:
      tags = mtags.TagsFile(os.path.join(dirpath, tagsfile))
      list_mode_handle_tags(dirpath, tags)

def main():
  if args.cmd == 'list':
    list_mode()


if __name__ == '__main__':
  main()

