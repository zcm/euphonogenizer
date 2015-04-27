#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

import mutagen.id3

from mutagen._compat import iteritems
from mutagen.easyid3 import EasyID3
from mutagen.easyid3 import EasyID3KeyError


is_configured = False


def url_frame_get(frameid, id3, key):
  urls = [frame.url for frame in id3.getall(frameid)]
  if urls:
    return urls
  else:
    raise EasyID3KeyError(key)

def url_frame_set(frameid, id3, key, value):
  id3.delall(frameid)
  for v in value:
    id3.add(getattr(mutagen.id3, frameid)(url=v))

def url_frame_delete(frameid, unused_id3, unused_key):
  id3.delall(frameid)

def get_url_frame_get_closure(frameid):
  return lambda id3, key: url_frame_get(frameid, id3, key)

def get_url_frame_set_closure(frameid):
  return lambda id3, key, value: url_frame_set(frameid, id3, key, value)

def get_url_frame_delete_closure(frameid):
  return lambda id3, key: url_frame_delete(frameid, id3, key)

def configure_url_frame(key, frameid):
  url_get = get_url_frame_get_closure(frameid)
  url_set = get_url_frame_set_closure(frameid)
  url_delete = get_url_frame_delete_closure(frameid)
  EasyID3.RegisterKey(key, url_get, url_set, url_delete)

def configure_id3_ext():
  """
  Configures Mutagen to handle ID3 tags in exactly the same way that foobar2000
  does it for compatibility, and also for simplicity so that we can use the
  EasyID3 interface to treat all file types the same (except probably MP4).
  """

  if is_configured:
    return

  global is_configured

  # First, we need to configure all the extended text frames.
  for frameid, key in iteritems({
      'TPE2': 'album artist',
      'TPE2': 'albumartist',
      'TSO2': 'albumartistsortorder',
      'TSOA': 'albumsortorder',
      'TSOP': 'artistsortorder',
      'TPE2': 'band',
      'COMM': 'comment',
      'TSOC': 'composersortorder',
      'TIT1': 'content group',
      'TENC': 'encoded by',
      'TSSE': 'encoding settings',
      'TKEY': 'initial key',
      'TCMP': 'itunescompilation',
      'TMED': 'media type',
      'TOAL': 'original album',
      'TOPE': 'original artist',
      'TOWN': 'owner',
      'TPUB': 'publisher',
      'WPUB': 'publisher url',
      'TRSN': 'radio station',
      'TRSO': 'radio station owner',
      'TRDL': 'release date',
      'TPE4': 'remixed by',
      'TSST': 'set subtitle',
      'TIT3': 'subtitle',
      'TSOT': 'titlesortorder',
      'TEXT': 'writer',
  }):
    EasyID3.RegisterTextKey(key, frameid)

  # And now we need to configure URL frames.
  for frameid, key in iteritems({
      'WOAR': 'artist webpage url',
      'WCOM': 'commercial information url',
      'WCOP': 'copyright url',
      'WOAF': 'file webpage url',
      'WORS': 'internet radio webpage url',
      'WPAY': 'payment url',
      'WOAS': 'source webpage url',
  }):
    configure_url_frame(key, frameid)

  # And now to handle text frames.
  # NOTE: Foobar handles "RECORDING DATES" differently depending on whether you
  # are dealing with ID3 2.3 or 2.4 tags.  Since we currently only support using
  # 2.4 tags, we'll do it this way (in a TXXX frame called "recording dates",
  # verified with Foobar 1.3.7), but in 2.3 (and perhaps earlier versions of
  # ID3), it will store this info instead in TRDA frames.
  for desc, key in iteritems({
      'recording dates': 'recording dates',
  }):
    EasyID3.RegisterTXXXKey(key, desc)

  # TODO(dremelofdeath): Support unsynced lyrics -- this can be complicated due
  # to the fact that ID3 supports different encodings and languages for this
  # frame, and we will have to detect both of those when converting M-TAGS,
  # since M-TAGS is always unicode, and I'm not sure how Foobar stores the
  # language attribute of this frame. (I also don't use this field.)
  #    'USLT': 'unsynced lyrics',

  is_configured = True

