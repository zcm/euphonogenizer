#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse


parser = argparse.ArgumentParser(
    description = 'Manages music libraries with metadata in M-TAGS format.',
    epilog = 'Written by Zachary Murray (dremelofdeath). Loved by you, I hope.',
)

parser.add_argument('--mode',
    choices = ['copy', 'move', 'rename'],
    default = 'copy',
    help = 'operating mode for transformations',
)

parser.add_argument('--tagsfile',
    default = '!.tags',
    help = 'internal: the filename of the target tags files in subdirectories',
)

parser.add_argument('--pattern',
    default = "'  $$$' [[''%ISRC%'' -] %TRACKNUMBER% - ] %TITLE%",
    help = 'the pattern used for output filenames in transformations',
)

parser.add_argument('--case-sensitive',
    action = 'store_true',
    dest = 'case_sensitive',
    help = 'force variable resolution to be case-sensitive (default is false)',
)
parser.add_argument('--no-case-sensitive',
    action = 'store_false',
    dest = 'case_sensitive',
    help = 'force variable resolution to be case-insensitive (the default)',
)
parser.set_defaults(case_sensitive=False)

parser.add_argument('--coversearchpatterns',
    default = [
      '../override.png',
      '../override.jpg',
      '../front.png',
      '../cover.png',
      '../%@%.png',
      '../%ALBUM%.png',
      '../folder.png',
      '../%ARTIST% - %ALBUM%.png',
      '../front.jpg',
      '../cover.jpg',
      '../%@%.jpg',
      '../%ALBUM%.jpg',
      '../folder.jpg',
      '../front.jpeg',
      '../cover.jpeg',
      '../folder.jpeg',
      '../%ARTIST% - %ALBUM%.jpg',
      '../%ARTIST% - %ALBUM%.jpeg',
      'override.png',
      'override.jpg',
      'override.jpeg',
      'front.png',
      'front.jpg',
      'cover.png',
      'cover.jpg',
      '%@%.png',
      '%@%.jpg',
      '%ALBUM%.png',
      '%ALBUM%.jpg',
      'folder.png',
      'folder.jpg',
      'artwork/front.png',
      'artwork/front.jpg',
      '00 %ALBUM%.png',
      '00 %ALBUM%.jpg',
      '%ALBUM% - front.png',
      '%ALBUM% - front.jpg',
      '%ALBUM% - cover.png',
      '%ALBUM% - cover.jpg',
      '%ARTIST% - %ALBUM% - front.png',
      '%ARTIST% - %ALBUM% - front.jpg',
      '%ARTIST% - %ALBUM% - cover.png',
      '%ARTIST% - %ALBUM% - cover.jpg',
      'front.jpeg',
      'cover.jpeg',
      'folder.jpeg',
      'artwork/front.jpeg',
      '00 %ALBUM%.jpeg',
      '%ALBUM% - front.jpeg',
      '%ALBUM% - cover.jpeg',
      '%ARTIST% - %ALBUM% - front.jpeg',
      '%ARTIST% - %ALBUM% - cover.jpeg',
      '%ARTIST% - %ALBUM%.jpg',
      '%ARTIST% - %ALBUM%.jpeg',
      '%ARTIST% - %ALBUM%.png',
      'folder*.jpg',
      'FOLDER*.jpg',
    ],
    nargs = '+',
)

args = parser.parse_args()

