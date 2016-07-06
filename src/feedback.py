# encoding: utf-8
"""Module for generating Alfred-Issues Script Filter feedback."""

import json
import urlparse
import urllib
from iso8601 import parse_date

ICON_INFO = 'icons/icon_info.png'
ICON_CACHE = 'icons/icon_cached.png'
ICON_PROJECT = 'icons/icon_assignment.png'
ICON_BACK = 'icons/icon_chevron_left.png'
ICON_ISSUE = 'icons/icon_bug_report.png'
ICON_ISSUE_MISSING = 'icons/icon_bug_report_missing.png'
ICON_TEXT = 'icons/icon_comment.png'
ICON_COMMENT = 'icons/icon_forum.png'
ICON_COMMENT_MISSING = 'icons/icon_forum_missing.png'
ICON_ATTACH = 'icons/icon_attach.png'
ICON_ATTACH_MISSING = 'icons/icon_attach_missing.png'
ICON_USER = 'icons/icon_account_circle.png'
ICON_USER_MISSING = 'icons/icon_account_circle_missing.png'
ICON_TRANSITION = 'icons/icon_share.png'
ICON_ADD = 'icons/icon_add.png'


def pluralize(item, amount):
    """Title for a count of items."""
    if amount == 0:
        return "No %ss yet" % item
    elif amount == 1:
        return "1 %s" % item
    elif amount > 1:
        return "%s %ss" % (amount, item)
    return "<Unable to retrieve %ss. Field hidden?>" % item


class Feedback(object):
    """A class which wraps the feedback to be sent to Alfred."""

    _items = []

    @property
    def items_json(self):
        """Get the feedback in JSON."""
        return json.dumps({'items': self._items})

    def add_item_info(self, message):
        """Add an informational message to Alfred feedback."""
        self._items.append({'title': message, 'valid': False})

    def add_item_warning(self, message):
        """Add a warning message to Alfred feedback."""
        self._items.append({
            'title': message,
            'valid': False,
            'icon': {
                'path': ICON_INFO
            }})

    def add_item_updating(self):
        """Add an updating notification to Alfred feedback."""
        self._items.append({
            'title': 'Updating issues in the background',
            'subtitle': 'Refresh list',
            'icon': {
                'path': ICON_CACHE
            }})

    def add_item_project(self, project):
        """Add a single project item to Alfred feedback."""
        project_key = project['key']
        self._items.append({
            'title': "%s: %s" % (project_key, project['name']),
            'subtitle': 'Set as active project',
            'arg': project_key,
            'icon': {
                'path': ICON_PROJECT
            },
            'mods': {
                'cmd': {
                    'subtitle': 'Open project in the browser'
                },
                'alt': {
                    'subtitle': 'Copy project URL to the clipboard'
                }
            }})

    def add_item_active_project(self, project_key):
        """Add the active project to Alfred feedback."""
        self._items.append({
            'title': "%s is the active project" % project_key,
            'subtitle': 'Change project',
            'arg': project_key,
            'icon': {
                'path': ICON_BACK
            },
            'mods': {
                'cmd': {
                    'subtitle': 'Open active project in the browser'
                },
                'alt': {
                    'subtitle': 'Copy active project URL to the clipboard'
                }
            }})

    def add_item_issue(self, issue):
        """Add a single issue to Alfred feedback."""
        self._items.append({
            'title': "%s: %s" % (issue['key'], issue['summary']),
            'subtitle': 'Work on this issue',
            'arg': issue['key'],
            'icon': {
                'path': ICON_ISSUE_MISSING if issue['resolved'] else ICON_ISSUE
            },
            'mods': {
                'cmd': {
                    'subtitle': 'Open issue in the browser'
                },
                'alt': {
                    'subtitle': 'Copy issue URL to the clipboard'
                }
            },
            'text': {
                'largetype': issue['description']
            }})

    def add_item_clipboard(self, data):
        """Add information about clipboard contents to Alfred feedback."""
        self._items.append({
            'title': "Clipboard has %s characters" % len(data),
            'subtitle': "⌘+L to preview",
            'valid': False,
            'text': {
                'largetype': data
            }})

    def add_item_new(self, project_key, issue_type, summary):
        """Add a new issue to create to Alfred feedback."""
        title = "Create a %s for project %s with summary" % (
            issue_type['name'],
            project_key)

        self._items.append({
            'title': title,
            'subtitle': summary if summary else '(start typing)',
            'arg': "%s:%s" % (issue_type['id'], summary),
            'icon': {
                'path': ICON_ADD
            },
            'valid': True if summary else False
            })

    def add_item_current_issue(self, issue, project):
        """Add the current issue to Alfred feedback."""
        self._items.append({
            'title': "Working on %s | %s | %s | Priority: %s" % (
                issue['key'],
                issue['type'],
                issue['status'],
                issue['priority']),
            'subtitle': 'Return to the project',
            'arg': project,
            'icon': {
                'path': ICON_BACK
            },
            'mods': {
                'cmd': {
                    'arg': issue['key'],
                    'subtitle': 'Open issue in the browser'
                },
                'alt': {
                    'arg': issue['key'],
                    'subtitle': 'Copy issue URL to the clipboard'
                }
            }})

    def add_item_summary(self, issue, editable=True):
        """Add the issue summary field to Alfred feedback."""
        item = {
            'title': issue['summary'],
            'subtitle': 'Edit issue summary',
            'icon': {
                'path': ICON_TEXT
            },
            'valid': editable
            }
        if editable:
            item['autocomplete'] = "%s summary=" % issue['key']
        if issue['description']:
            item['subtitle'] = 'Edit issue summary (⌘+L for description)'
            item['text'] = {'largetype': issue['description']}
        self._items.append(item)

    def add_item_comments_add(self, issue):
        """Add a comment count and edit to Alfred feedback."""
        comments = issue['comments']
        self._items.append({
            'title': pluralize('comment', comments),
            'subtitle':
                'Add and show comments' if comments > 0 else 'Add a comment',
            'icon': {
                'path': ICON_COMMENT if comments > 0 else ICON_COMMENT_MISSING
            },
            'autocomplete': "%s comment=" % issue['key']
            })

    def add_item_comments(self, issue):
        """Add a comment count without edit to Alfred feedback."""
        # TODO: Figure out how to show the comments as well.
        comments = issue['comments']
        self._items.append({
            'title': pluralize('comment', comments),
            'icon': {
                'path': ICON_COMMENT if comments > 0 else ICON_COMMENT_MISSING
            },
            'valid': False
            })

    def add_item_comment_new(self, issue_key, value):
        """Add a new comment to Alfred feedback."""
        self._items.append({
            'title': "Add comment to %s" % issue_key,
            'subtitle': '(start typing)' if not value else value,
            'arg': "%s comment=%s" % (issue_key, value),
            'icon': {
                'path': ICON_COMMENT
            },
            'valid': True if value else False
            })

    def add_item_attachments_add(self, issue):
        """Add an attachment count to Alfred feedback."""
        # TODO: Figure out how to show the attachments as well.
        attachments = issue['attachments']
        self._items.append({
            'title': pluralize('attachment', attachments),
            'subtitle': 'Add a file from your desktop',
            'icon': {
                'path': ICON_ATTACH if attachments > 0 else ICON_ATTACH_MISSING
            },
            'autocomplete': "%s attachment=" % issue['key']
            })

    def add_item_attachments(self, issue):
        """Add an attachment count without edit to Alfred feedback."""
        # TODO: Figure out how to show the attachments as well.
        attachments = issue['attachments']
        self._items.append({
            'title': pluralize('attachment', attachments),
            'icon': {
                'path': ICON_ATTACH if attachments > 0 else ICON_ATTACH_MISSING
            },
            'valid': False
            })

    def add_item_comment(self, issue_key, comment):
        """Add a single comment to Alfred feedback."""
        self._items.append({
            'title': comment['body'],
            'subtitle': "Reply to %s" % comment['displayName'],
            'icon': {
                'path': ICON_COMMENT
            },
            'autocomplete': "%s comment=@%s " % (issue_key, comment['name']),
            'text': {
                'largetype': comment['body']
            }})

    def add_item_file(self, issue_key, name, filepath):
        """Add a single file to attach to Alfred feedback."""
        url = urlparse.urljoin(
            'file:', urllib.pathname2url(filepath.encode('utf-8')))

        self._items.append({
            'title': name,
            'subtitle': 'Attach file',
            'arg': "%s attachment=%s" % (issue_key, filepath),
            'icon': {
                'path': ICON_ATTACH
            },
            'quicklookurl': url
            })

    def add_item_field_edit(self, issue_key, field, value):
        """Add an editable field to Alfred feedback."""
        self._items.append({
            'title': "Change %s %s to" % (issue_key, field),
            'subtitle': '(unchanged)' if not value else value,
            'arg': "%s %s=%s" % (issue_key, field, value),
            'icon': {
                'path': ICON_TEXT
            },
            'valid': True if value else False
            })

    def add_item_assign_user(self, user, issue_key):
        """Add a user to assign to Alfred feedback."""
        self._items.append({
            'uid': user['name'],
            'title': user['displayName'],
            'subtitle': 'Assign issue to this person',
            'arg': "%s assignee=%s" % (issue_key, user['name']),
            'icon': {
                'path': ICON_USER
            }})

    def add_item_reporter(self, issue):
        """Add the issue reporter to Alfred feedback."""
        created = parse_date(issue['created']).strftime('%d.%m.%Y %H:%M')
        self._items.append({
            'title': "Reported by %s (@ %s)" % (issue['reporter'], created),
            'icon': {
                'path': ICON_USER
            }})

    def add_item_assignee(self, issue, editable=True):
        """Add the assignee to Alfred feedback."""
        item = {
            'title': "Assigned to %s" % (issue['assignee'] or 'no one'),
            'icon': {
                'path': ICON_USER if issue['assignee'] else ICON_USER_MISSING
            },
            'valid': editable
            }
        if editable:
            item['subtitle'] = '(Re)assign issue'
            item['autocomplete'] = "%s assignee=" % issue['key']
        self._items.append(item)

    def add_item_transition(self, issue_key, transition):
        """Add an issue transition to Alfred feedback."""
        self._items.append({
            'title': transition['name'],
            'subtitle': 'Change issue status',
            'arg': "%s status=%s" % (issue_key, transition['id']),
            'icon': {
                'path': ICON_TRANSITION
            }})
