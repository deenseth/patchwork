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
from datetime import datetime, timedelta

class PatchInfo(object):

    def __init__(self, patch):

        self.patch = patch
        self.num_comments = 0
        self.num_reviewers = 0
        self.created_date = patch.date
        self.patch_id = patch.id

        comments = Comment.objects.filter(patch=patch).order_by('date')
        self.closed_date = comments.reverse()[0].date

        self.__collect_history_data(patch)
        self.save_metrics_to_db()

    def __inseconds(self, duration):
        # convert timedelta object to interger value in seconds
        return duration.days*24*3600 + duration.seconds

    def __collect_history_data(self, patch):

        
        comments = Comment.objects.filter(patch=patch).order_by('date')
        self.num_comments = comments.count()
        self.num_reviewers = Person.objects.filter(comment__patch=patch).distinct().count()

        if (len(comments) > 1):
            self.response_time = self.__inseconds(comments[1].date - comments[0].date)
        else:
            self.response_time = self.__inseconds(datetime.now() - comments[0].date)    

        self.inactivity_time = self.__inseconds(datetime.now() - comments.reverse()[0].date)     

    def is_closed(self):
        return not self.patch.state.action_required

    def get_all_metrics(self):
        return {'num_comments':self.num_comments,
                'num_reviewers':self.num_reviewers,
                'response_time':self.response_time,
                'inactivity_time':self.inactivity_time}

    def save_metrics_to_db(self):
        try:
            patchmetrics = PatchMetrics.objects.get(patch=self.patch.id)
        
        except PatchMetrics.DoesNotExist:
            patchmetrics = PatchMetrics()

        # Update PatchMetrics fields
        patchmetrics.project = self.patch.project
        patchmetrics.patch = self.patch
        patchmetrics.creation_date = self.created_date
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

        self.patches_info = [PatchInfo(patch) for patch in self.patches]

    def get_num_comments_stats(self):

        data = [patch_info.num_comments for patch_info in self.patches_info]
        stats = DescriptiveStats(data)
        return stats

    def get_num_reviewers_stats(self):

        data = [patch_info.num_reviewers for patch_info in self.patches_info]
        stats = DescriptiveStats(data)
        return stats

    def get_frequency_metrics_stats(self):

        return {"Number of comments per patch": self.get_num_comments_stats(),
                "Number of reviewers per patch": self.get_num_reviewers_stats()}

    def get_duration_metrics_stats(self):

        return {"Response time": self.get_response_time_stats(),
                "Inactivity time": self.get_inactivity_time_stats()}

    def get_response_time_stats(self):

        data = [patch_info.response_time for patch_info in self.patches_info]
        stats = DescriptiveStats(data)
        return stats

    def get_inactivity_time_stats(self):
        data = [patch_info.inactivity_time for patch_info in self.patches_info]
        stats = DescriptiveStats(data)
        return stats

    def get_patches_created_during(self, start_date, end_date):

        end_date = end_date.replace(hour=23, minute=59, second=59)

        #to-do: might not include patch on the end date
        created_patches = patches.filter(date__gte=start_date, date__lte=end_date)

        patch_ids = [patch.id for patch in patches]

        return patch_ids

    def get_remaning_opened_patch_on(self, end_date):
        """
            Assumption: patch state does not change back after it is resolved.
        """

        end_date = end_date.replace(hour=23, minute=59, second=59)
        patch_ids = []

        for patch_info in self.patches_info:

            # only consider the patch that was created before the end date.
            if patch_info.created_date <= end_date:

                if (patch_info.is_closed()):

                    if (end_date < patch_info.closed_date):
                        patch_ids.append(patch_info.patch_id)

                # Assume that patch that is not closed are opened
                else:
                    # only add the patch that was created before the end date
                    if (end_date >= patch_info.created_date):
                        patch_ids.append(patch_info.patch_id)

        return patch_ids

    def get_patches_closed_during(self, start_date, end_date):
        """
            Patchwork doesn't keep the date when status is changed.  I have to make assumption here.
            Patch is considered closed when it is in state whose required_action is False
            The closed date is the date of the last comment.
        """
        end_date = end_date.replace(hour=23, minute=59, second=59)

        patch_ids = []

        for patch_info in self.patches_info:

            if (patch_info.is_closed()):
                # Take the last comment date as closed date
                if (start_date <= patch_info.closed_date <= end_date):
                    patch_ids.append(patch.id)

        return patch_ids

    def get_bmi_monthly_stats(self, start_date, end_date):

        created_tickets = self.get_tickets_created_during(start_date, end_date)
        opened_tickets = self.get_remaning_opened_ticket_on(end_date)
        closed_tickets = self.get_tickets_closed_during(start_date, end_date)

        if opened_tickets == []:
            bmi = 0
        else:
            bmi = float(len(closed_tickets)) * 100 / float(len(opened_tickets))

        return ("%s/%s" % (start_date.month, start_date.year),
                created_tickets,
                opened_tickets,
                closed_tickets,
                bmi)

    def get_daily_backlog_history(self, start_date, end_date):
        """
            returns list of tuple (date,stats)
                date is date value in epoc time
                stats is dictionary of {'created':[], 'opened':[], 'closed':[]}
        """

        # this is list of date
        dates = date_range(start_date, end_date + timedelta(days=1), timedelta(days=1))
        end_date = end_date.replace(hour=23, minute=59, second=59)

        # used to lookup the index of date
        dates_index = dict((date.date(),idx) for idx, date in enumerate(dates))

        # each key is the list of list of patch.  The index of the list is corresponding
        # to the index of the date in numdates list.
        backlog_stats = {'created':[], 'opened':[], 'closed':[]}

        # initialize backlog_stats

        for date in dates:
            for key in backlog_stats:
                backlog_stats[key].append([])

        # start by getting the list of opened patch at the end of the start date.
        backlog_stats['opened'][0] = self.get_remaning_opened_patch_on(start_date)

        for patch_info in self.patches_info:

            # only consider the patch that was created before end dates.
            if patch_info.created_date <= end_date:

                # only track the patch that create since start_date
                if patch_info.created_date >= start_date:

                    #get index of day in the dates list
                    index = dates_index[patch_info.created_date.date()]
                    # add patch created patch list
                    backlog_stats['created'][index].append(patch_info.patch_id)

                    if (patch_info.is_closed() and patch_info.closed_date <= end_date):

                        #get index of day in the dates list
                        index = dates_index[patch_info.closed_date.date()]
                        # add patch closed patch list
                        backlog_stats['closed'][index].append(patch_info.patch_id)

        # update opened ticket list
        for idx, list in enumerate(backlog_stats['opened']):

            if idx > 0:

                # merge list of opened ticket from previous day
                list.extend(backlog_stats['opened'][idx-1])

                # add created ticket to opened ticket list
                list.extend(backlog_stats['created'][idx])

                # remove closed ticket from opened ticket list.
                for id in backlog_stats['closed'][idx]:
                    try:
                        list.remove(id)
                    except ValueError, e:
                        pass

                list.sort()

        return (dates, backlog_stats)

    #This method return data point based on Yahoo JSArray format.
    def get_daily_backlog_chart(self, backlog_history):

        dates = backlog_history[0]
        backlog_stats = backlog_history[1]

        # create counted list.
        opened_patches_dataset = [len(list) for list in backlog_stats['opened']]
        created_patches_dataset = [len(list) for list in backlog_stats['created']]
        closed_patches_dataset = [len(list) for list in backlog_stats['closed']]
        # need to add create and closed patch for charting purpose. We want to show
        # closed patches on top of opened patch in bar chart.
#        closed_patches_dataset = []
#        for i in range(len(created_patches_dataset)):
#            closed_patches_dataset.append(created_patches_dataset[i] + len(backlog_stats['closed'][i]))

        bmi_dataset = []
        for i in range(len(opened_patches_dataset)):
            if opened_patches_dataset[i] == 0:
                 bmi_dataset.append(0.0)
            else:
                bmi_dataset.append(float(closed_patches_dataset[i])*100/float(opened_patches_dataset[i]))

        ds_daily_backlog = ''

        for idx, date in enumerate(dates):
            ds_daily_backlog = ds_daily_backlog +  '{ date: "%s", opened: %d, closed: %d, created: %d}, ' \
                          % (date.strftime('%m/%d/%Y'), opened_patches_dataset[idx], \
                             closed_patches_dataset[idx], created_patches_dataset[idx])
        return '[ ' + ds_daily_backlog + ' ];'

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

def date_range(start, end, delta):
    r = (end + delta - start).days
    return [start+timedelta(days=i) for i in range(r)]