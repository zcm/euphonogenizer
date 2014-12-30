#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import os
import simplejson


class TagsFile:
  def __init__(self, filename):
    with open(filename) as tags:
      tagsjson = simplejson.load(tags)
      self.tracks = []

      saturated_tags = {}

      for track in tagsjson:
        for tag_field, value in track.iteritems():
          if value == []:
            # This is, strangely, how the M-TAGS format erases values
            del saturated_tags[tag_field]
          else:
            saturated_tags[tag_field] = value

        self.tracks.append(saturated_tags.copy())


def main():
  for dirpath, dirnames, filenames in os.walk(os.getcwd()):
    for tagsfile in [each for each in filenames if each == "!.tags"]:
      tags = TagsFile(os.path.join(dirpath, tagsfile))
      print dirpath + ":"
      for track in tags.tracks:
        if 'ARTIST' in track and 'TITLE' in track:
          print "  " + track.get('ARTIST') + " - " + track.get('TITLE')



# vim:ts=2:sw=2:et:ai
