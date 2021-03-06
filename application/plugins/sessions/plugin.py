from gi.repository import Gtk, Gio, GLib
from widgets.settings_page import SettingsPage


DEFAULT_NAME = _('Default')
DEFAULT_LOCK = False


def register_plugin(application):
	"""Method that Sunflower calls once plugin is loaded"""
	manager = SessionManager(application)
	settings_page = SessionsOptions(
				application.preferences_window,
				application
			)

	settings_page.set_manager(manager)


class Column:
	NAME = 0
	LOCKED = 1
	TAB_COUNT = 2
	INDEX = 3


class SessionsOptions(SettingsPage):
	"""Sessions options extension class"""

	def __init__(self, parent, application):
		SettingsPage.__init__(self, parent, application, 'sessions', _('Sessions'))

		self._options = application.tab_options
		self._manager = None

		# create list box
		container = Gtk.ScrolledWindow()
		container.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
		container.set_shadow_type(Gtk.ShadowType.IN)

		self._store = Gtk.ListStore(str, bool, int, int)

		self._list = Gtk.TreeView()
		self._list.set_model(self._store)
		self._list.set_rules_hint(True)

		# create cell renderers
		cell_name = Gtk.CellRendererText()
		cell_name.set_property('editable', True)
		cell_name.set_property('mode', Gtk.CellRendererMode.EDITABLE)
		cell_name.connect('edited', self._handle_edited_name, 0)

		cell_locked = Gtk.CellRendererToggle()
		cell_locked.set_property('activatable', True)
		cell_locked.connect('toggled', self._handle_lock_toggled, 0)

		cell_count = Gtk.CellRendererText()

		# create columns
		col_name = Gtk.TreeViewColumn(_('Name'), cell_name, text=Column.NAME)
		col_name.set_min_width(200)
		col_name.set_resizable(True)
		col_name.set_expand(True)

		col_locked = Gtk.TreeViewColumn(_('Locked'), cell_locked, active=Column.LOCKED)
		col_count = Gtk.TreeViewColumn(_('Tabs'), cell_count, text=Column.TAB_COUNT)

		self._list.append_column(col_name)
		self._list.append_column(col_locked)
		self._list.append_column(col_count)

		# create controls
		button_box = Gtk.HBox(False, 5)

		button_add = Gtk.Button(stock=Gtk.STOCK_ADD)
		button_add.connect('clicked', self._handle_add_session)

		button_delete = Gtk.Button(stock=Gtk.STOCK_DELETE)
		button_delete.connect('clicked', self._handle_delete_session)

		image_up = Gtk.Image()
		image_up.set_from_stock(Gtk.STOCK_GO_UP, Gtk.IconSize.BUTTON)
		button_move_up = Gtk.Button(label=None)
		button_move_up.add(image_up)
		button_move_up.set_tooltip_text(_('Move up'))
		button_move_up.connect('clicked', self._handle_move_session, -1)

		image_down = Gtk.Image()
		image_down.set_from_stock(Gtk.STOCK_GO_DOWN, Gtk.IconSize.BUTTON)
		button_move_down = Gtk.Button(label=None)
		button_move_down.add(image_down)
		button_move_down.set_tooltip_text(_('Move down'))
		button_move_down.connect('clicked', self._handle_move_session, 1)

		# pack ui
		container.add(self._list)

		button_box.pack_start(button_add, False, False, 0)
		button_box.pack_start(button_delete, False, False, 0)
		button_box.pack_end(button_move_down, False, False, 0)
		button_box.pack_end(button_move_up, False, False, 0)

		self.pack_start(container, True, True, 0)
		self.pack_start(button_box, False, False, 0)

	def _load_options(self):
		"""Load options and update interface"""
		self._store.clear()

		for index, session in enumerate(self._options.section('sessions').get('list')):
			tab_count = 0
			left_section = session.get('left')
			right_section = session.get('right')

			if left_section is not None and 'tabs' in left_section:
				tab_count += len(session.get('left').get('tabs'))

			if right_section is not None and 'tabs' in right_section:
				tab_count += len(session.get('right').get('tabs'))

			self._store.append((session.get('name'), session.get('locked'), tab_count, index))

	def _save_options(self):
		"""Update sessions config file to reflect running program"""
		new_list = []
		session_list = self._options.section('sessions').get('list')
		active_index = self._options.section('sessions').get('current')
		active_name = session_list[active_index].get('name')
		DefaultClass = self._application.plugin_classes['file_list']

		for row in self._store:
			session_index = row[Column.INDEX]

			if session_index > -1:
				# update index of active session
				if row[Column.NAME] == active_name:
					active_index = len(new_list)
				row[Column.INDEX] = len(new_list)

				# append session to the new list
				session_info = session_list[session_index]
				session_info['name'] = row[Column.NAME]
				session_info['locked'] = row[Column.LOCKED]
				new_list.append(session_info)

			else:
				# create new session container
				session_index = len(new_list)
				new_list.append({
						'name': row[Column.NAME],
						'locked': row[Column.LOCKED],
						'left': {
								'active_tab': 0,
								'tabs': [{'class': DefaultClass.__name__}]
							},
						'right': {
								'active_tab': 0,
								'tabs': [{'class': DefaultClass.__name__}]
							}
					})
				row[Column.INDEX] = session_index

		# save new configuration to config file
		self._options.section('sessions').set('list', new_list)
		self._options.section('sessions').set('current', active_index)

		# update menu
		if self._manager is not None:
			self._manager._update_menu()

	def _handle_edited_name(self, cell, path, text, column):
		"""Filter new names"""
		# check if name already exists
		existing_sessions = filter(lambda session: text == session[Column.NAME], self._store)

		if len(existing_sessions) > 0:
			dialog = Gtk.MessageDialog(
									self._parent,
									Gtk.DialogFlags.DESTROY_WITH_PARENT,
									Gtk.MessageType.ERROR,
									Gtk.ButtonsType.OK,
									_('Session with this name already exists.')
								)
			dialog.run()
			dialog.destroy()

			return False

		# change name
		session_iter = self._store.get_iter(path)
		self._store.set_value(session_iter, column, text)

		# enable save button
		self._parent.enable_save()

		return True

	def _handle_lock_toggled(self, cell, path, *ignore):
		"""Handle toggle on session locked state"""
		iter = self._store.get_iter(path)
		self._store.set_value(iter, Column.LOCKED, not self._store.get_value(iter, Column.LOCKED))

		# enable save button
		self._parent.enable_save()

		return True

	def _handle_add_session(self, widget, data=None):
		"""Add new session to the store"""
		# generate unique name
		session_names = [row[Column.NAME] for row in self._store]

		name_base = _('New session')
		new_name = name_base
		index = 1

		while new_name in session_names:
			new_name = '{0} {1}'.format(name_base, index)
			index += 1

		# add session
		self._store.append((new_name, False, 0, -1))

		# enable save button
		self._parent.enable_save()

	def _handle_delete_session(self, widget, data=None):
		"""Remove selected field from store"""
		selection = self._list.get_selection()
		item_list, selected_iter = selection.get_selected()

		if selected_iter is not None:
			# remove item from the store
			item_list.remove(selected_iter)

			# enable save button if item was removed
			self._parent.enable_save()

	def _handle_move_session(self, widget, direction):
		"""Move selected bookmark up or down"""
		selection = self._list.get_selection()
		item_list, selected_iter = selection.get_selected()

		if selected_iter is not None:
			# get iter index
			index = item_list.get_path(selected_iter)[0]

			# depending on direction, swap iters
			if (direction == -1 and index > 0) \
			or (direction == 1 and index < len(item_list) - 1):
				item_list.swap(selected_iter, item_list[index + direction].iter)

			# enable save button if iters were swapped
			self._parent.enable_save()

	def set_manager(self, manager):
		"""Set session manager"""
		self._manager = manager


class SessionManager:
	"""Session manager provides ability to save and restore tab
	layout configuration for different usage cases.

	"""

	def __init__(self, application):
		self._application = application
		self._options = application.tab_options

		# make sure we have a list to store sessions to
		self._options.create_section('sessions').update({
							'list': [{'name': DEFAULT_NAME, 'locked': DEFAULT_LOCK}],
							'current': 0
						})

		# create actions
		self._manage_action = Gio.SimpleAction.new('manage', None)
		self._save_action = Gio.SimpleAction.new('save', None)

		# connect signals
		self._manage_action.connect('activate', self._manage_sessions)
		self._save_action.connect('activate', self._save_session)

		# create menus
		self._popover_menu = Gio.Menu.new()
		self._sessions_menu = Gio.Menu.new()
		self._options_menu = Gio.Menu.new()

		self._options_menu.append(_('Manage sessions'), 'sessions.manage')
		self._options_menu.append(_('Save session'), 'sessions.save')

		self._popover_menu.append_section(None, self._sessions_menu)
		self._popover_menu.append_section(None, self._options_menu)

		# create container for header bar
		self._button = Gtk.MenuButton.new()
		self._button.set_menu_model(self._popover_menu)

		self._action_group = Gio.SimpleActionGroup.new()
		self._action_group.add_action(self._manage_action)
		self._action_group.add_action(self._save_action)

		self._button.insert_action_group('sessions', self._action_group)

		# add session button to header bar
		self._application.header_bar.pack_end(self._button)

		# update menu
		self._update_menu()
		self._update_menu_item()

	def _update_menu(self):
		"""Update main window session menu"""
		self._sessions_menu.remove_all()

		for action_name in self._action_group.list_actions():
			if action_name.startswith('switch_to_'):
				self._action_group.remove_action(action_name)

		# get current session index
		current_session = self._options.section('sessions').get('current')

		# iterate over saved sessions and create menu item for each
		for index, session in enumerate(self._options.section('sessions').get('list')):
			session_name = session.get('name')
			action_name = 'switch_to_{0}'.format(index)

			action = Gio.SimpleAction.new(action_name, None)
			action.connect('activate', self._switch_session, index)
			self._action_group.add_action(action)

			self._sessions_menu.append(session_name, 'sessions.{0}'.format(action_name))

	def _update_menu_item(self):
		"""Update main window menu item to contain session name"""
		current_session = self._options.section('sessions').get('current')
		session_name = self._options.section('sessions').get('list')[current_session].get('name')
		self._button.set_label(session_name)

	def _switch_session(self, action, data, session_index):
		"""Handle clicking on session menu"""
		left_section = self._options.section('left')
		right_section = self._options.section('right')
		section = self._options.section('sessions')
		session_list = section.get('list')
		current_session = section.get('current')

		# do nothing if session is already active
		if current_session == session_index:
			return

		# save current session
		left_notebook = self._application.left_notebook
		right_notebook = self._application.right_notebook

		self._application.save_tabs(left_notebook, 'left')
		self._application.save_tabs(right_notebook, 'right')

		# swap configs
		session_new = session_list[session_index]
		session_current = session_list[current_session]
		is_current_session_locked = session_current.get('locked')

		if right_section is not None:
			if not is_current_session_locked:
				session_current['right'] = right_section._get_data()

			right_section.set('tabs', session_new['right']['tabs'])
			right_section.set('active_tab', session_new['right']['active_tab'])

		if left_section is not None:
			if not is_current_session_locked:
				session_current['left'] = left_section._get_data()

			left_section.set('tabs', session_new['left']['tabs'])
			left_section.set('active_tab', session_new['left']['active_tab'])

		section.set('current', session_index)

		# close old tabs
		for index in xrange(left_notebook.get_n_pages()):
			page = left_notebook.get_nth_page(0)
			self._application.close_tab(left_notebook, page, can_close_all=True)

		for index in xrange(right_notebook.get_n_pages()):
			page = right_notebook.get_nth_page(0)
			self._application.close_tab(right_notebook, page, can_close_all=True)

		# load new tabs
		self._application.load_tabs(self._application.left_notebook, 'left')
		self._application.load_tabs(self._application.right_notebook, 'right')

		# update menu item to show session name
		self._update_menu_item()

	def _save_session(self, *ignore):
		"""Handle creating a new session."""
		section = self._options.section('sessions')
		session_list = section.get('list')
		current_session_index = section.get('current')

		# save current tabs
		self._application.save_tabs(self._application.left_notebook, 'left')
		self._application.save_tabs(self._application.right_notebook, 'right')

		# update options
		left_section = self._options.section('left')
		right_section = self._options.section('right')

		current_session_options = session_list[current_session_index]
		current_session_options['left'] = left_section._get_data()
		current_session_options['right'] = right_section._get_data()

		# save options
		self._options.save()

	def _manage_sessions(self, widget, data=None):
		"""Show preferences window for managing sessions."""
		self._application.preferences_window._show(widget, 'sessions')
