# Patchwork - automated patch tracking system
# Copyright (C) 2010 Deen Sethanandha <deenseth@gmail.com>
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

from patchwork.models import Patch, PatchMetrics, Project, Person, Comment
import datetime

def UpdatePatchMetrics(patch):

    try: 
        patchmetrics = PatchMetrics.objects.get(patch=patch.id)
        
    except PatchMetrics.DoesNotExist:
        patchmetrics = PatchMetrics()
        
    # Update PatchMetrics fields
    patchmetrics.project = patch.project    
    patchmetrics.patch = patch
    patchmetrics.num_comments = Comment.objects.filter(patch=patch).count()
    patchmetrics.num_reviewers = Comment.objects.filter(patch=patch).distinct().count()
    patchmetrics.creation_date = patch.date
    patchmetrics.last_modified_date = datetime.datetime.now()
    
    try:
        patchmetrics.save()
    except Exception, ex:
        print str(ex)