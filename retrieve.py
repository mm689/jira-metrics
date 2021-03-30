#!/usr/bin/env python3
import requests
import sys
import csv
import json
from pprint import pprint
from urllib.parse import urlencode

def config(name: str, arg_index: int = None, optional: bool = False):
    if arg_index is not None and len(sys.argv) > arg_index:
        return sys.argv[arg_index]
    try:
        with open('.' + name, 'r') as config_file:
            return config_file.read().replace('\n', '')
    except FileNotFoundError:
        if optional:
            return None
        print("No " + name + " configuration. Try running this via make.")
        exit(1)

ESTIMATE_FIELDS = ['customfield_10026', 'customfield_10016']

GET_BOARDS_ONLY = '--get-all-boards' in sys.argv
OUTPUT_TO = config('directory', 3, GET_BOARDS_ONLY)
EMAIL = config('email')
PASSWORD = config('apikey')
PROJECT = config('project', 1, GET_BOARDS_ONLY)
BOARD = config('board', 2, GET_BOARDS_ONLY)
JIRA = config('jira-url').rstrip('/')
RESULTS_PER_PAGE = 50

# Debug only: run only one API call per query type, even if multiple would be needed.
LIMIT_API_CALLS = False

# Send off an API request
def retrieve(url: str):
    response = requests.get(JIRA + url, auth=(EMAIL, PASSWORD))
    if response.status_code != 200:
        raise Exception('Received status ' + str(response.status_code) + ' from ' + JIRA + url)
    return response.json()

# Send off a series of API requests, incrementing 'start' each time, until they return nothing
def retrieve_all(base_url: str, get_items, simplify_items):
    page = 0
    start = 0
    all_data = []
    while True:
        try:
            url = base_url + '&startAt=' + str(start) + '&maxResults=' + str(RESULTS_PER_PAGE)
            print("Page {} ({}-{}): {}{}".format(
                page, start, start + RESULTS_PER_PAGE, JIRA, url), file=sys.stderr)
            response = retrieve(url)
            new_data = get_items(response)
            new_data = [ simplify_items(item) for item in new_data ]
            total_results = response['total'] if 'total' in response else None
            if (len(new_data) == 0):
                break
            all_data.extend(new_data)
            if total_results is not None and total_results < start + RESULTS_PER_PAGE:
                break
            page = page + 1
            start = start + RESULTS_PER_PAGE
            if LIMIT_API_CALLS and page > 0:
                break
        except ValueError as e:
            raise e
        except Exception as e:
            print(e)
            break
    return all_data

def prompt_for_estimate_field():
    fields = retrieve("/rest/api/2/field")
    pprint([{
        'id': field['id'],
        'name': field['name']
    } for field in fields])
    print("* Please check the above data structure for an estimate field,")
    print("* then add its 'id' to ESTIMATE_FIELDS in retrieve.py.")
    raise ValueError('No estimate field found')

def issue_estimate(details):
    for field in ESTIMATE_FIELDS:
        if field in details['fields'].keys():
            return details['fields'][field]
    prompt_for_estimate_field()


# Simplify the dict relating to an issue
def issue_details(details):
    return {
        'id': details['key'],
        'created': details['fields']['created'],
        'status': details['fields']['status']['name'],
        'priority': details['fields']['priority']['id'] if details['fields']['priority'] is not None else None,
        'priority_name': details['fields']['priority']['name'] if details['fields']['priority'] is not None else None,
        'type': details['fields']['issuetype']['name'],
        'points': issue_estimate(details),
        'assignee': details['fields']['assignee']['displayName']
            if details['fields']['assignee'] is not None
            else None
    }

# Retrieve meaningful details of the given issue
def issue(issue_id):
    details = retrieve(JIRA + '/rest/api/2/issue/' + issue_id)
    return issue_details(issue_id)

# Retrieve meaningful details of all issues matching the given JQL
def issues(jql):
    return retrieve_all('/rest/api/2/search?jql=' + jql,
        lambda obj: obj['issues'],
        issue_details)

# Simplify the dict relating to a series of status transitions
def transitions_of(issue_details):
    return [
        {
            'issue': issue_details['key'],
            'from': event['fromString'] if 'fromString' in event else None,
            'to': event['toString'] if 'toString' in event else None,
            'date': events['created'] if 'created' in events else None
        }
        for events in issue_details['changelog']['histories']
        for event in events['items']
        if event['field'] == 'status'
    ]

# Retrieve meaningful details of all transitions of all issues matching search query
def transitions(jql):
    all_changesets = retrieve_all(
        '/rest/api/2/search?jql=' + jql + '&expand=changelog',
        lambda row: row['issues'],
        transitions_of)
    return [ changeset for issue_changesets in all_changesets
        for changeset in issue_changesets]

def all_board_names():
    all_boards = retrieve_all('/rest/agile/1.0/board/?',
        lambda row : row['values'],
        lambda board : {
            'id': board['id'],
            'name': board['name'],
            'projectKey': board['location']['projectKey'],
            'projectName': board['location']['projectName'],
            'type': board['type']
        })
    return [b for b in all_boards if b['type'] == 'scrum' or b['type'] == 'simple']

# List all board/project pairings
def print_all_boards(board = None, project = None, all_boards = None):
    if all_boards is None:
        all_boards = all_board_names()
    all_boards = sorted(all_boards, key=lambda b: (b['projectName'] + b['name']).lower())
    print("\nAll available scrum boards:", file=sys.stderr)
    all_boards.insert(0, { 'name': 'Board name to use', 'projectKey': 'Project ID', 'projectName': 'Project name (do not use)'})
    all_boards.insert(1, { 'name': '-----', 'projectKey': '----------', 'projectName': '-----'})
    name_width = max([ len(b['name']) for b in all_boards])
    proj_width = max([ len(b['projectKey']) for b in all_boards])
    print('\n'.join([
        ('{0:>'+str(name_width)+'} | {1:<'+str(proj_width)+'} | {2:<}')
            .format(b['name'], b['projectKey'], b['projectName'])
        for b in all_boards]), file=sys.stderr)

# From the list of all boards, try to guess which one(s) the user wants
def guess_board(board = None, project = None, all_boards = None):
    if all_boards is None:
        all_boards = all_board_names()
    candidates = [ b for b in all_boards if b['projectName'] == board ]
    if len(candidates) == 1:
        return candidates
    return [ b for b in all_boards if project is None or b['projectKey'].lower() == project.lower() ]

# Retrieve metadata about a given board, or give a helpful error
def board(name, project):
    details = retrieve('/rest/agile/1.0/board?' + urlencode({ 'name': name }))
    if len(details['values']) == 0:
        all_boards = all_board_names()
        candidates = guess_board(name, project, all_boards)
        if len(candidates) == 1:
            raise ValueError("Invalid board name\n\n" +
            "To resolve, replace \"{}\" with \"{}\" in your configuration or run `make get-boards`.\n".format(name, candidates[0]['name']))
        print_all_boards(project, all_boards)
        raise ValueError("Board '{}' not found. Please update configs to indicate one of the above".format(name))
    return details['values'][0]

# Simplify the dict relating to a sprint to just store iteration info
def sprint_details(details):
    issue_keys = retrieve_all(
        '/rest/agile/1.0/sprint/{}/issue?'.format(details['id']),
        lambda row: row['issues'],
        lambda row: row['key'])
    return {
        'name': details['name'] if 'name' in details else None,
        'start': details['startDate'] if 'startDate' in details else None,
        'end': details['completeDate'] if 'completeDate' in details else None,
        'state': details['state'] if 'state' in details else None,
        'issues': ';'.join(issue_keys)
    }

def sprints(board_name, project_id):
    board_details = board(board_name, project_id)
    return retrieve_all(
        '/rest/agile/1.0/board/{}/sprint?'.format(board_details['id']),
        lambda row: row['values'],
        sprint_details)

# Write a list of dicts to a CSV file
def write_csv(filename, dataset):
    if len(dataset) == 0:
        raise ValueError("No {} available".format(filename))
    keys = dataset[0].keys()
    filename = OUTPUT_TO + '/' + filename + '.csv'
    with open(filename, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(dataset)

# Write a list of dicts to a JSON file
def write_json(filename, dataset):
    filename = OUTPUT_TO + '/' + filename + '.json'
    with open(filename, 'w') as output_file:
        json.dump(dataset, output_file)

# Write a list of dicts out to file so it can be accessed flexibly
def write(name, dataset):
    write_csv(name, dataset)
    write_json(name, dataset)

if GET_BOARDS_ONLY:
    print_all_boards()
    exit(0)

# Retrieve all data

issues = issues('project=' + PROJECT)
write('issues', issues)

iterations = sprints(BOARD, PROJECT)
write('iterations', iterations)

# Warning: this will send off quite a number of API calls
changes = transitions('project=' + PROJECT) # &status=Done
write('transitions', changes)
