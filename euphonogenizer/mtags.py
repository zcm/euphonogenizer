#!/usr/bin/python
# -*- coding: utf-8 -*-

import simplejson
import sys


class TrackListing:
  def __init__(self, dict_obj):
    self._dict_obj = dict_obj

  def __contains__(self, key):
    return key in self._dict_obj

  def get(self, key):
    return self._dict_obj.get(key)


class PrintableTrackListing:
  def __init__(self, track_listing):
    self.track_listing = track_listing

  def __contains__(self, key):
    return key in self.track_listing

  def get(self, key):
    track_string = self.track_listing.get(key)
    if track_string is None:
      return None
    return track_string.encode(sys.stdout.encoding, errors='replace')


class TagsFile:
  def __init__(self, filename):
    with open(filename) as tags:
      tagsjson = simplejson.load(tags)
      self._process_saturated_tags(tagsjson)

  def _process_saturated_tags(self, tagsjson):
    self._tracks = []
    saturated_tags = {}

    for track in tagsjson:
      for tag_field, value in track.iteritems():
        if value == []:
          # This is, strangely, how the M-TAGS format erases values
          del saturated_tags[tag_field]
        else:
          saturated_tags[tag_field] = value

      self._tracks.append(saturated_tags.copy())

  def tracks(self):
    for each in self._tracks:
      yield TrackListing(each)

  def printable_tracks(self):
    for each in self.tracks():
      yield PrintableTrackListing(each)

  def both_tracks(self):
    for each in self._tracks:
      current_track = TrackListing(each)
      yield (current_track, PrintableTrackListing(current_track))

