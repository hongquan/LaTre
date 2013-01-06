import os
import os.path
import shutil
import re
import urllib.parse
import concurrent.futures
from gi.repository import EBook
from . import config

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
	vcards = set()
	with concurrent.futures.ThreadPoolExecutor(max_workers=5) as e:
		fts = [e.submit(vcards_from_file, f) for f in files]
	for f in concurrent.futures.as_completed(fts):
		if f.exception() is None:
			vcs = f.result()
			vcards = vcards.union(vcs)
	contacts = [EBook.Contact.new_from_vcard(v) for v in vcards]
	return contacts

def vcards_from_file(fil):
	if fil.startswith('file://'): # fil is a URI
		fil = fil[7:]             # Strip "file://" part
		fil = urllib.parse.unquote(fil)
	elif '://' in fil:            # Other URI schemes (http, ftp...) are rejected
		return
	with open(fil) as fl:
		content = fl.read()
	# There may be multiple vcards in file
	# Use set to avoid duplicated
	vcards = set()
	for m in re.finditer('BEGIN:VCARD.+?END:VCARD', content, re.DOTALL):
		vcards.add(m.group(0))
	return vcards

def contacts_identical(contact1, contact2):
	cformat = getattr(EBook.VCardFormat, '30')
	return (contact1.to_string(cformat) == contact2.to_string(cformat))

def contact_already_in_list(contact, contactlist):
	for c in contactlist:
		if contacts_identical(contact, c):
			return True
	return False
