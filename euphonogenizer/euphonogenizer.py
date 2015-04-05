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

def print_or_defer_output(output, group=None):
  if args.unique:
    unique_key = output
    if group is not None:
      # Unique only applies within groups -- this is to prevent unexpected
      # behavior when output lines have the same output but are in different
      # groups (for example, when two tracks have the same name but are on
      # differently named albums).
      unique_key = group + output
    if unique_key not in unique_output:
      unique_output.add(unique_key)
      handle_group_uniprint(output, group)
  else:
    handle_group_uniprint(output, group)

def print_deferred_output():
  if hasattr(args, 'groupby') and args.groupby:
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
}

escape_glob_rc = re.compile('|'.join(map(re.escape, escape_glob_dict)))

def escape_glob(path):
  return escape_glob_rc.sub(lambda m: escape_glob_dict[m.group(0)], path)

def find_cover_art(dirname, track, dstpath=None):
  retval = None
  if args.include_covers and dirname not in cover_dirs:
    if hasattr(args, 'explain') and args.explain:
      uniprint('attempting to find cover art for directory:')
      uniprint('  ' + dirname)
    for each in args.include_covers:
      cover_file = os.path.join(dirname, titleformatter.format(track, each))
      cover_glob = glob.glob(escape_glob(cover_file))
      if hasattr(args, 'explain') and args.explain:
        uniprint("  attempting pattern '" + each + "'")
        uniprint('    ==> ' + cover_file)
        if len(cover_glob) > 0:
          uniprint('    possible matches:')
          for n, each_glob in enumerate(cover_glob):
            uniprint('      %d: %s' % (n, each_glob))
        else:
          uniprint('    no matches')
      if cover_glob and os.path.isfile(cover_glob[0]):
        found_cover = cover_glob[0]
        if not dstpath:
          retval = found_cover
          break
        else:
          # Perhaps a bit of a hack to get the metadata formated properly...
          cover_track = track.copy()
          cover_track['@'] = found_cover
          ext = found_cover.split('.')[-1]
          dst = fileformatter.format(cover_track, args.cover_name) + '.' + ext
          dst = os.path.join(dstpath, dst)
          cover_dirs.add(dirname)
          retval = (found_cover, dst)
          break
    if not args.per_track_cover_search:
      cover_dirs.add(dirname)
  return retval

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

def static_format(track, field, **kwargs):
  if field in kwargs:
    value = kwargs[field]
    staticfield = field + 'static'
    if staticfield not in kwargs or not kwargs[staticfield]:
      value = titleformatter.format(track, value)
    return value

def precompute_static_pattern(track_params, attr):
  argsattr = getattr(args, attr)
  if argsattr:
    track_params[attr] = argsattr
    if is_static_pattern(argsattr):
      track_params[attr + 'static'] = True

def precompute_static_filter_patterns(track_params):
  precompute_static_pattern(track_params, 'startswith')
  precompute_static_pattern(track_params, 'equals')
  precompute_static_pattern(track_params, 'contains')

def precompute_static_group_filter_patterns(track_params):
  precompute_static_pattern(track_params, 'group_startswith')

def should_filter_include(formatted, track, **kwargs):
  if 'startswith' in kwargs:
    startswith = static_format(track, 'startswith', **kwargs)
    return formatted.startswith(startswith)
  elif 'equals' in kwargs:
    equals = static_format(track, 'equals', **kwargs)
    return formatted == equals
  elif 'contains' in kwargs:
    contains = static_format(track, 'contains', **kwargs)
    return contains in formatted
  return True

def should_group_filter_include(formattedgroup, track, **kwargs):
  if 'group_startswith' in kwargs:
    group_startswith = static_format(track, 'group_startswith', **kwargs)
    return formattedgroup.startswith(group_startswith)
  return True


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
  def handle_track(self, track, **kwargs):
    formatted = titleformatter.format(track, args.display)
    group = None
    if args.groupby:
      group = titleformatter.format(track, args.groupby)
      if not should_group_filter_include(group, track, **kwargs):
        return
    if should_filter_include(formatted, track, **kwargs):
      print_or_defer_output(formatted, group)

  def handle_tags(self, dirpath, tags, visited_dirs):
    track_params = {}
    precompute_static_filter_patterns(track_params)
    precompute_static_group_filter_patterns(track_params)
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

    cover = find_cover_art(dirpath, track, dirname)

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
    return visited_dirs


class FindCoversCommand(TrackCommand):
  def handle_cover(self, dirpath, track):
    cover = find_cover_art(dirpath, track)
    if cover:
      uniprint(dirpath)
      uniprint('  ==> ' + cover)
      uniprint('')

  def handle_track(self, dirpath, track, **kwargs):
    if args.filter_value:
      formatted = titleformatter.format(track, args.filter_value)
      if should_filter_include(formatted, track, **kwargs):
        self.handle_cover(dirpath, track)
    else:
      self.handle_cover(dirpath, track)

  def handle_tags(self, dirpath, tags, visited_dirs):
    track_params = {}
    precompute_static_filter_patterns(track_params)
    for track in tags.tracks:
      if self.records_processed == args.limit:
        raise LimitReachedException(visited_dirs=visited_dirs)
      self.handle_track(dirpath, track, **track_params)
      self.records_processed += 1

  def run(self):
    if not args.include_covers:
      sep = '\n    '
      parser.error(
          'you must specify one of the following options:%s%s' % (
              sep,
              sep.join([
                '--include-covers',
                '--include-covers-default',
                '--include-covers-aggressive',
              ])
          )
      )
    return super(FindCoversCommand, self).run()


def main():
  if args.cmd == 'list':
    ListCommand().run()
  elif args.cmd == 'copy':
    CopyCommand().run()
  elif args.cmd == 'findcovers':
    FindCoversCommand().run()
  else:
    parser.error("can't understand command '%s' -- this is a bug!" % (args.cmd))


if __name__ == '__main__':
  main()

