# encoding: utf-8
"""Command-line helper for the Alfred-Issues workflow."""

import sys
import argparse
import re
import subprocess
from os import environ, walk, path
from workflow import Workflow, PasswordNotFound
from workflow.background import run_in_background, is_running

from jira import Client
from feedback import Feedback

DEFAULT_MAX_AGE = 600


def get_recent():
    """Get recent issues."""
    recent = wf.stored_data('recent')
    if not recent:
        recent = []
    return recent


def add_recent(issue_key):
    """Add issue to 9 recently worked on."""
    recent = get_recent()
    if issue_key in recent:
        recent.remove(issue_key)
    recent.insert(0, issue_key)
    if len(recent) > 9:
        recent.pop()
    wf.store_data('recent', recent)


def key_for_projects(project):
    """Generate a string search key for a Jira projects."""
    return u' '.join([
        project['key'],
        project['name']])


def key_for_issues(issue):
    """Generate a string search key for a Jira issues."""
    return u' '.join([
        issue['key'],
        issue['summary']])


def key_for_users(user):
    """Generate a string search key for a Jira users."""
    return u' '.join([
        user['name'],
        user['displayName']])


def search_for_projects(query):
    """Search for projects matching a query."""
    jira = create_client_from_settings()
    projects = wf.cached_data(
        '_projects',
        jira.get_projects,
        max_age=DEFAULT_MAX_AGE)

    if query:
        projects = wf.filter(query, projects, key_for_projects)
    else:
        fb.add_item_info('No active project')

    if not projects:  # we have no data to show, so show a warning and stop
        fb.add_item_warning('No matching projects found')
        return

    for project in projects:
        fb.add_item_project(project)


def search_for_issues_cached(query, project_key):
    """Cache all issues in a project and search."""
    is_cached = wf.cached_data_age(project_key) > 0

    # Start update script if cached data is too old (or doesn't exist)
    if not wf.cached_data_fresh(project_key, max_age=DEFAULT_MAX_AGE):
        # Fetch total issue count first
        jira = create_client_from_settings()
        total = jira.get_total(project_key)
        cmd = [
            '/usr/bin/python',
            wf.workflowfile('update.py'),
            project_key,
            "--total=%s" % total]
        run_in_background('update', cmd)

    # Notify the user if the cache is being updated
    if is_running('update'):
        fb.add_item_updating()
    elif is_cached:
        fb.add_item_active_project(project_key)

    issues = wf.cached_data(project_key, None, max_age=0)
    if issues and query:
        issues = wf.filter(query, issues, key=key_for_issues)

    if not issues:
        if is_cached:
            fb.add_item_warning("No issues found in project %s" % project_key)
        return

    for issue in issues:
        fb.add_item_issue(issue)


def search_for_issues(query, project_key):
    """Search for issues matching a query in a project."""
    # TODO: Make this an option?
    jira = create_client_from_settings()
    issues = jira.search(query, project=project_key)

    if not issues:
        fb.add_item_warning("No issues found in project %s" % project_key)
        return

    for issue in issues:
        fb.add_item_issue(issue)


def search_for_my_issues(query):
    """Search for issues assigned to me."""
    jira = create_client_from_settings()
    issues = jira.search(
        query,
        assignee='currentUser()',
        resolution='Unresolved')

    if not issues:
        fb.add_item_warning('No matching issues assigned to you')
        return

    for issue in issues:
        fb.add_item_issue(issue)


def search_for_recent(query):
    """Search for issues recently worked on."""
    recent_keys = get_recent()
    jira = create_client_from_settings()
    recent = jira.get_issues(recent_keys) if len(recent_keys) > 0 else []

    # Sort the issues according to recently used
    issues = sorted(recent, key=lambda issue: recent_keys.index(issue['key']))

    # Check if all issues could not be fetched
    if len(recent_keys) != len(recent):
        valid_keys = [issue['key'] for issue in issues]
        wf.store_data('recent', valid_keys)

    if query and issues:
        issues = wf.filter(query, issues, key_for_issues)

    if not issues:
        fb.add_item_warning('No recent issues')
        return

    for issue in issues:
        fb.add_item_issue(issue)


def new_issue(summary):
    """Prompt creating a new issue from clipboard."""
    active_project = wf.settings['active_project']

    if not active_project:
        fb.add_item_warning('No active project')
        return

    def get_clipboard_data():
        p = subprocess.Popen(['pbpaste'], stdout=subprocess.PIPE)
        retcode = p.wait()
        return p.stdout.read().strip() if retcode == 0 else None

    data = get_clipboard_data()
    wf.cache_data('_clipboard', data)

    fb.add_item_clipboard(data)
    for issue_type in active_project['issueTypes']:
        fb.add_item_new(active_project['key'], issue_type, summary)


def create_issue_from_clipboard(project_id, type_id, summary):
    """Create a new issue with a description from the cached clipboard."""
    description = wf.cached_data('_clipboard', max_age=0)
    if not description:
        print 'Nothing to create'
        return

    jira = create_client_from_settings()
    try:
        key = jira.create_issue(project_id, type_id, summary, description)
        add_recent(key)
        wf.clear_cache(lambda name: name.startswith('_clipboard'))
        print "Issue %s created" % key
    except:
        print "Error creating issue: %s" % sys.exc_info()[0]


def edit_issue(issue_key, field, value):
    """Edit issue fields."""
    jira = create_client_from_settings()
    if field == 'assignee':  # Assign issue
        users = jira.get_users(issue_key, value)
        for user in users:
            fb.add_item_assign_user(user, issue_key)

    # Add a comment
    elif field == 'comment':
        fb.add_item_comment_new(issue_key, value)

        comments = jira.get_comments(issue_key)
        if not comments:
            fb.add_item_warning('No comments yet')
            return

        for comment in comments:
            fb.add_item_comment(issue_key, comment)

    # Upload an attachment
    elif field == 'attachment':
        matching_files = [
            (f, path.join(root, f))
            for root, dirs, files in walk(path.expanduser(u'~/Desktop'))
            for f in files
            if value.lower() in f.lower() and not f.startswith(u'.')]

        if not matching_files:
            fb.add_item_warning('No matching files')
            return

        for (name, filepath) in matching_files:
            fb.add_item_file(issue_key, name, filepath)

    # Change any other field
    else:
        fb.add_item_field_edit(issue_key, field, value)


def show_issue(issue_key):
    """Show issue details."""
    jira = create_client_from_settings()
    issue = jira.get_issue(issue_key)  # Do not cache
    if not issue:
        fb.add_item_warning("Issue %s does not exist" % issue_key)
        return

    add_recent(issue['key'])

    active_project = wf.settings['active_project']
    project_key = active_project['key'] if active_project else None

    project = issue['project']
    if project != project_key:
        switch_project(project_key, project)

    fb.add_item_current_issue(issue, project)

    # Only show edit actions if editing is allowed
    can_edit = 'edit-issue' in issue['operations']
    fb.add_item_summary(issue, editable=can_edit)

    # Only enable commenting if comments are allowed
    if 'comment-issue' in issue['operations']:
        fb.add_item_comments_add(issue)
    else:
        fb.add_item_comments(issue)

    if can_edit:
        fb.add_item_attachments_add(issue)
    else:
        fb.add_item_attachments(issue)

    # Show issue reporter
    fb.add_item_reporter(issue)

    # Only show assign action if assigning is allowed
    can_assign = 'assign-issue' in issue['operations']
    fb.add_item_assignee(issue, editable=can_assign)

    # List valid transitions
    for transition in issue['transitions']:
        fb.add_item_transition(issue['key'], transition)


def update_issue(issue_key, field, value):
    """Update issue fields."""
    jira = create_client_from_settings()
    try:
        if field == 'comment':
            jira.add_comment(issue_key, body=value)
            print "Comment added to issue %s" % issue_key
        elif field == 'status':
            jira.set_status(issue_key, status=value)
            print "Issue %s status changed to '%s'" % (issue_key, value)
        elif field == 'assignee':
            jira.set_assignee(issue_key, name=value)
            print "Issue %s assigned to '%s'" % (issue_key, value)
        elif field == 'attachment':
            jira.add_attachment(issue_key, filepath=value)
            print "File '%s' attached to issue %s" % (value, issue_key)
        else:
            jira.set_field(issue_key, field, value)
            print "Issue %s %s changed to '%s'" % (issue_key, field, value)
    except:
        print "Error updating %s: %s" % (issue_key, sys.exc_info()[0])


def switch_project(old_project, new_project):
    """Change or reset active project."""
    if new_project == old_project:
        wf.settings['active_project'] = None
    else:
        # Invalidate cache when switching projects
        wf.cache_data(new_project, None)
        jira = create_client_from_settings()
        wf.settings['active_project'] = jira.get_project(new_project)


def main(wf):
    """Handle actions from Alfred."""
    # FIXME: This is too complex. Simplify
    parser = argparse.ArgumentParser()
    parser.add_argument('--my', action='store_true')
    parser.add_argument('--set-project', dest='new_project')
    parser.add_argument('--issue', nargs='?')
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--recent', action='store_true')
    parser.add_argument('--new', action='store_true')
    parser.add_argument('--create', dest='new_issue')
    parser.add_argument('query', nargs='?')
    args = parser.parse_args(wf.args)

    query = args.query.strip() if args.query else None

    active_project = wf.settings.get('active_project')
    project_key = active_project['key'] if active_project else None

    if args.new_project:
        switch_project(project_key, args.new_project)
        return 0  # Suppress feedback
    elif args.issue:
        cmd = re.match(r'(.+) (.+)=(.*)', args.issue)
        if cmd:  # The query string is a command on an issue
            issue_key, field, value = cmd.group(1), cmd.group(2), cmd.group(3)
            if args.update:
                update_issue(issue_key, field, value)
                return 0  # Suppress feedback
            else:
                edit_issue(issue_key, field, value)
        else:  # Display an issue and applicable commands
            issue_key = args.issue.strip().split(' ', 1)[0]
            show_issue(issue_key)
    elif args.my:
        search_for_my_issues(query)
    elif args.recent:
        search_for_recent(query)
    elif args.new:
        new_issue(query)
    elif args.new_issue:
        cmd = re.match(r'(.+):(.+)', args.new_issue)
        type_id, summary = cmd.group(1), cmd.group(2)
        create_issue_from_clipboard(active_project['id'], type_id, summary)
        return 0
    elif active_project:
        search_for_issues_cached(query, project_key)
    else:
        search_for_projects(query)

    if fb:
        # Send output to Alfred
        print fb.items_json
    else:
        # FIXME: Handle error feedback
        wf.send_feedback()


def create_client_from_settings():
    """Get user credentials from the keychain."""
    api_url = environ['JIRA_API_URL']
    if not api_url:  # API URL has not yet been set
        raise ValueError('JIRA_API_URL not set in the environment variables')
    username = environ['JIRA_USER']
    if not username:  # Username has not yet been set
        raise ValueError('JIRA_USER not set in the environment variables')
    try:
        password = wf.get_password(username)
    except PasswordNotFound:
        password = ''
        wf.save_password(username, password)
    if not password:  # Password has not yet been set
        raise ValueError("Password for '%s' not found in keychain" % username)

    return Client(api_url, username, password)

if __name__ == u'__main__':
    wf = Workflow()
    log = wf.logger
    fb = Feedback()
    sys.exit(wf.run(main))
