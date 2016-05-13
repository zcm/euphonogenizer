#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

from mutagen import File
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, Encoding, PictureType
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from PIL import Image

from .common import unistr

class AlbumArtUnsupportedException(Exception):
  pass

class AlbumArtNotImplementedException(Exception):
  pass

def embed(cover, target):
  if isinstance(target, File):
    embed_file(cover, target)
  else:
    mutagen_file = File(target, easy=False)
    embed_file(cover, mutagen_file)
    mutagen_file.save()

embed_callbacks = {
    FLAC.__name__: embed_to_flac,
    MP3.__name__: embed_to_mp3,
    MP4.__name__: embed_to_mp4,
}

def embed_file(cover, mutagen_file):
  try:
    embed_using_image(
        cover, mutagen_file, embed_callbacks[mutagen_file.__name__])
  except KeyError:
    raise AlbumArtUnsupportedException(
        'Album art is not supported for type ' + mutagen_file.__name__)

def embed_using_image(cover, mutagen_file, embed_to_callback):
  return embed_to_callback(cover, Image.open(cover), mutagen_file)

img_mime = {
    'jpeg': unistr('image/jpeg'),
    'png': unistr('image/png'),
}

img_bpp = {
    '1': 1,
    'L': 8,
    'P': 8,
    'RGB': 24,
    'YCbCr': 24,
    'RGBA': 32,
    'CMYK': 32,
    'I': 32,
    'F': 32,
}

def embed_to_flac(cover, cover_image, flac_file):
  flac_file.clear_pictures()
  pic = Picture()

  with open(cover, 'rb') as f:
    pic.data = f.read()

  pic.type = PictureType.COVER_FRONT
  pic.mime = img_mime[cover_image.format.lower()]
  pic.width, pic.height = cover_image.size
  pic.depth = img_bpp[cover_image.mode]

  flac_file.add_picture(pic)

def embed_to_mp3(cover, cover_image, mp3_file):
  mp3_file.tags.delall('APIC')

  with open(cover, 'rb') as f:
    apic = APIC(
        encoding = Encoding.UTF8,
        mime = img_mime[cover_image.format.lower()],
        type = PictureType.COVER_FRONT,
        data = f.read())

    mp3_file.tags.add(apic)

def embed_to_mp4(cover, cover_image, mp4_file):
  raise AlbumArtNotImplementedException(
      'MP4 album art is not yet implemented.')

