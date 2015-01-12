#!/usr/bin/python
# -*- coding: utf-8 -*-

import codecs
import simplejson
import sys


class TagsFile:
  def __init__(self, filenameorlist):
    if isinstance(filenameorlist, list):
      self._tracks = filenameorlist
    else:
      with open(filenameorlist) as tags:
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
      yield each

  def desaturate(self):
    desaturated = []
    if self._tracks:
      last_saturated_tags = {}
      for track in self._tracks:
        current_desaturated = {}
        for tag_field, value in track.iteritems():
          if tag_field in last_saturated_tags:
            if value != last_saturated_tags[tag_field]:
              current_desaturated[tag_field] = value
          else:
            current_desaturated[tag_field] = value
        for tag_field, value in last_saturated_tags.iteritems():
          if tag_field not in track:
            current_desaturated[tag_field] = []
        last_saturated_tags = track
        desaturated.append(current_desaturated)
    return desaturated

  def write(self, filename):
    with codecs.open(filename, 'w', encoding='utf-8-sig') as fp:
      simplejson.dump(self.desaturate(), fp,
          sort_keys=True, indent=3, separators=(',', ' : '))
      fp.write('\n')
