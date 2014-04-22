#! /usr/bin/env python3

import difflib
import re
import logging
import datetime
import dateutil.parser

from gi.repository import EDataServer
from gi.repository import EBook
from gi.repository.EBookContacts import Contact, ContactField, BookQuery, \
                                        BookQueryTest, VCardFormat

from . import config

logging.basicConfig(filename='/tmp/latre.log', filemode='w', level=logging.DEBUG)

PHONE_PROPS = (
	'primary-phone',
	'mobile-phone',
	'business-phone',
	'home-phone',
	'business-phone-2',
	'home-phone-2',
	'company-phone',
	'other-phone',
	'assistant-phone',
	'callback-phone',
	'car-phone',
	'pager'
)

registry = EDataServer.SourceRegistry.new_sync(None)
source = registry.ref_builtin_address_book()
abook = EBook.BookClient.new(source)
abook.open_sync(False, None)

def get_first_phone(contact):
	for p in PHONE_PROPS:
		prop = contact.get_property(p)
		if prop:
			return prop

def get_repr_name(contact):
	''' Get name to represent. May be name or phone number or email '''
	try:
		return contact.get_property('name').to_string()
	except AttributeError:
		return get_first_phone(contact) or contact.get_property('email-1')

def get_contacts_by_uids(uids):
	# Build query
	queries = []
	for i in uids:
		q = BookQuery.field_test(ContactField.UID, BookQueryTest.IS, i)
		queries.append(q.to_string())
	query = "(or {})".format(' '.join(queries))
	r, cons = abook.get_contacts_sync(query, None)
	if r:
		return cons
	return []

def get_contacts_all():
	r, cons = abook.get_contacts_sync('#t', None)
	if r:
		return cons
	return []

def contact_to_vcard_string(contact, return_name=False):
	contact.inline_local_photos()
	vcard = contact.to_string(getattr(VCardFormat, '30'))
	if return_name:
		name = get_repr_name(contact)
		return vcard, name
	else:
		return vcard

def export_vcards_all(return_name=False):
	for c in get_contacts_all():
		yield contact_to_vcard_string(c, return_name)

def export_vcards_by_uids(uids, return_name=False):
	for c in get_contacts_by_uids(uids):
		yield contact_to_vcard_string(c, return_name)


def contacts_to_edataserver_one_by_one(contacts, callback):
	''' Add contacts to EDataServer, one by one.
	The callback is for the case of single contact adding '''
	for c in contacts:
		# Check if phone number is duplicated with an existing contact.
		# We call this case conflict.
		conflicts = get_conflicts_of_contact(c)
		if conflicts == []:
			# No conflict
			abook.add_contact(c, None, callback, None)
		elif len(conflicts):
			try_solve_conflicts(c, conflicts)


def contacts_to_edataserver_by_group(contacts, callback):
	''' Add a group of contacts to EDataServer.
	Note that the callback here is for the case of adding
	multiple contacts. '''
	contacts = reduce_to_uniques(contacts)
	# First, we test with all numbers here for any one existing already in EDataServer
	numbers = []
	for c in contacts:
		numbers.extend(c.numbers)
	query = make_query_test_any_number_exist(numbers)
	r, conflicts = abook.get_contacts_sync(query, None)
	if not conflicts:
		# No conflict, add in batch
		abook.add_contacts(contacts, None, callback, None)
		return
	# else: One of contacts in group has conflict with database
	for c in contacts:
		narrow_conflicts = narrow_conflicts_around_contact(conflicts, c)
		if not narrow_conflicts:
			# No conflict
			abook.add_contacts((c,), None, callback, None)
		else:
			try_solve_conflicts(c, narrow_conflicts)


def reduce_to_uniques(contacts):
	''' Combines contacts which share 1 or more phone numbers.
	Return list of separated contacts '''
	for c in contacts:
		ats = c.get_attributes(ContactField.TEL)
		c.numbers = frozenset(a.get_value() for a in ats)

	if len(contacts) == 1:
		return contacts
	# More than 1
	uniques = []
	while len(contacts) > 1:
		reduced = []
		picked = contacts[0]
		for c in contacts[1:]:
			if len(picked.numbers & c.numbers):
				picked = meld_to_newer(picked, c)
			else:
				reduced.append(c)
		contacts = reduced
		uniques.append(picked)
	# Add the last remain
	uniques.append(contacts[0])
	return uniques


def make_query_test_any_number_exist(numbers):
	queries = []
	for n in numbers:
		q = BookQuery.vcard_field_test('TEL', BookQueryTest.CONTAINS, n)
		queries.append(q.to_string())
	return "(or {})".format(' '.join(queries))


def get_conflicts_of_contact(contact):
	''' Search among existing contacts for the one having
	1 same phone number as the given contact. '''
	# Build query
	ats = contact.get_attributes(ContactField.TEL)
	numbers = frozenset(a.get_value() for a in ats)
	query = make_query_test_any_number_exist(numbers)
	# Apply query
	r, conflicts = abook.get_contacts_sync(query, None)
	return conflicts


def narrow_conflicts_around_contact(conflicts, contact):
	new = []
	for c in conflicts:
		ats = c.get_attributes(ContactField.TEL)
		cf_numbers = frozenset(a.get_value() for a in ats)
		if cf_numbers.intersection(contact.numbers):
			new.append(c)
	return new


def meld_to_newer(c1, c2):
	rev1 = c1.get_property('Rev')
	d1 = dateutil.parser.parse(rev1)
	rev2 = c2.get_property('Rev')
	d2 = dateutil.parser.parse(rev2)
	if d1 >= d2:
		c = mix_phones(c1, c2)
	else:
		c = mix_phones(c2, c1)
	# Update numbers set
	ats = c.get_attributes(ContactField.TEL)
	c.numbers = frozenset(a.get_value() for a in ats)
	return c


def try_solve_conflicts(newcontact, conflicts):
	# If there is only conflict contact, just solve it with the new one.
	# If there are more, we solve between these contacts first, then solve
	# the last remain with the new.
	existing = conflicts[0]
	for other_existing in conflicts[1:]:
		abook.remove_contact_sync(other_existing, None)
		merge_contacts(existing, other_existing)
	# Merge if differ
	if get_different_fields(existing, newcontact):
		merge_contacts(existing, newcontact)


def merge_contacts(existing, pending):
	''' Update existing contact with detail from new one. '''
	dif_vcardfields = get_different_fields(existing, pending)
	for vcfield in dif_vcardfields:
		if vcfield == 'TEL':
			# Mix phone numbers from pending contact to existing contact
			existing = mix_phones(existing, pending)
		else:
			# Replace other fields of existing contact with pending's ones
			try:
				field = Contact.field_id_from_vcard(vcfield)
			except ValueError:
				logging.info('Field %s seems not to be supported', vcfield)
				continue
			new_attrs = pending.get_attributes(field)
			existing.set_attributes(field, new_attrs)
	abook.modify_contact_sync(existing, None)


def get_different_fields(existing, pending):
	''' At which field two contacts differ? '''
	c1 = existing.to_string(getattr(VCardFormat, '30'))
	c2 = pending.to_string(getattr(VCardFormat, '30'))
	diffields = set()
	for line in difflib.unified_diff(c1.splitlines(), c2.splitlines()):
		if len(line) < 3:
			continue
		leading = line[:3]
		if leading in ('+++', '---', '@@ '):
			continue
		if line[0] in ('-', '+') and line[1:4] not in ('UID', 'REV'):
			m = re.search('([A-Z][-A-Z0-9]+)[:;]', line)
			if m:
				diffields.add(m.group(1))
	return diffields


def mix_phones(existing, pending):
	''' Mix phone numbers from pending contact to existing contact. '''
	tel1 = existing.get_attributes(ContactField.TEL)
	tel2 = pending.get_attributes(ContactField.TEL)
	oldnumbers = [t.get_value() for t in tel1]
	# Get only new phone numbers from pending contact
	newtels = [t for t in tel2 if t.get_value() not in oldnumbers]
	# Add these new phone numbers to existing contact
	newtels.extend(tel1)
	existing.set_attributes(ContactField.TEL, newtels)
	return existing
