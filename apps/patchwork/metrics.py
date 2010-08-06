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
from datetime import datetime

class PatchMetricsCollector(object):

    def __init__(self, patch):

        self.lead_time = 0
        self.closed_time = 0
        self.num_comments = 0
        self.num_closed = 0

        self.__collect_history_data(patch)

    def __inseconds(self, duration):
        # convert timedelta object to interger value in seconds
        return duration.days*24*3600 + duration.seconds

    def __collect_history_data(self, patch):

        self.patch = patch
        self.creation_date = patch.date
        
        comments = Comment.objects.filter(patch=patch).order_by('date')
        self.num_comments = comments.count()
        self.num_reviewers = Person.objects.filter(comment__patch__project = patch.project, patch=patch).distinct().count()
        self.response_time = self.__inseconds(comments[1].date - comments[0].date)
        self.inactivity_time = self.__inseconds(datetime.now() - comments.reverse()[0].date)     

    def get_all_metrics(self):
        return {'num_comments':self.num_comments,
                'num_reviewers':self.num_reviewers,
                'response_time':self.response_time,
                'inactivity_time':self.inactivity_time}

    def save_to_db(self):
        try:
            patchmetrics = PatchMetrics.objects.get(patch=self.patch.id)
        
        except PatchMetrics.DoesNotExist:
            patchmetrics = PatchMetrics()

        # Update PatchMetrics fields
        patchmetrics.project = self.patch.project
        patchmetrics.patch = self.patch
        patchmetrics.creation_date = self.creation_date
        patchmetrics.last_modified_date = datetime.now()
        patchmetrics.num_comments = self.num_comments
        patchmetrics.num_reviewers = self.num_reviewers
        patchmetrics.response_time = self.response_time
        patchmetrics.inactivity_time = self.inactivity_time

        try:
            patchmetrics.save()
        except Exception, ex:
            print str(ex)
