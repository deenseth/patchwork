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


from patchwork.models import Patch, Project, Person
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from patchwork.requestcontext import PatchworkRequestContext
from patchwork.metrics import PatchGroupMetrics, PersonGroupMetrics
from datetime import datetime, timedelta

# Constants
DAYS_BACK = 28

def dashboard(request, project_id):
    context = PatchworkRequestContext(request)
    project = get_object_or_404(Project, linkname = project_id)
    context.project = project

    context['n_patches'] = Patch.objects.filter(project = project,
            archived = False).count()
    context['n_archived_patches'] = Patch.objects.filter(project = project,
            archived = True).count()
    context['n_new_patches'] = Patch.objects.filter(project = project,
            archived = False, state = 1).count()
    context['n_underreview_patches'] = Patch.objects.filter(project = project,
            archived = False, state = 2).count()
    context['n_accepted_patches'] = Patch.objects.filter(project = project,
            archived = False, state = 3).count()
    context['n_rejected_patches'] = Patch.objects.filter(project = project,
            archived = False, state = 4).count()
    context['n_resolved_patches'] = context['n_accepted_patches'] + \
                                    context['n_rejected_patches']

    context['n_reviewers'] = Person.objects.filter(comment__patch__project = project).distinct().count()
    context['n_contributors'] = Person.objects.filter(patch__project = project).distinct().count()

    # Get list of patch for the current project
    patches = Patch.objects.filter(project=project)

    # Populate group metrics statistics
    patch_group_metrics = PatchGroupMetrics(patches)

    context['ds_patches_by_state'] = patch_group_metrics.get_patches_by_state()

    today = datetime.now()
    # get daily backlog history
    last_day = datetime(today.year, today.month, today.day)
    first_day = last_day - timedelta(days=DAYS_BACK)

    backlog_history = patch_group_metrics.get_daily_backlog_history(first_day, last_day)
    context['ds_daily_backlog'] = patch_group_metrics.get_daily_backlog_chart(backlog_history)

    #Contributors Chart
    person_group_metrics = PersonGroupMetrics(Person.objects.filter(comment__patch__project=project).distinct())
    context['ds_contributor_info'] = person_group_metrics.get_contributors_chart()

    return render_to_response('patchwork/analytics.html', context)


def contributors(request, project_id):

    context = PatchworkRequestContext(request)
    project = get_object_or_404(Project, linkname = project_id)
    context.project = project

    #Contributors Chart
    person_group_metrics = PersonGroupMetrics(Person.objects.filter(comment__patch__project=project).distinct())
    context['ds_contributor_info'] = person_group_metrics.get_contributors_chart()


    context['ds_top_submitters'] = person_group_metrics.get_top_submitters(20)
    context['ds_top_reviewers'] = person_group_metrics.get_top_reviewers(20)
    context['ds_top_commenters'] = person_group_metrics.get_top_commenters(20)

    return render_to_response('patchwork/contributors.html', context)

def patches(request, project_id):
    context = PatchworkRequestContext(request)
    project = get_object_or_404(Project, linkname = project_id)
    context.project = project

    # Get list of patch for the current project
    patches = Patch.objects.filter(project=project)

    # Populate group metrics statistics
    patch_group_metrics = PatchGroupMetrics(patches)

    context['patch_duration_stats'] = patch_group_metrics.get_duration_metrics_stats()
    context['patch_frequency_stats'] = patch_group_metrics.get_frequency_metrics_stats()
    
    return render_to_response('patchwork/patch-stats.html', context)