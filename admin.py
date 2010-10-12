
import random

from django.contrib import admin
from django.contrib import messages

import election.models as election
import membership.models as membership

class CandidateInline( admin.TabularInline ) :
	model = election.Candidate

class ElectionAdmin( admin.ModelAdmin ) :
	inlines = [CandidateInline]
	list_display = ('label', 'opened')

	actions = ['populate_voters', 'check_integrity', 'open', 'close']

	def check_integrity( celf, request, queryset ) :
		for el in queryset :
			# ensure uniq (election, member) in Voter
			votersids = [v.id for v in el.voter.only("member__id")]
			if len(votersids) != len(set(votersids)) :
				messages.error(request, "%s: duplicated voters!!")
			# len(vote) == len(voter/hasvoted)
			if el.vote.count() != el.voter.filter(hasvoted=True).count() :
				message.error(request, "%s: mismatch number of votes/voters")
	check_integrity.short_description = "Check integrity of selected elections"

	def _set_opened( celf, request, queryset, opened ) :
		queryset.update(opened=opened)
	def open( celf, request, queryset ) :
		return celf._set_opened(request, queryset, True)
	open.short_description = "Open selected elections"
	def close( celf, request, queryset ) :
		return celf._set_opened(request, queryset, False)
	close.short_description = "Close selected elections"
		
	def populate_voters( celf, request, queryset ) :
		for el in queryset :
			new_voters = membership.MembershipInfo.objects.filter(active=True).exclude(voter__election=el)
			for mi in new_voters :
				nv = election.Voter(election=el, member=mi)
				nv.passwd = "".join([random.choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)") for i in range(32)])
				nv.save()
			messages.success(request, "%s: %d voter(s) added" % (el, new_voters.count()))
	populate_voters.short_description = "Populate voters of selected elections"

admin.site.register(election.Election, ElectionAdmin)
admin.site.register(election.Voter)

