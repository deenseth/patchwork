#!/usr/bin/python
#
# Patchwork - automated patch tracking system
# Copyright (C) 2008 Jeremy Kerr <jk@ozlabs.org>
#
# This file is part of the Patchwork package.
#
# Patchwork is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Patchwork is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Patchwork; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import sys
import re
import datetime
import time
import operator
from email import message_from_file
try:
    from email.header import Header, decode_header
    from email.utils import parsedate_tz, mktime_tz
except ImportError:
    # Python 2.4 compatibility
    from email.Header import Header, decode_header
    from email.Utils import parsedate_tz, mktime_tz

from patchwork.parser import parse_patch
from patchwork.models import Patch, Project, Person, Comment, State

list_id_headers = ['List-ID', 'X-Mailing-List']

whitespace_re = re.compile('\s+')
def normalise_space(str):
    return whitespace_re.sub(' ', str).strip()

def clean_header(header):
    """ Decode (possibly non-ascii) headers """

    def decode(fragment):
        (frag_str, frag_encoding) = fragment
        if frag_encoding:
            return frag_str.decode(frag_encoding)
        return frag_str.decode()

    fragments = map(decode, decode_header(header))

    return normalise_space(u' '.join(fragments))

def find_project(mail):
    project = None
    listid_res = [re.compile('.*<([^>]+)>.*', re.S),
                  re.compile('^([\S]+)$', re.S)]

    for header in list_id_headers:
        if header in mail:

            for listid_re in listid_res:
                match = listid_re.match(mail.get(header))
                if match:
                    break

            if not match:
                continue

            listid = match.group(1)

            try:
                project = Project.objects.get(listid = listid)
                break
            except:
                pass

    return project

def find_author(mail):

    from_header = clean_header(mail.get('From'))
    (name, email) = (None, None)

    # tuple of (regex, fn)
    #  - where fn returns a (name, email) tuple from the match groups resulting
    #    from re.match().groups()
    from_res = [
        # for "Firstname Lastname" <example@example.com> style addresses
       (re.compile('"?(.*?)"?\s*<([^>]+)>'), (lambda g: (g[0], g[1]))),

       # for example@example.com (Firstname Lastname) style addresses
       (re.compile('"?(.*?)"?\s*\(([^\)]+)\)'), (lambda g: (g[1], g[0]))),

       # everything else
       (re.compile('(.*)'), (lambda g: (None, g[0]))),
    ]

    for regex, fn in from_res:
        match = regex.match(from_header)
        if match:
            (name, email) = fn(match.groups())
            break

    if email is None:
        raise Exception("Could not parse From: header")

    email = email.strip()
    if name is not None:
        name = name.strip()

    new_person = False

    try:
        person = Person.objects.get(email__iexact = email)
    except Person.DoesNotExist:
        person = Person(name = name, email = email)
        new_person = True

    return (person, new_person)

def mail_date(mail):
    t = parsedate_tz(mail.get('Date', ''))
    if not t:
        return datetime.datetime.utcnow()
    return datetime.datetime.utcfromtimestamp(mktime_tz(t))

def mail_headers(mail):
    return reduce(operator.__concat__,
            ['%s: %s\n' % (k, Header(v, header_name = k, \
                    continuation_ws = '\t').encode()) \
                for (k, v) in mail.items()])

def find_content(project, mail):
    patchbuf = None
    commentbuf = ''

    for part in mail.walk():
        if part.get_content_maintype() != 'text':
            continue

        payload = part.get_payload(decode=True)
        charset = part.get_content_charset()
        subtype = part.get_content_subtype()

        # if we don't have a charset, assume utf-8
        if charset is None:
            charset = 'utf-8'

        if not isinstance(payload, unicode):
            payload = unicode(payload, charset)

        if subtype in ['x-patch', 'x-diff']:
            patchbuf = payload

        elif subtype == 'plain':
            if not patchbuf:
                (patchbuf, c) = parse_patch(payload)
            else:
                c = payload

            if c is not None:
                commentbuf += c.strip() + '\n'

    patch = None
    comment = None

    if patchbuf:
        mail_headers(mail)
	name = clean_subject(mail.get('Subject'), [project.linkname])
        patch = Patch(name = name, content = patchbuf,
                    date = mail_date(mail), headers = mail_headers(mail))

    if commentbuf:
        if patch:
            cpatch = patch
        else:
            cpatch = find_patch_for_comment(project, mail)
            if not cpatch:
                return (None, None)
        comment = Comment(patch = cpatch, date = mail_date(mail),
                content = clean_content(commentbuf),
                headers = mail_headers(mail))

    return (patch, comment)

def find_patch_for_comment(project, mail):
    # construct a list of possible reply message ids
    refs = []
    if 'In-Reply-To' in mail:
        refs.append(mail.get('In-Reply-To'))

    if 'References' in mail:
        rs = mail.get('References').split()
        rs.reverse()
        for r in rs:
            if r not in refs:
                refs.append(r)

    for ref in refs:
        patch = None

        # first, check for a direct reply
        try:
            patch = Patch.objects.get(project = project, msgid = ref)
            return patch
        except Patch.DoesNotExist:
            pass

        # see if we have comments that refer to a patch
        try:
            comment = Comment.objects.get(patch__project = project, msgid = ref)
            return comment.patch
        except Comment.DoesNotExist:
            pass


    return None

split_re = re.compile('[,\s]+')

def split_prefixes(prefix):
    """ Turn a prefix string into a list of prefix tokens

    >>> split_prefixes('PATCH')
    ['PATCH']
    >>> split_prefixes('PATCH,RFC')
    ['PATCH', 'RFC']
    >>> split_prefixes('')
    []
    >>> split_prefixes('PATCH,')
    ['PATCH']
    >>> split_prefixes('PATCH ')
    ['PATCH']
    >>> split_prefixes('PATCH,RFC')
    ['PATCH', 'RFC']
    >>> split_prefixes('PATCH 1/2')
    ['PATCH', '1/2']
    """
    matches = split_re.split(prefix)
    return [ s for s in matches if s != '' ]

re_re = re.compile('^(re|fwd?)[:\s]\s*', re.I)
prefix_re = re.compile('^\[([^\]]*)\]\s*(.*)$')

def clean_subject(subject, drop_prefixes = None):
    """ Clean a Subject: header from an incoming patch.

    Removes Re: and Fwd: strings, as well as [PATCH]-style prefixes. By
    default, only [PATCH] is removed, and we keep any other bracketed data
    in the subject. If drop_prefixes is provided, remove those too,
    comparing case-insensitively.

    >>> clean_subject('meep')
    'meep'
    >>> clean_subject('Re: meep')
    'meep'
    >>> clean_subject('[PATCH] meep')
    'meep'
    >>> clean_subject('[PATCH] meep \\n meep')
    'meep meep'
    >>> clean_subject('[PATCH RFC] meep')
    '[RFC] meep'
    >>> clean_subject('[PATCH,RFC] meep')
    '[RFC] meep'
    >>> clean_subject('[PATCH,1/2] meep')
    '[1/2] meep'
    >>> clean_subject('[PATCH RFC 1/2] meep')
    '[RFC,1/2] meep'
    >>> clean_subject('[PATCH] [RFC] meep')
    '[RFC] meep'
    >>> clean_subject('[PATCH] [RFC,1/2] meep')
    '[RFC,1/2] meep'
    >>> clean_subject('[PATCH] [RFC] [1/2] meep')
    '[RFC,1/2] meep'
    >>> clean_subject('[PATCH] rewrite [a-z] regexes')
    'rewrite [a-z] regexes'
    >>> clean_subject('[PATCH] [RFC] rewrite [a-z] regexes')
    '[RFC] rewrite [a-z] regexes'
    >>> clean_subject('[foo] [bar] meep', ['foo'])
    '[bar] meep'
    >>> clean_subject('[FOO] [bar] meep', ['foo'])
    '[bar] meep'
    """

    if drop_prefixes is None:
        drop_prefixes = []
    else:
        drop_prefixes = [ s.lower() for s in drop_prefixes ]

    drop_prefixes.append('patch')

    # remove Re:, Fwd:, etc
    subject = re_re.sub(' ', subject)

    subject = normalise_space(subject)

    prefixes = []

    match = prefix_re.match(subject)

    while match:
        prefix_str = match.group(1)
        prefixes += [ p for p in split_prefixes(prefix_str) \
                        if p.lower() not in drop_prefixes]

        subject = match.group(2)
        match = prefix_re.match(subject)

    subject = normalise_space(subject)

    subject = subject.strip()
    if prefixes:
        subject = '[%s] %s' % (','.join(prefixes), subject)

    return subject

sig_re = re.compile('^(-- |_+)\n.*', re.S | re.M)
def clean_content(str):
    """ Try to remove signature (-- ) and list footer (_____) cruft """
    str = sig_re.sub('', str)
    return str.strip()

def parse_mail(mail):

    # some basic sanity checks
    if 'From' not in mail:
        return 0

    if 'Subject' not in mail:
        return 0

    if 'Message-Id' not in mail:
        return 0

    hint = mail.get('X-Patchwork-Hint', '').lower()
    if hint == 'ignore':
        return 0;

    project = find_project(mail)
    if project is None:
        print "no project found"
        return 0

    msgid = mail.get('Message-Id').strip()

    (author, save_required) = find_author(mail)

    (patch, comment) = find_content(project, mail)

    if patch:
        # we delay the saving until we know we have a patch.
        if save_required:
            author.save()
            save_required = False
        patch.submitter = author
        patch.msgid = msgid
        patch.project = project
        try:
            patch.save()
        except Exception, ex:
            print str(ex)

    if comment:
        if save_required:
            author.save()
        # looks like the original constructor for Comment takes the pk
        # when the Comment is created. reset it here.
        if patch:
            comment.patch = patch
        comment.submitter = author
        comment.msgid = msgid
        try:
            comment.save()
        except Exception, ex:
            print str(ex)

        # Automatically update patch state when other people comment the patch
        tpatch = comment.patch
        if (tpatch.submitter != comment.submitter and tpatch.state.action_required == True):

            # Assume that patch that has Reviewed-by is accepted
            if (comment.patch_responses().rfind('Reviewed-by') == 0):
                tpatch.state = State.objects.get(id = 3) # Accepted
            else:
                tpatch.state = State.objects.get(id = 2) # Under Review
            try:
                tpatch.save()
            except Exception, ex:
                print str(ex)

    return 0

def main(args):
    mail = message_from_file(sys.stdin)
    return parse_mail(mail)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
