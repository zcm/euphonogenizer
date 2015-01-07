#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse

from common import progname

desc = '''
Manages music libraries with metadata in M-TAGS format.
Written with love by Zachary Murray (dremelofdeath).
'''

parser = argparse.ArgumentParser(prog=progname, description=desc)

cmd_parser = parser.add_subparsers(title='supported operations', dest='cmd')

copy_cmd_parser = cmd_parser.add_parser('copy',
    help = 'copy all referenced files found in metadata',
)

copy_cmd_parser.add_argument('--to',
    help = 'pattern that specifies the destination for file operations',
    required = True,
)

copy_cmd_parser.add_argument('--dry-run',
    action = 'store_true',
    default = 'false',
    dest = 'dry_run',
    help = "don't actually copy anything, just show what would happen",
)

list_cmd_parser = cmd_parser.add_parser('list',
    help = 'print out all found tracks',
)

list_cmd_parser.add_argument('--display',
    default = '%artist% - %title%',
    help = 'pattern used to format output when listing tracks',
    metavar = 'PATTERN',
)

list_cmd_output_filter = list_cmd_parser.add_mutually_exclusive_group()

list_cmd_output_filter.add_argument('--startswith',
    default = False,
    help = 'display only output that starts with the specified pattern',
    metavar = 'PATTERN',
)

list_cmd_output_filter.add_argument('--equals',
    default = False,
    help = 'display only output that matches the specified pattern exactly',
    metavar = 'PATTERN',
)

list_cmd_parser.add_argument('--unique',
    action = 'store_true',
    default = False,
    help = 'only print each uniquely formatted line once',
)

parser.add_argument('--tagsfile',
    default = '!.tags',
    help = 'the filename of the target tags files in subdirectories (!.tags)',
)

parser.add_argument('--case-sensitive',
    action = 'store_true',
    dest = 'case_sensitive',
    help = 'force variable resolution to instead be case-sensitive',
)
parser.set_defaults(case_sensitive=False)

parser.add_argument('--disable-magic',
    action = 'store_false',
    dest = 'magic',
    help = 'prevent variable resolution from searching multiple fields',
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
    help = 'search list for front cover art',
    metavar = 'PATTERN',
)

args = parser.parse_args()

