#!/usr/bin/python
# -*- coding: utf-8 -*-

import chardet
import codecs
import simplejson
import sys

from .common import compat_iteritems


class TagsFile:
  def __init__(self, filenameorlist):
    if isinstance(filenameorlist, list):
      self.tracks = filenameorlist
    else:
      with open(filenameorlist, 'rb') as tags:
        tbytes = tags.read()
        tagsjson = simplejson.loads(
            tbytes, encoding=chardet.detect(tbytes)['encoding'])
        self._process_saturated_tags(tagsjson)

  def _process_saturated_tags(self, tagsjson):
    self.tracks = []
    saturated_tags = {}

    for track in tagsjson:
      for tag_field, value in compat_iteritems(track):
        if value == []:
          # This is, strangely, how the M-TAGS format erases values
          del saturated_tags[tag_field]
        else:
          saturated_tags[tag_field] = value

      self.tracks.append(saturated_tags.copy())

  def desaturate(self):
    desaturated = []
    if self.tracks:
      last_saturated_tags = {}
      for track in self.tracks:
        current_desaturated = {}
        for tag_field, value in compat_iteritems(track):
          if tag_field in last_saturated_tags:
            if value != last_saturated_tags[tag_field]:
              current_desaturated[tag_field] = value
          else:
            current_desaturated[tag_field] = value

        for tag_field, value in compat_iteritems(last_saturated_tags):
          if tag_field not in track:
            current_desaturated[tag_field] = []

        last_saturated_tags = track
        desaturated.append(current_desaturated)
    return desaturated

  def write(self, filename):
    with codecs.open(filename, 'w', encoding='utf-8-sig') as fp:
      simplejson.dump(self.desaturate(), fp,
          ensure_ascii=False, sort_keys=True, indent=3, separators=(',', ' : '))
      fp.write('\n')
