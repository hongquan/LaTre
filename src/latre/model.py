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