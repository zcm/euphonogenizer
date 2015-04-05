#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

import glob
import os
import re
import shutil
import sys

import mtags
import titleformat

from args import args, parser
from common import dbg, err, unicwd, uniprint, unistr


titleformatter = titleformat.TitleFormatter(
    args.case_sensitive, args.magic, for_filename=False)
fileformatter = titleformat.TitleFormatter(
    args.case_sensitive, args.magic, for_filename=True)

unique_output = set()
groupby_output = {}
cover_dirs = set()

def handle_group_uniprint(output, group):
  if group:
    if group not in groupby_output:
      groupby_output[group] = [output]
    else:
      groupby_output[group].append(output)
  else:
    uniprint(output)

def print_or_defer_output(output, group):
  if args.unique:
    if output not in unique_output:
      unique_output.add(output)
      handle_group_uniprint(output, group)
  else:
    handle_group_uniprint(output, group)

def print_deferred_output():
  if args.groupby:
    first = True
    for key in groupby_output:
      if not first:
        uniprint('')
      uniprint(key + ':')
      for each in groupby_output[key]:
        uniprint(' ' * args.groupby_indent + each)
      first = False

def is_static_pattern(pattern):
  formatted = titleformatter.format({}, pattern)
  return pattern == formatted

escape_glob_dict = {
    '[': '[[]',
    ']': '[]]',
    '*': '[*]',
    '?': '[?]',
}

escape_glob_rc = re.compile('|'.join(map(re.escape, escape_glob_dict)))

def escape_glob(path):
  return escape_glob_rc.sub(lambda m: escape_glob_dict[m.group(0)], path)

def find_cover_art(dirname, dstpath, track):
  if args.include_covers and dirname not in cover_dirs:
    for each in args.include_covers:
      cover_file = os.path.join(dirname, titleformatter.format(track, each))
      cover_glob = glob.glob(escape_glob(cover_file))
      if cover_glob and os.path.isfile(cover_glob[0]):
        found_cover = cover_glob[0]
        # Perhaps a bit of a hack to get the metadata formated properly...
        cover_track = track.copy()
        cover_track['@'] = found_cover
        ext = found_cover.split('.')[-1]
        dst = fileformatter.format(cover_track, args.cover_name) + '.' + ext
        dst = os.path.join(dstpath, dst)
        cover_dirs.add(dirname)
        return (found_cover, dst)
    if not args.per_track_cover_search:
      cover_dirs.add(dirname)

def create_dirs_and_copy(dirname, src, dst):
  if os.path.isfile(dst):
    if not args.quiet:
      uniprint('file already exists: ' + dst)
  else:
    if not args.quiet:
      uniprint(dst)
    if os.path.isfile(src):
      if not args.dry_run:
        try:
          os.makedirs(dirname)
        except OSError:
          pass

        shutil.copy2(src, dst)


class LimitReachedException(Exception):
  def __init__(self, message="Limit reached", visited_dirs=None):
    super(LimitReachedException, self).__init__(message)
    self.visited_dirs = visited_dirs


class TrackCommand(object):
  def __init__(self):
    self.records_processed = 0

  def handle_tags(self, dirpath, tags):
    pass

  def run(self):
    visited_dirs = None

    try:
      visited_dirs = self.do_run()
    except LimitReachedException as e:
      visited_dirs = e.visited_dirs

    print_deferred_output()
    return visited_dirs

  def do_run(self):
    self.records_processed = 0
    visited_dirs = {}

    for dirpath, dirnames, filenames in os.walk(unicwd()):
      for tagsfile in [each for each in filenames if each == args.tagsfile]:
        tags = mtags.TagsFile(os.path.join(dirpath, tagsfile))
        self.handle_tags(dirpath, tags, visited_dirs)

    return visited_dirs


class ListCommand(TrackCommand):
  def static_fmt(self, track, field, **kwargs):
    if field in kwargs:
      value = kwargs[field]
      staticfield = field + 'static'
      if staticfield not in kwargs or not kwargs[staticfield]:
        value = titleformatter.format(track, value)
      return value

  def handle_track(self, track, **kwargs):
    formatted = titleformatter.format(track, args.display)
    group = None
    if args.groupby:
      group = titleformatter.format(track, args.groupby)
      if 'group_startswith' in kwargs:
        group_startswith = self.static_fmt(track, 'group_startswith', **kwargs)
      if not group.startswith(group_startswith):
        return
    if 'startswith' in kwargs:
      startswith = self.static_fmt(track, 'startswith', **kwargs)
      if formatted.startswith(startswith):
        print_or_defer_output(formatted, group)
    elif 'equals' in kwargs:
      equals = self.static_fmt(track, 'equals', **kwargs)
      if formatted == equals:
        print_or_defer_output(formatted, group)
    elif 'contains' in kwargs:
      contains = self.static_fmt(track, 'contains', **kwargs)
      if contains in formatted:
        print_or_defer_output(formatted, group)
    else:
      print_or_defer_output(formatted, group)

  def handle_tags(self, dirpath, tags, visited_dirs):
    startswith = False
    track_params = {}
    if args.group_startswith:
      track_params['group_startswith'] = args.group_startswith
      if is_static_pattern(args.group_startswith):
        track_params['group_startswithstatic'] = True
    if args.startswith:
      track_params['startswith'] = args.startswith
      if is_static_pattern(args.startswith):
        track_params['startswithstatic'] = True
    elif args.equals:
      track_params['equals'] = args.equals
      if is_static_pattern(args.equals):
        track_params['equalsstatic'] = True
    elif args.contains:
      track_params['contains'] = args.contains
      if is_static_pattern(args.contains):
        track_params['containsstatic'] = True
    for track in tags.tracks:
      if self.records_processed == args.limit:
        raise LimitReachedException(visited_dirs=visited_dirs)
      self.handle_track(track, **track_params)
      self.records_processed += 1


class CopyCommand(TrackCommand):
  def handle_track(self, dirpath, track, visited_dirs, **kwargs):
    track_filename = unistr(track.get('@'))

    if args.skip_cue:
      if '.cue|' in track_filename:
        return

    u_dirpath = unistr(dirpath)
    u_track_filename = unistr(track_filename)
    src = os.path.join(u_dirpath, u_track_filename)
    dst = fileformatter.format(track, args.to + '.$ext(%filename_ext%)')
    dirname, basename = os.path.split(dst)

    cover = find_cover_art(dirpath, dirname, track)

    if cover:
      coversrc = cover[0]
      coverdst = cover[1]
      create_dirs_and_copy(dirname, coversrc, coverdst)

    if args.write_mtags:
      if dirname not in visited_dirs:
        visited_dirs[dirname] = []
      visited_dirs[dirname].append((basename, track))

    create_dirs_and_copy(dirname, src, dst)

  def handle_tags(self, dirpath, tags, visited_dirs):
    for track in tags.tracks:
      if self.records_processed == args.limit:
        raise LimitReachedException(visited_dirs=visited_dirs)
      self.handle_track(dirpath, track, visited_dirs)
      self.records_processed += 1

  def run(self):
    visited_dirs = super(CopyCommand, self).run()
    if args.write_mtags:
      for dirname, trackfiles in visited_dirs.iteritems():
        pending_mtags = []
        for trackfile in trackfiles:
          basename = trackfile[0]
          trackinfo = trackfile[1].copy()
          trackinfo['@'] = basename
          pending_mtags.append(trackinfo)
        mtagsfile = mtags.TagsFile(pending_mtags)
        mtags_dst = os.path.join(dirname, args.tagsfile)
        if not args.quiet:
          uniprint(mtags_dst)
        mtagsfile.write(mtags_dst)


def main():
  if args.cmd == 'list':
    ListCommand().run()
  elif args.cmd == 'copy':
    CopyCommand().run()


if __name__ == '__main__':
  main()

