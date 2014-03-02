import os
import subprocess

from ajenti.api import *
from ajenti.plugins.main.api import SectionPlugin
from ajenti.ui import on
from ajenti.ui.binder import Binder

from api import MailManager, Mailbox


@plugin
class MailPlugin (SectionPlugin):
    def init(self):
        self.title = _('Mail')
        self.icon = 'envelope'
        self.category = 'Web'

        self.manager = MailManager.get()

        if not self.manager.is_configured:
            self.append(self.ui.inflate('vh-mail:not-configured'))
        else:
            self.post_init()

    @on('initial-enable', 'click')
    def on_initial_enable(self):
        self.post_init()
        self.manager.save()
        self.refresh()

    def post_init(self):
        self.empty()
        self.append(self.ui.inflate('vh-mail:main'))

        self.binder = Binder(None, self)

        def post_mb_bind(object, collection, item, ui):
            #def manage():
            #    self.context.launch('v:manage-website', website=item)
            #ui.find('manage').on('click', manage)
            pass

        def post_mb_update(object, collection, item, ui):
            if ui.find('password').value:
                item.password = ui.find('password').value

        self.find('mailboxes').post_item_bind = post_mb_bind
        self.find('mailboxes').post_item_update = post_mb_update

        self.binder.setup(self.manager.config)

    @on('new-mailbox', 'click')
    def on_new_mailbox(self):
        self.binder.update()
        mb = Mailbox.create()
        mb.local = self.find('new-mailbox-local').value
        mb.domain = self.find('new-mailbox-domain').value
        mb.password = ''
        self.find('new-mailbox-local').value = ''
        if not mb.local:
            self.context.error(_('Invalid mailbox name'))
        if not mb.domain:
            self.context.error(_('Invalid mailbox domain'))

        self.manager.config.mailboxes.append(mb)
        self.manager.save()
        self.binder.populate()

    def on_page_load(self):
        self.refresh()

    def refresh(self):
        if self.manager.is_configured:
            self.binder.unpopulate().populate()

    @on('save', 'click')
    def save(self):
        self.binder.update()
        self.manager.save()
        self.refresh()
        self.context.notify('info', _('Saved'))
