#! /usr/bin/env python3

from . import config

from gi.repository import EDataServer
from gi.repository import EBook

PHONE_PROPS = (
	'mobile-phone',
	'business-phone',
	'home-phone',
	'business-phone-2',
	'home-phone-2',
	'company-phone',
	'other-phone',
	'primary-phone',
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
	c = contacts[0]
	queries = []
	for a in c.get_attributes(EBook.ContactField.TEL):
		value = a.get_value()
		q = EBook.BookQuery.vcard_field_test('TEL',
		                                     EBook.BookQueryTest.CONTAINS,
		                                     value)
		queries.append(q.to_string())
	query = "(or {})".format(' '.join(queries))
	r = abook.get_contacts_sync(query, None)
	abook.add_contacts(contacts, None, callback, None)