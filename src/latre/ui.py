#!/usr/bin/env python3

from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Gdk
from gi._glib import GError
from . import data
from .model import abook
import gettext

COL_NAME    = 0
COL_DEFNUM  = 1
COL_PHOTO   = 2
COL_UID     = 3

_ = gettext.gettext

class UIFactory():
	''' Allow to retrieve GUI elements as object attributes '''
	def __init__(self, uifile):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(uifile)
		self._pending_handlers = []

	def __getattr__(self, name):
		''' Allow to get UI elements as from dictionary/object attributes '''
		return self.builder.get_object(name)

	def connect_signals(self, obj):
		self.builder.connect_signals(obj)

	def connect_handlers(self, handlers):
		handlers.extend(self._pending_handlers)
		handlersdict = dict([(h.__name__, h) for h in handlers])
		self.connect_signals(handlersdict)

class VCardFileChooser:
	def __init__(self, action=Gtk.FileChooserAction.OPEN):
		self.dialog = Gtk.FileChooserDialog(action=action)
		self.dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
		self.dialog.add_button(Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
		self.dialog.set_select_multiple(True)
		vcardfil = Gtk.FileFilter()
		vcardfil.set_name('vCard files (*.vcf)')
		vcardfil.add_pattern('*.vcf')
		self.dialog.add_filter(vcardfil)
		allfil = Gtk.FileFilter()
		allfil.set_name('All files')
		allfil.add_pattern('*.*')
		self.dialog.add_filter(allfil)

	def run(self):
		return self.dialog.run()

	def destroy(self):
		return self.dialog.destroy()

	def hide(self):
		return self.dialog.hide()

	def get_filenames(self):
		files = self.dialog.get_filenames()
		cur = self.dialog.get_current_folder()
		if cur:
			self.dialog.set_current_folder(cur)
		return files


class LaTreUI(UIFactory):
	def __init__(self):
		f = data.uifile('MainWindow')
		super(LaTreUI, self).__init__(f)
		self._pending_handlers.extend([self.on_contact_tree_key_press_event,
		                               self.on_contact_tree_unselect_all,
		                               self.on_contact_selection_changed])

	def set_accel_quit(self, callback):
		agroup = Gtk.AccelGroup()
		wrapcallback = lambda acgroup, acceleratable, keyval, modifier: callback()
		agroup.connect(ord('q'), Gdk.ModifierType.CONTROL_MASK,
		               Gtk.AccelFlags.LOCKED, wrapcallback)
		self.mainwindow.add_accel_group(agroup)

	def on_contact_tree_key_press_event(self, widget, event):
		if event.keyval == Gdk.KEY_Escape:
			widget.get_selection().unselect_all()
			self.on_contact_tree_unselect_all(widget)

	def on_contact_selection_changed(self, selection):
		if selection.count_selected_rows() == 0:
			self.contactdetail.hide()

	def on_contact_tree_unselect_all(self, treeview):
		self.contactdetail.hide()

	def show_contact(self, uid):
		try:
			r, contact = abook.get_contact_sync(uid, None)
		except GError:
			return
		if not r:
			return
		name = contact.get_property('name').to_string()
		self.contactname.set_text(name)
		self.contactdetail.set_visible(True)
		self.contactdetail.show_all()


class RemovePromptDialog(Gtk.Dialog):
	def __init__(self, name):
		super(RemovePromptDialog, self).__init__('Remove', None,
				Gtk.DialogFlags.MODAL)
		self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.REJECT,
		                 Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT)
		label = Gtk.Label(_("Are you really want to delete ") + name + "?")
		self.vbox.pack_start(label, True, True, 10)
		self.vbox.show_all()