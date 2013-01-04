#!/usr/bin/env python3

import sys, os, shutil
from distutils.core import setup

sys.path.insert(1, 'src')
from latre.config import version, package

# Copy the script to other place, rename it for building
src_bin = 'src/latre-bin'
bin_folder = 'bin'
bin_file = os.path.join(bin_folder, package)

if len(sys.argv) > 1:
	if not os.path.isdir(bin_folder):
		os.mkdir(bin_folder)
	print('Copy {} to {}'.format(src_bin, bin_file))
	shutil.copy(src_bin, bin_file)


setup(name=package,
	  version=version,
	  description='A phonebook app, allow to import contacts from vCard files, delete contact. This app uses the same storage as GNOME Contacts, so the contacts can seen in both application.',
	  author='Nguyễn Hồng Quân',
	  author_email='ng.hong.quan@gmail.com',
	  url='http://heomoi.wordpress.com',
	  package_dir = {'': 'src'},
	  packages=['latre'],
	  scripts=[bin_file],
	  data_files=[('share/latre', ['data/MainWindow.ui', 'data/latre.svg'])]
)

# Remove the copied file
if os.path.exists(bin_folder):
	print('Remove', bin_folder)
	shutil.rmtree(bin_folder)

