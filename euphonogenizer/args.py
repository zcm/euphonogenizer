#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse

desc = '''
Manages music libraries with metadata in M-TAGS format.
Written by Zachary Murray (dremelofdeath). Loved by you, I hope.
'''

parser = argparse.ArgumentParser(prog='euphonogenizer', description=desc)

cmd_parser = parser.add_subparsers(title='Supported operations', dest='cmd')

copy_cmd_parser = cmd_parser.add_parser('copy',
    help = 'copy all referenced files found in metadata',
)

copy_cmd_parser.add_argument('--to',
    help = 'pattern that specifies the destination for file operations',
    required = True,
)

list_cmd_parser = cmd_parser.add_parser('list',
    help = 'print out all found tracks',
)

list_cmd_parser.add_argument('--display',
    default = '%artist% - %title%',
    help = 'pattern used to format output when listing tracks',
)

parser.add_argument('--tagsfile',
    default = '!.tags',
    help = 'internal: the filename of the target tags files in subdirectories',
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

parser.add_argument('--magic',
    action = 'store_true',
    dest = 'magic',
    help = 'allow variable resolution to search multiple fields (the default)',
)
parser.add_argument('--no-magic',
    action = 'store_false',
    dest = 'magic',
    help = 'forbid magical variable resolution (default is allow)',
)
parser.set_defaults(magic=True)

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

