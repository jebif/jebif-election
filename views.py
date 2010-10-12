# -*- coding: utf-8

from django.core.mail import *
from django.shortcuts import *
from django.views.generic.simple import direct_to_template

from django import forms
from django.core.exceptions import ValidationError

from django.contrib.auth.decorators import user_passes_test

from jebif import settings

import election.models as election

import datetime
import operator

def vote( request, election_id ) :
	el = election.Election.objects.get(id=election_id)
	if not el.opened :
		return direct_to_template(request, "election/vote-closed.html")

	candidate_choices = [(c.id, c.label) for c in el.candidate.all()]

	def validate_candidates( value ) :
		if len(value) < el.min_choices :
			raise ValidationError(u"Sélectionnez au moins %d candidat(s)." % el.min_choices)
		if len(value) > el.max_choices :
			raise ValidationError(u"Sélectionnez au plus %d candidat(s)." % el.max_choices)

	def validate_passwd( value ) :
		if len(value) != 32 :
			raise ValidationError(u"Clef de vote invaide.")
		try :
			v = el.voter.get(passwd=value)
			if v.hasvoted :
				raise ValidationError(u"Clef de vote déjà utilisée.")
		except election.Voter.DoesNotExist :
			raise ValidationError(u"Clef de vote inconnue.")

	class VoteForm( forms.Form ) :
		voteA = forms.ChoiceField(label=u"Vote A : Bilan moral - \"Approuvez vous le bilan moral de l'association ?\"",
						choices=election.Vote._meta.get_field("voteA").choices,
						widget=forms.RadioSelect)
		voteB = forms.ChoiceField(label=u"Vote B : Bilan financier - \"Approuvez vous le bilan moral de l'association ?\"",
						choices=election.Vote._meta.get_field("voteB").choices,
						widget=forms.RadioSelect)
		candidates = forms.MultipleChoiceField(label=u"Vote C : Renouvellement du Conseil d'Administration - " +
				u"\"Voulez-vous que la personne suivante fasse partie du Conseil d'Administration ?\" (%d maximum)" % el.max_choices,
						required=False,
						choices=candidate_choices,
						widget=forms.CheckboxSelectMultiple,
						validators=[validate_candidates])
		passwd = forms.CharField(label=u"Clef du vote", 
						max_length=32, min_length=32,
						validators=[validate_passwd])

	if request.method == 'POST' :
		form = VoteForm(request.POST)
		if form.is_valid() :
			d = form.cleaned_data

			trace = "%s %s(%s)" % (datetime.datetime.now(), request.META["REMOTE_HOST"], 
						request.META["REMOTE_ADDR"])

			voter = el.voter.get(passwd=d["passwd"])

			vote = election.Vote(election=el)
			vote.trace = trace
			vote.voteA = d["voteA"]
			vote.voteB = d["voteB"]
			vote.save()
			vote.choices = d["candidates"]
			voter.hasvoted = True
			voter.trace = trace
			vote.save()
			voter.save()

			return HttpResponseRedirect("ok")
	else :
		form = VoteForm()

	return direct_to_template(request, "election/vote.html",
			{"election": el, "form": form})



def is_admin() :
	def validate( u ) :
		return u.is_authenticated() and u.is_staff
	return user_passes_test(validate)

@is_admin()
def results( request, election_id ) :
	el = election.Election.objects.get(id=election_id)

	total = el.vote_set.count()

	def make_pc( e, t ) :
		if t > 0 :
			e["pc"] = (100.*e["nb"])/t
		else :
			e["pc"] = 0.

	def make_votes( r ) :
		get_nb = operator.itemgetter("nb")
		r.sort(key=get_nb, reverse=True)
		t = sum(map(get_nb, r))
		for e in r :
			make_pc(e,t)
		return t

	def make_abstained( e ) :
		make_pc(e, total)

	def tristate_result( field ) :
		r = []
		a = None
		for (val, label) in election.Vote._meta.get_field(field).choices :
			d = {"value": val, "label": label, "nb": el.vote_set.filter(**{field: val}).count()}
			if val != 0 :
				r.append(d)
			else :
				a = d
		make_votes(r)
		make_abstained(a)
		return {"votes": r, "abstained": a}
			
	rC = [ { "candidate" : c, "nb" : c.vote_set.count() } for c in el.candidate.all()]
	tC = make_votes(rC)
	aC = {"nb": total-tC}
	make_abstained(aC)

	results = {
		"voteA" : tristate_result("voteA"),
		"voteB" : tristate_result("voteB"),
		"voteC" : {"votes": rC, "abstained": aC}
	}

	return direct_to_template(request, "election/results.html", 
		{"election": el, "total": total, "results": results})
	

@is_admin()
def mailing( request, election_id ) :
	info = MembershipInfo.objects.get(id=info_id)
	info.active = True
	info.inscription_date = datetime.date.today()
	info.save()

	msg_from = "NO-REPLY@jebif.fr"
	msg_to = [info.email]
	msg_subj = "Bienvenue dans l'association JeBiF"
	msg_txt = u"""
Bonjour %s,

Nous avons bien pris en compte ton adhésion à l’association JeBiF. N’hésite pas à nous contacter si tu as des questions, des commentaires, des idées, etc…

Tu connais sans doute déjà notre site internet http://jebif.fr. Tu peux aussi faire un tour sur notre page internationale du RSG-France.
http://www.iscbsc.org/rsg/rsg-france

Tu vas être inscrit à la liste de discussion des membres de l’association. Tu pourras y consulter les archives si tu le souhaites.
http://lists.jebif.fr/mailman/listinfo/membres

A bientôt,
L’équipe du RSG-France (JeBiF)
""" % info.firstname
	send_mail(msg_subj, msg_txt, msg_from, msg_to)

	return HttpResponseRedirect("../../")

