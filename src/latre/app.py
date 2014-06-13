#!/usr/bin/env python3

import os
import concurrent.futures
import gettext
from gi.repository import GLib, Gtk, Gio, Gdk

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
AUTOSCROLL_THRESHOLD = 2

_ = gettext.gettext

class LaTreApp(Gtk.Application):
	# Ref: http://www.micahcarrick.com/tutorials/autotools-tutorial-python-gtk/getting-started.html
	# http://www.micahcarrick.com/gtk3-python-hello-world.html
	def __init__(self, version='0.1'):
		super().__init__(application_id='apps.vn.latre',
		                 flags=Gio.ApplicationFlags.FLAGS_NONE)
		self.set_ui()
		self._autoscroll_allow = 0

		self.connect('activate', self.on_activated)

		# User folder
		if not os.path.exists(config.userdata_dir):
			os.mkdir(config.userdata_dir)
		self.pending_imports = []


	def set_ui(self):
		self.ui = LaTreUI()
		# Drag 'n' drop
		self.ui.contact_tree.enable_model_drag_dest([],
		                                   Gdk.DragAction.COPY)
		self.ui.contact_tree.drag_dest_add_uri_targets()
		# Bind handlers to signals. The handler'name is suggested by Glade.
		self.ui.connect_handlers([self.on_quit_btn_clicked, self.on_btn_ct_add_clicked,
		                          self.on_btn_ct_clear_clicked,
		                          self.on_contact_tree_cursor_changed,
		                          self.on_contact_tree_drag_data_received,
		                          self.on_btn_ct_remove_clicked,
		                          self.on_btn_ct_export_clicked,
		                          self.on_mainwindow_realize])
		self.ui.filechooser = None
		self.ui.set_accel_quit(self.quit)


	def on_activated(self, user_data=None):
		window = self.ui.mainwindow
		window.set_title(config.appname + ' - ' + config.version)
		if data.run_from_source():
			window.set_icon_from_file(data.iconfile())
		else:
			window.set_icon_name(config.package)
		self.add_window(window)
		window.show_all()


	def on_mainwindow_realize(self, widget):
		Gtk.main_iteration()
		self.populate_contact_list()
		self.ui.mainwindow.resize(550, 400)
		# Set pane position
		panewidth = self.ui.mainpane.get_allocated_width()
		position = int(panewidth/3)
		self.ui.mainpane.set_position(position)


	def on_quit_btn_clicked(self, widget, data=None):
		self.quit()


	def on_btn_ct_add_clicked(self, widget, funcdata=None):
		if self.ui.filechoose is None:
			self.ui.filechooser = VCardFileChooser()
		res = self.ui.filechooser.run()
		if res == Gtk.ResponseType.OK:
			files = self.ui.filechooser.get_filenames()
		self.ui.filechooser.hide()

		try:
			Gtk.main_iteration()
			contacts = data.contacts_from_files(files)
			model.contacts_to_edataserver_by_group(contacts, self.contacts_import_done)

		except UnboundLocalError: # files not defined
			return


	def on_btn_ct_remove_clicked(self, widget, funcdata=None):
		selection = self.ui.contact_selection
		if selection.count_selected_rows() == 0:
			return
		model, paths = selection.get_selected_rows()
		names = [model[p][COL_NAME] for p in paths]
		dialog = RemovePromptDialog(', '.join(names))
		response = dialog.run()
		dialog.destroy()
		if response != Gtk.ResponseType.ACCEPT:
			return
		uids = [model[p][COL_UID] for p in paths]
		r = abook.remove_contacts_sync(uids, None)
		if r:
			iters = [model.get_iter(p) for p in paths]
			[model.remove(i) for i in iters]


	def populate_contact_list(self):
		self.ui.btn_ct_add.set_sensitive(False)
		abook.get_contacts('#t', None, self.load_contacts_done, None)


	def load_contacts_done(self, source, res, user_data):
		r, contacts = source.get_contacts_finish(res)
		if r:
			[self.ui.add_contact_to_treeview(c) for c in contacts]
		self.ui.btn_ct_add.set_sensitive(True)
		#self.ui.contact_tree.connect('size-allocate', self.on_contact_tree_size_allocate)
		# For a short time later, the 'size-allocate' will be emitted, but
		# we don't want the autoscroll is active right


	# Auto scroll treeview to end
	def on_contact_tree_size_allocate(self, widget, rectangle, user_data=None):
		# There is a problem that the fist click on tree row will
		# trigger size-allocate, make the tree view scroll to end undesiredly.
		# So we'll ignore the first trigger of this signal
		if self._autoscroll_allow < AUTOSCROLL_THRESHOLD:
			# AUTOSCROLL_THRESHOLD = 2, count the comment in load_contacts_done()
			self._autoscroll_allow += 1
			return
		selection = widget.get_selection()
		# Do not autoscroll when there is row selected
		if not selection.count_selected_rows():
			return
		adj = widget.get_vadjustment()
		diff = adj.get_upper() - adj.get_page_size()
		if adj.get_value() != diff:
			adj.set_value(diff)


	# Callback when a list row is selected. We will show contact then.
	def on_contact_tree_cursor_changed(self, treeview):
		selection = treeview.get_selection()
		if not selection or selection.count_selected_rows() != 1:
			return
		model, (path,) = selection.get_selected_rows()
		uid = model[path][COL_UID]
		self.ui.show_contact(uid)


	# Drag n Drop
	def on_contact_tree_drag_data_received(self, widget, drag_context, x, y, sel_data, info, time):
		uris = sel_data.get_uris()
		Gtk.main_iteration()
		contacts = data.contacts_from_files(uris)
		model.contacts_to_edataserver_by_group(contacts, self.contacts_import_done)


	def on_btn_ct_clear_clicked(self, widget):
		dialog = RemovePromptDialog(_('all contacts'))
		response = dialog.run()
		dialog.destroy()
		if response != Gtk.ResponseType.ACCEPT:
			return
		r, uids = abook.get_contacts_uids_sync('#t', None)
		if not r:
			return
		r = abook.remove_contacts_sync(uids, None)
		if r:
			self.ui.contactlist.clear()


	def on_btn_ct_export_clicked(self, widget):
		# If no contact is chosen, we export all.
		# Otherwise, export selected contacts
		selection = self.ui.contact_selection
		dialog = VCardFileChooser(Gtk.FileChooserAction.SELECT_FOLDER)
		#dialog.set_current_name('Exported contacts')
		resp = dialog.run()
		action = dialog.get_action()
		if action == Gtk.FileChooserAction.SELECT_FOLDER:
			folder = dialog.get_current_folder()
		else:
			filename = dialog.get_filename()
			if not filename.endswith('.vcf'):
				filename = filename + '.vcf'
		# Get options
		options = {
			'vcard_version': dialog.vcard_version,
			'to_compose_unicode': dialog.to_compose_unicode,
			'to_strip_unicode': dialog.to_strip_unicode
		}
		dialog.destroy()
		if resp != Gtk.ResponseType.OK:
			return
		Gtk.main_iteration()
		liststore, paths = selection.get_selected_rows()
		if paths:
			uids = (liststore[p][COL_UID] for p in paths)
		else:
			uids = None

		# Chose to save as separated files
		if action == Gtk.FileChooserAction.SELECT_FOLDER:
			if uids:
				vcards_iter = model.export_vcards_by_uids(uids, options, True)
			else:
				vcards_iter = model.export_vcards_all(options, True)
			for vc, name in vcards_iter:
				if not name:
					continue
				filename = os.path.join(folder, name + '.vcf')
				data.vcard_to_file(vc, filename)
		# Chose to save to common file.
		else:
			if uids:
				vcards = model.export_vcards_by_uids(uids, options)
			else:
				vcards = model.export_vcards_all(options)
			with open(filename, 'w') as fl:
				fl.write('\n'.join(vcards))


	def quit(self):
		abook.cancel_all()
		super(LaTreApp, self).quit()


	# Callback for the case of adding multiple contacts
	def contacts_import_done(self, client, res, user_data):
		success, uids = client.add_contacts_finish(res)
		if not success:
			return
		cons = model.get_contacts_by_uids(uids)
		for c in cons:
			self.ui.add_contact_to_treeview(c)
		self._autoscroll_allow = 0


	# Callback for the case of adding single contact
	def contact_import_done(self, client, res, user_data):
		success, uid = client.add_contact_finish(res)
		if not success:
			return
		r, con = client.get_contact_sync(uid, None)
		if r:
			self.ui.add_contact_to_treeview(con)


if __name__ == '__main__':
	Gdk.threads_init()
	app = LaTreApp(config.version)
	app.run(None)
