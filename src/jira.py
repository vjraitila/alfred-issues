# encoding: utf-8
"""Module for making REST API calls to Jira."""

import base64
import logging
import json

import requests


class Client(object):
    """A class which wraps the Jira REST API."""

    def __init__(self, url, username, password):
        """Constructor.

        Args:
            url (str):      REST API endpoint URL
            username (str): User name used to authenticate to Jira.
            password (str): The password
        """
        self.url = url
        # Workaround for BasicAuth as Jira REST API does not return a 401
        base64string = base64.encodestring(
            "%s:%s" % (username, password)).replace('\n', '')
        self.headers = {
            'Authorization': "Basic %s" % base64string,
            'Content-Type': 'application/json'
            }
        self.log = logging.getLogger('workflow')  # FIXME: Relies on wf lib

    def get_project(self, project_key):
        """Retrieve a project and its valid issue types from Jira."""
        r = requests.get(
            "%s/project/%s" % (self.url, project_key),
            headers=self.headers)
        r.raise_for_status()
        if r.status_code == 404:
            return None
        else:
            r.raise_for_status()

        item = r.json()

        # Build a list of valid issue types
        issue_types = [
            {'id': issue_type['id'], 'name': issue_type['name']}
            for issue_type in item['issueTypes']
            if not issue_type['subtask']]

        return {
            'id': item['id'],
            'key': item['key'],
            'name': item['name'],
            'issueTypes': issue_types
            }

    def get_projects(self):
        """Retrieve all projects from Jira."""
        r = requests.get("%s/project" % self.url, headers=self.headers)
        r.raise_for_status()

        return map(lambda item: {
            'key': item['key'], 'name': item['name']
            }, r.json())

    def search(self, query, **kwargs):
        """Retrieve issues matching a set of criteria."""
        criteria = ['text ~ "%s"' % query] if query else []
        for field, value in kwargs.items():
            criteria.append("%s=%s" % (field, value))

        params = {
            'jql': u' AND '.join(criteria),
            'fields': 'summary,description,issuetype,status,resolution'
            }

        r = requests.get(
            "%s/search" % self.url,
            params=params,
            headers=self.headers)
        r.raise_for_status()

        return map(lambda item: {
            'key': item['key'],
            'summary': item['fields']['summary'],
            'description': item['fields']['description'],
            'type': item['fields']['issuetype']['name'],
            'status': item['fields']['status']['name'],
            'resolved': True if item['fields']['resolution'] else False
            }, r.json()['issues'])

    def get_total(self, project_key):
        """Retrieve total count of issues in a project."""
        # Fetch total issue count first
        r = requests.get(
            "%s/search" % self.url,
            params={'jql': "project=%s" % project_key, 'maxResults': 0},
            headers=self.headers)
        r.raise_for_status()
        return r.json()['total']

    def get_issue(self, issue_key):
        """Retrieve a single issue."""
        params = {
            'fields': 'project,summary,description,issuetype,priority,status,'
                      'resolution,created,reporter,assignee,comment,'
                      'attachment',
            'expand': 'transitions,operations'
            }

        r = requests.get(
            "%s/issue/%s" % (self.url, issue_key),
            params=params,
            headers=self.headers)
        if r.status_code == 404:
            return None
        else:
            r.raise_for_status()

        item = r.json()
        if item['fields']['assignee']:
            assignee = item['fields']['assignee']['displayName']
        else:
            assignee = None

        # Build a list of valid operations
        operations = [
            link['id']
            for linkGroup in item['operations']['linkGroups']
            for group in linkGroup['groups']
            for link in group['links'] if 'id' in link]

        try:
            attachments = len(item['fields']['attachment'])
        except KeyError:
            attachments = None

        return {
            'key': item['key'],
            'project': item['fields']['project']['key'],
            'summary': item['fields']['summary'],
            'description': item['fields']['description'],
            'type': item['fields']['issuetype']['name'],
            'priority': item['fields']['priority']['name'],
            'status': item['fields']['status']['name'],
            'resolved': True if item['fields']['resolution'] else False,
            'created': item['fields']['created'],
            'reporter': item['fields']['reporter']['displayName'],
            'assignee': assignee,
            'transitions': item['transitions'],
            'operations': operations,
            'comments': len(item['fields']['comment']['comments']),
            'attachments': attachments
            }

    def get_issues(self, issue_keys, retrying=False):
        """Retrieve a set of issues."""
        params = {
            'jql': "key in (%s)" % ','.join(issue_keys),
            'fields': 'summary,description,issuetype,status,resolution'
            }

        r = requests.get(
            "%s/search" % self.url,
            params=params,
            headers=self.headers)
        # Workaround for deleted issues
        if r.status_code == 400 and not retrying:
            valid_keys = [
                issue_key
                for issue_key in issue_keys
                if self.get_issue(issue_key)]
            return self.get_issues(valid_keys, retrying=True)
        else:
            r.raise_for_status()

        return map(lambda item: {
            'key': item['key'],
            'summary': item['fields']['summary'],
            'description': item['fields']['description'],
            'type': item['fields']['issuetype']['name'],
            'status': item['fields']['status']['name'],
            'resolved': True if item['fields']['resolution'] else False
            }, r.json()['issues'])

    def create_issue(self, project_id, type_id, summary, description):
        """Create an issue of a specific issue type."""
        fields = {
            'project': {'id': project_id},
            'issuetype': {'id': type_id},
            'summary': summary,
            'description': description
            }

        r = requests.post(
            "%s/issue" % self.url,
            data=json.dumps({'fields': fields}),
            headers=self.headers)
        r.raise_for_status()

        return r.json()['key']

    def get_users(self, issue_key, username):
        """Retrieve assignable users."""
        params = {
            'issueKey': issue_key,
            'username': username
            }

        try:
            r = requests.get(
                "%s/user/assignable/search" % self.url,
                params=params,
                headers=self.headers)
            r.raise_for_status()
        except:
            return []

        return map(lambda item: {
            'name': item['name'],
            'displayName': item['displayName']
            }, r.json())

    def get_comments(self, issue_key):
        """Retrieve issue comments."""
        try:
            r = requests.get(
                "%s/issue/%s/comment" % (self.url, issue_key),
                headers=self.headers)
            r.raise_for_status()
        except:
            return []

        comments = map(lambda item: {
            'body': item['body'],
            'name': item['author']['name'],
            'displayName': item['author']['displayName'],
            'created': item['created']
            }, r.json()['comments'])

        #  Rest API version 5.2.11 did not support orderBy for comments
        return sorted(
            comments,
            key=lambda comment: comment['created'],
            reverse=True)

    def add_comment(self, issue_key, body):
        """Add comment to an issue."""
        r = requests.post(
            "%s/issue/%s/comment" % (self.url, issue_key),
            data=json.dumps({'body': body}),
            headers=self.headers)
        r.raise_for_status()

    def set_status(self, issue_key, status):
        """Perform transition to change issue state."""
        r = requests.post(
            "%s/issue/%s/transitions" % (self.url, issue_key),
            data=json.dumps({'transition': {'id': status}}),
            headers=self.headers)
        r.raise_for_status()

    def set_assignee(self, issue_key, name):
        """Assign issue to a user."""
        r = requests.put(
            "%s/issue/%s/assignee" % (self.url, issue_key),
            data=json.dumps({'name': name}),
            headers=self.headers)
        r.raise_for_status()

    def add_attachment(self, issue_key, filepath):
        """Upload a file and attach it to an issue."""
        files = {'file': open(filepath, 'rb')}
        headers = self.headers.copy()
        headers['X-Atlassian-Token'] = 'no-check'
        del headers['Content-Type']
        r = requests.post(
            "%s/issue/%s/attachments" % (self.url, issue_key),
            files=files,
            headers=headers)
        r.raise_for_status()

    def set_field(self, issue_key, field, value):
        """Set issue field value."""
        r = requests.put(
            "%s/issue/%s" % (self.url, issue_key),
            data=json.dumps({'fields': {field: value}}),
            headers=self.headers)
        r.raise_for_status()
