import os
import os.path
import shutil
import concurrent.futures
from gi.repository import EBook
from . import config
from . import vcard

_data_dir = config.data_dir

def run_from_source():
	''' If running from source, return source folder path,
	otherwise, return False '''
	cdir = os.path.dirname(__file__)   # Current dir of the script
	pdir = os.path.normpath(os.path.join(cdir, '..'))  # Parent dir
	path = os.path.split(pdir)
	return path[0] if path[1] == 'src' else False

src = run_from_source()  # Whether run from source
if src is not False:
	_data_dir = os.path.join(src, 'data')


def uifile(name):
	fname =  name + '.ui'
	fpath = os.path.join(_data_dir, fname)
	if not os.path.exists(fpath):
		raise IOError('UI file {} does not exist.'.format(fpath))
	return fpath

def iconfile():
	return os.path.join(_data_dir, config.package + '.svg')

def contacts_from_files(files):
	contacts = []
	with concurrent.futures.ThreadPoolExecutor(max_workers=5) as e:
		fts = [e.submit(contact_from_file, f) for f in files]
	for f in concurrent.futures.as_completed(fts):
		if f.exception() is None:
			con = f.result()
			# Avoid duplicate
			if not contact_already_in_list(con, contacts):
				contacts.append(con)
	return contacts

def contact_from_file(fil):
	with open(fil) as fl:
		content = fl.read()
	# Assume that vcard file contains only 1 contact
	return EBook.Contact.new_from_vcard(content)

def contacts_identical(contact1, contact2):
	cformat = getattr(EBook.VCardFormat, '30')
	return (contact1.to_string(cformat) == contact2.to_string(cformat))

def contact_already_in_list(contact, contactlist):
	for c in contactlist:
		if contacts_identical(contact, c):
			return True
	return False
