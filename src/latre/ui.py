#!/usr/bin/env python3

import math
import urllib.parse
import gettext

from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import EBook
from gi.repository.GLib import GError
from gi.repository.EBookContacts import Contact, ContactField

from . import data
from . import model
from .model import abook, PHONE_PROPS

COL_NAME    = 0
COL_DEFNUM  = 1
COL_PHOTO   = 2
COL_UID     = 3

SIZE_PHOTO_LIST = 40

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
		title = _('Import') if action == Gtk.FileChooserAction.OPEN else _('Export')
		self.dialog = dialog = Gtk.FileChooserDialog(title, action=action)
		dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
		dialog.add_button(Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
		if action == Gtk.FileChooserAction.OPEN:
			dialog.set_select_multiple(True)
		else:
			grid = Gtk.Grid()
			grid.set_column_spacing(4)
			opt_per = Gtk.RadioButton.new_with_label(None, _('One file per contact'))
			opt_bulk = Gtk.RadioButton.\
			           new_with_label_from_widget(opt_per, _('All to one file'))
			self.opt_v2 = opt_v2 = Gtk.RadioButton.new_with_label(None, _('Ver 2.1'))
			opt_v3 = Gtk.RadioButton.\
			         new_with_label_from_widget(opt_v2, _('Ver 3.0'))
			self.opt_prec = Gtk.CheckButton.new_with_label(_('Compose Unicode'))
			self.opt_strp = Gtk.CheckButton.new_with_label(_('Strip Unicode'))
			opt_per.connect('toggled', self.switch_saving, True)
			opt_bulk.connect('toggled', self.switch_saving, False)
			grid.attach(opt_per, 0, 0, 1, 1)
			grid.attach_next_to(opt_bulk, opt_per, Gtk.PositionType.BOTTOM, 1, 1)
			grid.attach_next_to(opt_v2, opt_per, Gtk.PositionType.RIGHT, 1, 1)
			grid.attach_next_to(opt_v3, opt_v2, Gtk.PositionType.BOTTOM, 1, 1)
			grid.attach_next_to(self.opt_prec, opt_v2, Gtk.PositionType.RIGHT, 1, 1)
			grid.attach_next_to(self.opt_strp, self.opt_prec,
								Gtk.PositionType.BOTTOM, 1, 1)
			grid.show_all()
			self.dialog.set_extra_widget(grid)

		if action == Gtk.FileChooserAction.OPEN or action == Gtk.FileChooserAction.SAVE:
			vcardfil = Gtk.FileFilter()
			vcardfil.set_name('{} (*.vcf)'.format(_('vCard files')))
			vcardfil.add_pattern('*.vcf')
			dialog.add_filter(vcardfil)
			allfil = Gtk.FileFilter()
			allfil.set_name(_('All files'))
			allfil.add_pattern('*.*')
			dialog.add_filter(allfil)

	@property
	def vcard_version(self):
		return '21' if self.opt_v2.get_active() else '30'

	@property
	def to_compose_unicode(self):
		return self.opt_prec.get_active()

	@property
	def to_strip_unicode(self):
		return self.opt_strp.get_active()

	def run(self):
		return self.dialog.run()

	def destroy(self):
		return self.dialog.destroy()

	def hide(self):
		return self.dialog.hide()

	def get_action(self):
		return self.dialog.get_property('action')

	def get_current_folder(self):
		return self.dialog.get_current_folder()

	def get_filename(self):
		return self.dialog.get_filename()

	def get_filenames(self):
		files = self.dialog.get_filenames()
		cur = self.dialog.get_current_folder()
		if cur:
			self.dialog.set_current_folder(cur)
		return files

	def set_current_name(self, name):
		self.dialog.set_current_name(name)

	def switch_saving(self, button, separating):
		if not button.get_active():
			return
		if separating:
			self.dialog.set_action(Gtk.FileChooserAction.SELECT_FOLDER)
		else:
			self.dialog.set_action(Gtk.FileChooserAction.SAVE)


class LaTreUI(UIFactory):
	def __init__(self):
		f = data.uifile('MainWindow')
		super().__init__(f)
		self.make_photos_rounded()
		self._pending_handlers.extend([self.on_contact_tree_key_press_event,
		                               self.on_contact_tree_unselect_all,
		                               self.on_contact_selection_changed])

	def make_photos_rounded(self):
		self.contactphoto._todraw = True  # Prevent the callback below from acting second time.
		self.contactphoto.connect('draw', self.round_contact_photo)
		# TODO: Rounded corner for photos in list.

	def round_contact_photo(self, widget, cairo_ctx, user_data=None):
		# Prevent drawing being done second time.
		widget._todraw = not widget._todraw
		if not widget._todraw:
			return
		size = widget.get_pixel_size()
		cairo_rounded_box(cairo_ctx, 0, 0, size, size, 4)
		cairo_ctx.clip()

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

	def add_contact_to_treeview(self, contact):
		try:
			name = contact.get_property('name').to_string()
		except AttributeError:
			name = model.get_first_phone(contact) or contact.get_property('email-1')
		number = model.get_first_phone(contact)
		uid = contact.get_property('id')
		photo = self.get_contact_photo(contact, SIZE_PHOTO_LIST)
		if photo is None:
			icontheme = Gtk.IconTheme.get_default()
			photo = icontheme.load_icon('avatar-default', SIZE_PHOTO_LIST,
			                            Gtk.IconLookupFlags.USE_BUILTIN)
		self.contactlist.append((name, number, photo, uid))


	def get_contact_photo(self, contact, size=SIZE_PHOTO_LIST):
		photo = contact.get_property('photo')
		if photo:
			uri = photo.get_uri()
			if uri:
				path = urllib.parse.urlparse(uri).path
				path = urllib.parse.unquote(path)
				photo = GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
			else:
				inlined = photo.get_inlined()
				photo = GdkPixbuf.Pixbuf.new_from_inline_at_size(inlined, size, size)
		return photo


	def show_contact(self, uid):
		Gtk.main_iteration()
		try:
			r, contact = abook.get_contact_sync(uid, None)
		except GError:
			return
		if not r:
			return
		#print(contact.to_string(getattr(EBook.VCardFormat, '30')))
		# Name
		try:
			name = contact.get_property('name').to_string()
		except AttributeError:
			name = model.get_first_phone(contact) or contact.get_property('email-1')
		self.contactname.set_text(name)
		# Photo
		size = self.contactphoto.get_pixel_size()
		photo = self.get_contact_photo(contact, size)
		if photo:
			self.contactphoto.set_from_pixbuf(photo)
		else:
			(self.contactphoto.get_icon_name() == ('avatar-default', size)) \
			or self.contactphoto.set_from_icon_name('avatar-default', size)
		# Get the children of contactdetail box
		children = self.contactdetail.get_children()
		# The 2nd child is for showing phone numbers.
		if len(children) == 2:
			# Remove phone numbers of old contact
			self.contactdetail.remove(children[1])
		# Show phone numbers of this new contact
		grid = self.show_phonenumbers(contact)
		self.contactdetail.pack_start(grid,
		                              True, True, 0)
		self.contactdetail.set_visible(True)
		grid.show_all()
		self.contactdetail.show_all()


	def show_phonenumbers(self, contact):
		grid = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)
		# There is a bug in libebook that using Contact.get_poperty() does not
		# retrieve all phone numbers. So we will apply a trick here.
		all_numbers = set()    # All numbers found in vcard.
		tels = contact.get_attributes(ContactField.TEL)
		all_numbers = set([t.get_value() for t in tels])

		counted = set()      # Numbers get via Contact.get_poperty()
		for p in PHONE_PROPS:
			field = p.replace('-', '_')
			fid = Contact.field_id(field)
			value = contact.get_property(p)
			if not value or value == '' or value in counted:
				continue
			counted.add(value)
			name = Contact.pretty_name(fid)
			# Add to UI
			row = self.phonenumber_to_ui(name, value)
			grid.pack_start(row, False, True, 0)

		# Check the remain numbers missed by get_property(). This part won't be needed
		# when the libebook's bug is fixed.
		remains = (t for t in tels if t.get_value() not in counted)
		for attr in remains:
			type_params = attr.get_param('TYPE')
			if 'CELL' in type_params:
				name = Contact.pretty_name(ContactField.PHONE_MOBILE)
			else:
				name = Contact.pretty_name(ContactField.PHONE_OTHER)
			value = attr.get_value()
			row = self.phonenumber_to_ui(name, value)
			grid.pack_start(row, False, True, 0)

		return grid


	def phonenumber_to_ui(self, name, value):
		name = Gtk.Label(name)
		value = Gtk.Label(value)
		value.set_selectable(True)
		value.set_justify(Gtk.Justification.RIGHT)
		value.set_alignment(1, 0.5)
		row = Gtk.Box(Gtk.Orientation.HORIZONTAL)
		row.pack_start(name, False, True, 0)
		row.pack_start(value, True, True, 0)
		return row


class RemovePromptDialog(Gtk.Dialog):
	def __init__(self, name):
		super(RemovePromptDialog, self).__init__('Remove', None,
				Gtk.DialogFlags.MODAL)
		self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.REJECT,
		                 Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT)
		nm = '\n<b>{}</b>'.format(name)
		label = Gtk.Label()
		label.set_line_wrap(True)
		label.set_markup(_("Are you really want to delete") + nm + "?")
		label.set_margin_left(5)
		label.set_margin_right(5)
		label.set_justify(Gtk.Justification.CENTER)
		self.vbox.pack_start(label, True, True, 10)
		self.vbox.show_all()


####  Functions  ####

def cairo_rounded_box(cairo_ctx, x, y, width, height, radius):
	cairo_ctx.new_sub_path()
	cairo_quater_arc(cairo_ctx, x+radius, y+radius, radius, 3)
	cairo_quater_arc(cairo_ctx, x+width-radius, y+radius, radius, 4)
	cairo_quater_arc(cairo_ctx, x+width-radius, y+height-radius, radius, 1)
	cairo_quater_arc(cairo_ctx, x+radius, y+height-radius, radius, 2)


def cairo_quater_arc(cairo_ctx, xc, yc, radius, quater):
	assert type(quater) == int and quater > 0
	if radius <= 0.0:
		cairo_ctx.line_to(xc, yc)
		return
	cairo_ctx.save()
	cairo_ctx.translate(xc, yc)
	start, end = (quater - 1)*math.pi/2, quater*math.pi/2
	cairo_ctx.arc(0, 0, radius, start, end)
	cairo_ctx.restore()
