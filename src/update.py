# encoding: utf-8
"""Command-line helper for pre-caching issues in the background."""

import sys
import argparse
from os import environ
from concurrent.futures import ThreadPoolExecutor
from requests_futures.sessions import FuturesSession
from workflow import Workflow


class ConcurrentJiraClient(object):
    """REST API client for background fetching using futures."""

    def __init__(self, url, username, password):
        """Constructor.

        Args:
            url (str):      REST API endpoint URL
            username (str): User name used to authenticate to Jira.
            password (str): The password
        """
        self.url = url
        self.username = username
        self.password = password

    def get_all_issues(self, project_key, total, max_results):
        """Fetch all project issues."""
        log.debug("%s issues to fetch" % total)

        # Setup a session for concurrent fetching
        s = FuturesSession(executor=ThreadPoolExecutor(max_workers=4))
        s.auth = (self.username, self.password)
        s.params = {
            'jql': "project=%s" % project_key,
            'fields': 'summary,description,issuetype,status,resolution',
            'maxResults': max_results
            }
        s.headers = {'Content-Type': 'application/json'}

        def parse_json_cb(sess, resp):
            resp.data = map(lambda item: {
                'key': item['key'],
                'summary': item['fields']['summary'],
                'description': item['fields']['description'],
                'type': item['fields']['issuetype']['name'],
                'status': item['fields']['status']['name'],
                'resolved': True if item['fields']['resolution'] else False
                }, resp.json()['issues'])

        def get_issues(start_at=0):
            future = s.get(
                "%s/search" % self.url,
                params={'startAt': start_at},
                background_callback=parse_json_cb)
            next_at = start_at + max_results
            log.debug("... %s/%s" % (min(next_at, total), total))
            if next_at < total:
                data = get_issues(next_at)
            else:
                return future.result().data
            return future.result().data + data

        issues = get_issues()
        return issues


def main(wf):
    """Parse project key, fetch and cache issues."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--total', type=int, required=True)
    parser.add_argument('--max-results', default=50, type=int)
    parser.add_argument('--max-age', default=600, type=int)
    parser.add_argument('project')
    args = parser.parse_args(wf.args)

    project_key = args.project

    issues = wf.cached_data(
        project_key,
        lambda: jira.get_all_issues(project_key, args.total, args.max_results),
        max_age=args.max_age)
    log.debug("%s issues cached (maxAge: %s)" % (len(issues), args.max_age))


def create_client_from_settings():
    """Get user credentials from the keychain."""
    api_url = environ['JIRA_API_URL']
    username = environ['JIRA_USER']
    password = wf.get_password(username)
    return ConcurrentJiraClient(api_url, username, password)

if __name__ == u'__main__':
    wf = Workflow()
    log = wf.logger
    jira = create_client_from_settings()
    sys.exit(wf.run(main))
