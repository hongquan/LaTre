#!/usr/bin/env python3

import os
import concurrent.futures
from gi.repository import Gtk, Gio, Gdk

from gi.repository import EDataServer
from gi.repository import EBook

from . import config
from . import data
from .model import abook
from .ui import COL_UID, COL_NAME
from .ui import LaTreUI, VCardFileChooser, RemovePromptDialog

from . import model

# Errors due to which a contact cannot be imported
TEL_MISSING         = 1
NAME_MISSING        = 2
INTEGRITY_ERROR     = 3
CROSS_OWN_NUMBER    = 4  # Different persons own same number

class LaTreApp(Gtk.Application):
	# Ref: http://www.micahcarrick.com/tutorials/autotools-tutorial-python-gtk/getting-started.html
	# http://www.micahcarrick.com/gtk3-python-hello-world.html
	def __init__(self, version='0.1'):
		super(LaTreApp, self).__init__(application_id='apps.vn.sodien',
		                               flags=Gio.ApplicationFlags.FLAGS_NONE)
		self.set_ui()

		self.connect('activate', self.on_activated)

		# User folder
		if not os.path.exists(config.userdata_dir):
			os.mkdir(config.userdata_dir)
		self.pending_imports = []


	def set_ui(self):
		self.ui = LaTreUI()
		self.ui.connect_handlers([self.on_quit_btn_clicked, self.on_import_btn_clicked,
		                          self.on_clear_btn_clicked,
		                          self.on_contact_tree_size_allocate,
		                          self.on_contact_tree_cursor_changed,
		                          self.on_del_btn_clicked,
		                          self.on_mainwindow_realize])
		self.ui.filechooser = None
		self.ui.set_accel_quit(self.quit)


	def on_activated(self, data=None):
		window = self.ui.mainwindow
		window.set_title(config.appname + ' - ' + config.version)
		window.set_icon_name(config.package)
		self.add_window(window)
		window.show_all()
		#methods = inspect.getmembers(self, predicate=inspect.ismethod)
		#callbacks = [m for n, m in methods if n.startswith('on_')]


	def on_mainwindow_realize(self, widget):
		self.populate_contact_list()
		self.ui.mainwindow.resize(400, 400)


	def on_quit_btn_clicked(self, widget, data=None):
		self.quit()


	def on_import_btn_clicked(self, widget, funcdata=None):
		if self.ui.filechoose is None:
			self.ui.filechooser = VCardFileChooser()
		res = self.ui.filechooser.run()
		if res == Gtk.ResponseType.OK:
			files = self.ui.filechooser.get_filenames()
		self.ui.filechooser.hide()

		try:
			Gtk.main_iteration()
			contacts = data.contacts_from_files(files)
			model.contacts_to_edataserver(contacts, self.contact_import_done)

		except UnboundLocalError: # files not defined
			return


	def on_del_btn_clicked(self, widget, funcdata=None):
		selection = self.ui.contact_selection
		if selection.count_selected_rows() == 0:
			return
		model, itr = selection.get_selected()
		name = model.get_value(itr, COL_NAME)
		dialog = RemovePromptDialog(name)
		response = dialog.run()
		dialog.destroy()
		if response != Gtk.ResponseType.ACCEPT:
			return
		uid = model.get_value(itr, COL_UID)
		r = abook.remove_contact_by_uid_sync(uid, None)
		if r:
			model.remove(itr)


	def populate_contact_list(self):
		self.ui.import_btn.set_sensitive(False)
		r, values = abook.get_contacts_sync('#t', None)
		if r:
			[self.add_contact_to_treeview(c) for c in values]
		self.ui.import_btn.set_sensitive(True)


	def add_contact_to_treeview(self, contact):
		name = contact.get_property('name').to_string()
		number = model.get_first_phone(contact)
		uid = contact.get_property('id')
		self.ui.contactlist.append((name, number, None, uid))


	# Auto scroll treeview to end
	def on_contact_tree_size_allocate(self, widget, event, data=None):
		adj = widget.get_vadjustment()
		adj.set_value(adj.get_upper() - adj.get_page_size())


	def on_contact_tree_cursor_changed(self, treeview):
		selection = treeview.get_selection()
		if not selection:
			return
		model, itr = selection.get_selected()
		if itr:
			uid = model.get_value(itr, COL_UID)
			self.ui.show_contact(uid)


	def on_clear_btn_clicked(self, widget):
		r, uids = abook.get_contacts_uids_sync('#t', None)
		if not r:
			return
		r = abook.remove_contacts_sync(uids, None)
		if r:
			self.ui.contactlist.clear()


	def quit(self):
		super(LaTreApp, self).quit()


	def contacts_import_done(self, client, res, user_data):
		success, uids = client.add_contacts_finish(res)
		if not success:
			return
		for uid in uids:
			r, con = client.get_contact_sync(uid, None)
			if not r:
				continue
			self.add_contact_to_treeview(con)


	def contact_import_done(self, client, res, user_data):
		success, uid = client.add_contact_finish(res)
		if not success:
			return
		r, con = client.get_contact_sync(uid, None)
		if r:
			self.add_contact_to_treeview(con)


if __name__ == '__main__':
	Gdk.threads_init()
	app = LaTreApp(config.version)
	app.run(None)