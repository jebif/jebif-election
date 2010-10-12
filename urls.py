
from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template

from election.views import *

urlpatterns = patterns('',
	('^(?P<election_id>\d+)/$', vote),
	('^(?P<election_id>\d+)/ok$', direct_to_template, {"template": "election/vote-ok.html"}),
	('^(?P<election_id>\d+)/results/$', results),
	('^(?P<election_id>\d+)/mailing/$', mailing),
)

