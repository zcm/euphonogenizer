#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

import mutagen.id3

from mutagen._compat import iteritems
from mutagen.easyid3 import EasyID3
from mutagen.easyid3 import EasyID3KeyError
from mutagen.easyid3 import gain_get, gain_set, gain_delete, peakgain_list
from mutagen.easyid3 import peak_get, peak_set, peak_delete


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

def get_best_txxx_encoding(value):
  # Store 8859-1 if we can, per MusicBrainz spec.
  for v in value:
    if v and max(v) > u'\x7f':
      return 3

  return 0

def gain_get_with_txxx(id3, key):
  frameid = 'TXXX:' + key

  try:
    frame = id3[frameid]
  except KeyError:
    return None

  return gain_get(id3, key)

def gain_set_with_txxx(id3, key, value):
  frameid = 'TXXX:' + key

  try:
    frame = id3[frameid]
  except KeyError:
    enc = get_best_txxx_encoding(value)

    id3.add(mutagen.id3.TXXX(encoding=enc, text=value, desc=key))
  else:
    frame.text = value

  return gain_set(id3, key, value)

def gain_delete_with_txxx(id3, key):
  del(id3['TXXX:' + key])
  return gain_delete(id3, key)

def peak_get_with_txxx(id3, key):
  frameid = 'TXXX:' + key

  try:
    frame = id3[frameid]
  except KeyError:
    return None

  return peak_get(id3, key)

def peak_set_with_txxx(id3, key, value):
  frameid = 'TXXX:' + key

  try:
    frame = id3[frameid]
  except KeyError:
    enc = get_best_txxx_encoding(value)

    id3.add(mutagen.id3.TXXX(encoding=enc, text=value, desc=key))
  else:
    frame.text = value

  return peak_set(id3, key, value)

def peak_delete_with_txxx(id3, key):
  del(id3['TXXX:' + key])
  return peak_delete(id3, key)

def comment_txxx_set_fallback(cls, id3, key, value):
  frameid = 'TXXX:'

  if key is None or key == 'comment':
    frameid = 'COMM'
  else:
    frameid = frameid + key

  try:
    frame = id3[frameid]
  except KeyError:
    enc = get_best_txxx_encoding(value)

    if key is None:
      id3.add(mutagen.id3.COMM(encoding=enc, text=value))
    else:
      id3.add(mutagen.id3.TXXX(encoding=enc, text=value, desc=key))
  else:
    frame.text = value

def configure_id3_ext():
  """
  Configures Mutagen to handle ID3 tags in exactly the same way that foobar2000
  does it for compatibility, and also for simplicity so that we can use the
  EasyID3 interface to treat all file types the same (except probably MP4).
  """

  global is_configured

  if is_configured:
    return

  # First, we need to configure all the extended text frames.
  for frameid, key in iteritems({
      'TPE2': 'album artist',
      'TPE2': 'albumartist',
      'TSO2': 'albumartistsortorder',
      'TSOA': 'albumsortorder',
      'TSOP': 'artistsortorder',
      'TPE2': 'band',
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
      'TDRL': 'release date',
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

  # Override Mutagen's default behavior for ReplayGain, since Foobar handles it
  # differently. We will still write the RVA2 frame, but we'll write the
  # ReplayGain info to TXXX frames as well.
  del(EasyID3.Get['replaygain_*_gain'])
  del(EasyID3.Get['replaygain_*_peak'])
  del(EasyID3.Set['replaygain_*_gain'])
  del(EasyID3.Set['replaygain_*_peak'])
  del(EasyID3.Delete['replaygain_*_gain'])
  del(EasyID3.Delete['replaygain_*_peak'])

  EasyID3.RegisterKey('replaygain_*_gain',
      gain_get_with_txxx, gain_set_with_txxx, gain_delete_with_txxx,
      peakgain_list)
  EasyID3.RegisterKey('replaygain_*_peak',
      peak_get_with_txxx, peak_set_with_txxx, peak_delete_with_txxx)

  # And for whatever unknown frames exist out there, we will just make them TXXX
  # comments, just to be completely sure we're copying EVERYTHING.
  EasyID3.SetFallback = comment_txxx_set_fallback

  # TODO(dremelofdeath): Support unsynced lyrics -- this can be complicated due
  # to the fact that ID3 supports different encodings and languages for this
  # frame, and we will have to detect both of those when converting M-TAGS,
  # since M-TAGS is always unicode, and I'm not sure how Foobar stores the
  # language attribute of this frame. (I also don't use this field.)
  #    'USLT': 'unsynced lyrics',

  is_configured = True

