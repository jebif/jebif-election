# -*- coding: utf-8 -*-

import datetime

from django.db import models
from django.contrib.auth.models import User

import membership.models as membership

import settings

class Election( models.Model ) :
	opened = models.BooleanField(default=False)
	label = models.CharField(u"Libellé", max_length=50)
	max_choices = models.PositiveSmallIntegerField()
	min_choices = models.PositiveSmallIntegerField(default=0)
	def __unicode__( self ) :
		return "%s" % self.label
	def get_absolute_url( self ) :
		return "/%selection/%d/" % (settings.ROOT_URL, self.id)

class Candidate( models.Model ) :
	election = models.ForeignKey(Election, related_name='candidate')
	label = models.CharField(u"Libellé", max_length=150)
	description = models.TextField("Description")

class Voter( models.Model ) :
	election = models.ForeignKey(Election, related_name='voter')
	member = models.ForeignKey(membership.MembershipInfo)
	passwd = models.CharField(max_length=32, unique=True)
	hasvoted = models.BooleanField(default=False)
	trace = models.CharField(max_length=255)
	def __unicode__( self ) :
		return u"%s/%s" % (self.election, self.member)

class Vote( models.Model ) :
	election = models.ForeignKey(Election, related_name='vote')
	choices = models.ManyToManyField(Candidate)
	trace = models.CharField(max_length=255)

