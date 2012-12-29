#! /usr/bin/env python3

import difflib
import re
from . import config

from gi.repository import EDataServer
from gi.repository import EBook

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

def contacts_to_edataserver(contacts, callback):
	for c in contacts:
		print(c.get_property('mobile-phone'))
		# Check if phone number is duplicated with an existing contact.
		# We call this case conflict.
		conflicts = get_conflict_contacts(c)
		if conflicts == []:
			# No conflict
			abook.add_contact(c, None, callback, None)
		elif len(conflicts):
			try_solve_conflicts(c, conflicts)


def get_conflict_contacts(contact):
	''' Search among existing contacts for the one having
	1 same phone number as the given contact. '''
	# Build query
	queries = []
	for a in contact.get_attributes(EBook.ContactField.TEL):
		value = a.get_value()
		q = EBook.BookQuery.vcard_field_test('TEL',
		                                     EBook.BookQueryTest.CONTAINS,
		                                     value)
		queries.append(q.to_string())
	query = "(or {})".format(' '.join(queries))
	# Apply query
	r, conflicts = abook.get_contacts_sync(query, None)
	return conflicts


def try_solve_conflicts(newcontact, conflicts):
	# If there is only conflict contact, just solve it with the new.
	# If there are more, we solve between these contacts first, then solve
	# the last remain with the new.
	existing = conflicts[0]
	print('Existing', existing.get_property('mobile-phone'))
	for other_existing in conflicts[1:]:
		abook.remove_contact_sync(other_existing, None)
		merge_contacts(existing, other_existing)
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
			field = EBook.Contact.field_id_from_vcard(vcfield)
			new_attrs = pending.get_attributes(field)
			existing.set_attributes(field, new_attrs)
	abook.modify_contact_sync(existing, None)


def get_different_fields(existing, pending):
	''' At which field two contacts differ? '''
	c1 = existing.to_string(getattr(EBook.VCardFormat, '30'))
	c2 = pending.to_string(getattr(EBook.VCardFormat, '30'))
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
	tel1 = existing.get_attributes(EBook.ContactField.TEL)
	tel2 = pending.get_attributes(EBook.ContactField.TEL)
	oldnumbers = [t.get_value() for t in tel1]
	# Get only new phone numbers from pending contact
	newtels = [t for t in tel2 if t.get_value() not in oldnumbers]
	# Add these new phone numbers to existing contact
	newtels.extend(tel1)
	existing.set_attributes(EBook.ContactField.TEL, newtels)
	return existing
