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
        self.save_to_db()

    def __inseconds(self, duration):
        # convert timedelta object to interger value in seconds
        return duration.days*24*3600 + duration.seconds

    def __collect_history_data(self, patch):

        self.patch = patch
        self.creation_date = patch.date
        
        comments = Comment.objects.filter(patch=patch).order_by('date')
        self.num_comments = comments.count()
        self.num_reviewers = Person.objects.filter(comment__patch=patch).distinct().count()

        if (len(comments) > 1):
            self.response_time = self.__inseconds(comments[1].date - comments[0].date)
        else:
            self.response_time = self.__inseconds(datetime.now() - comments[0].date)    

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

class PatchGroupMetrics(object):

    def __init__(self, patches):

        self.patches = patches  #django QuerySet
        self.num_patches = len(patches)

        self.patches_metrics = [PatchMetricsCollector(patch) for patch in self.patches]

    def get_num_comments_stats(self):

        data = [patch_metrics.num_comments for patch_metrics in self.patches_metrics]
        stats = DescriptiveStats(data)
        return stats

    def get_num_reviewers_stats(self):

        data = [patch_metrics.num_reviewers for patch_metrics in self.patches_metrics]
        stats = DescriptiveStats(data)
        return stats

    def get_frequency_metrics_stats(self):

        return {"Number of comments per patch": self.get_num_comments_stats(),
                "Number of reviewers per patch": self.get_num_reviewers_stats()}

    def get_duration_metrics_stats(self):

        return {"Response time": self.get_response_time_stats(),
                "Inactivity time": self.get_inactivity_time_stats()}

    def get_response_time_stats(self):

        data = [patch_metrics.response_time for patch_metrics in self.patches_metrics]
        stats = DescriptiveStats(data)
        return stats

    def get_inactivity_time_stats(self):
        data = [patch_metrics.inactivity_time for patch_metrics in self.patches_metrics]
        stats = DescriptiveStats(data)
        return stats

class DescriptiveStats(object):

    def __init__(self, sequence):
        # sequence of numbers we will process
        # convert all items to floats for numerical processing
        self.sequence = [float(item) for item in sequence]

    def sum(self):
        if len(self.sequence) < 1:
            return None
        else:
            return sum(self.sequence)

    def count(self):
        return len(self.sequence)

    def min(self):
        if len(self.sequence) < 1:
            return None
        else:
            return min(self.sequence)

    def max(self):
        if len(self.sequence) < 1:
            return None
        else:
            return max(self.sequence)

    def avg(self):
        if len(self.sequence) < 1:
            return None
        else: 
            return sum(self.sequence) / len(self.sequence)    

    def median(self):
        if len(self.sequence) < 1:
            return None
        else:
            self.sequence.sort()
            return self.sequence[len(self.sequence) // 2]

    def stdev(self):
        if len(self.sequence) < 1:
            return None
        else:
            avg = self.avg()
            sdsq = sum([(i - avg) ** 2 for i in self.sequence])
            stdev = (sdsq / (len(self.sequence) - 1 or 1)) ** .5
            return stdev
