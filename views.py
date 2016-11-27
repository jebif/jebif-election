# -*- coding: utf-8

from django.core.mail import *
from django.shortcuts import *
from django.views.generic.simple import direct_to_template

from django import forms
from django.core.exceptions import ValidationError

from django.contrib.auth.decorators import user_passes_test

from django.contrib.sites.models import Site

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
		voteA = forms.ChoiceField(label=u"Vote A : %s" % el.voteA_label, # Bilan moral - \"Approuvez vous le bilan moral de l'association ?\"",
						choices=election.Vote._meta.get_field("voteA").choices,
						widget=forms.RadioSelect)
		if el.voteB_label :
			voteB = forms.ChoiceField(label=u"Vote B : %s" % el.voteB_label, # Bilan financier - \"Approuvez vous le bilan financier de l'association ?\"",
						choices=election.Vote._meta.get_field("voteB").choices,
						widget=forms.RadioSelect)
		if el.max_choices > 0 :
			candidates = forms.MultipleChoiceField(label=u"Vote C : Renouvellement du Conseil d'Administration - "
				+ u"\"Voulez-vous que la personne suivante fasse partie du Conseil d'Administration ?\""
				+ ((u" (%d maximum)" % el.max_choices) if el.max_choices < el.candidate.count()
						else u" (sélectionnez tous les candidats que vous souhaitez voir élus)"),
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

			trace = "%s %s(%s)" % (datetime.datetime.now(), request.META.get("REMOTE_HOST"), 
						request.META.get("REMOTE_ADDR"))

			voter = el.voter.get(passwd=d["passwd"])

			vote = election.Vote(election=el)
			vote.trace = trace
			vote.voteA = d["voteA"]
			vote.voteB = d["voteB"] if "voteB" in d else 0
			vote.save()
			vote.choices = d["candidates"] if "candidates" in d else []
			voter.hasvoted = True
			voter.trace = trace
			vote.save()
			voter.save()

			return HttpResponseRedirect("ok/")
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

	nb_voters = el.voter.count()
	total = el.vote_set.count()
	participation = (100.*total)/nb_voters if nb_voters > 0 else 0

	def make_pc( e, t ) :
		e["pc"] = (100.*e["nb"])/t if t > 0 else 0.

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


	aC_nb = el.vote_set.exclude(choices__in=el.candidate.all()).count()
	aC = {"nb": aC_nb}
	make_abstained(aC)

	base = total - aC_nb
	rC = []
	for c in el.candidate.all() :
		nb = c.vote_set.count()
		rC.append({"candidate" : c, "pc": (100.*nb)/base if base > 0 else 0, "nb": nb })
	rC.sort(key=operator.itemgetter("pc"), reverse=True)

	results = {
		"voteA" : tristate_result("voteA"),
		"voteB" : tristate_result("voteB"),
		"voteC" : {"votes": rC, "abstained": aC}
	}

	return direct_to_template(request, "election/results.html", 
		{"election": el, "nb_voters": nb_voters, "participation": participation,
			"total": total, "results": results})
	

@is_admin()
def mailing( request, election_id ) :
	el = election.Election.objects.get(id=election_id)

	def validate_template( value ) :
		if not "%ELECTION_PASSWD%" in value or not "%ELECTION_URL%" in value :
			raise ValidationError(u"Macros %ELECTION_URL% ou %ELECTION_PASSWD non présentes")

	class MailingForm( forms.Form ) :
		email_to = forms.ChoiceField(label=u"Destinataires", choices=[
						("hasnotvoted", u"Seuls les inscrits n'ayant pas voté"),
						("allvoters", u"Tous les inscrits au vote"),
						#("custom", u"Personnalisé"),
						])
		email_from = forms.EmailField(label=u"Expéditeur", initial="iscb.rsg.france@gmail.com")
		email_subject = forms.CharField(label=u"Sujet", initial="[JeBiF] ")
		email_template = forms.CharField(label=u"Modèle du message",
					widget=forms.Textarea(attrs={'cols': 90, 'rows': 30}),
					help_text="Utiliser les macros %ELECTION_URL% et %ELECTION_PASSWD%. Optionnellement: %VOTER_FIRSTNAME%.",
					validators=[validate_template])
		attachment1 = forms.FileField(label=u"Attachement 1", required=False)
		attachment2 = forms.FileField(label=u"Attachement 2", required=False)
	
	def template_instance(tmpl, voter) :
		ELECTION_URL = "http://%s%s" % (Site.objects.get_current().domain, el.get_absolute_url())
		return tmpl.replace("%ELECTION_URL%", ELECTION_URL).replace(
					"%ELECTION_PASSWD%", voter.passwd).replace(
					"%VOTER_FIRSTNAME%", voter.member.firstname)

	message = None
	mode = "init"
	voters = None
	if request.method == "POST" :
		form = MailingForm(request.POST, request.FILES)
		if form.is_valid() :
			d = form.cleaned_data
			message = {
				"from": d["email_from"],
				"subject": d["email_subject"],
				"attachment1" : d["attachment1"],
				"attachment2" : d["attachment2"],
			}
			if d["email_to"] == "hasnotvoted":
				voters = el.voter.filter(hasvoted=False)
			elif d["email_to"] == "allvoters":
				voters = el.voter.all()
			#elif d["email_to"] == "custom":
			#	voters = el.voter.filter(member__email__in=[ ])

			if "do_it" in request.POST :
				def prep_attach( uf ) :
					if uf :
						return { "name": uf.name, "data": uf.read(), "content_type": uf.content_type }
				message["attachment1"] = prep_attach(message["attachment1"])
				message["attachment2"] = prep_attach(message["attachment2"])
				for voter in voters :
					msg_txt = template_instance(d["email_template"], voter)
					email = EmailMessage(message["subject"], msg_txt, message["from"],
								[voter.member.email])
					def attach( uf ) :
						if uf :
							email.attach(uf["name"], uf["data"], uf["content_type"])
					attach(message["attachment1"])
					attach(message["attachment2"])
					email.send()

				return direct_to_template(request, "election/mailing-ok.html",
						{"election": el, "voters": voters})

			else :
				mode = "preview"
				class member :
					firstname = u"Loïc"
				m = member()
				class voter :
					passwd = "PASSWD_TEST"
					member = m
				message["preview"] = template_instance(d["email_template"], voter())

	else :
		form = MailingForm()

	return direct_to_template(request, "election/mailing-form.html",
			{"election": el, "voters": voters, "form": form, "mode": mode,
				"message": message})


