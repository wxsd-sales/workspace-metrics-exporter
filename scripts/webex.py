from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests
import threading
import datetime
import random
import time
import json
import jwt
import sys
import re

# Retry / rate-limit tuning
MAX_ATTEMPTS = 5            # total tries per request (covers repeated 429s and transient errors)
BACKOFF_BASE = 1.0         # base seconds for exponential backoff on transient errors
BACKOFF_MAX = 30.0         # cap on a single backoff sleep
RETRYABLE_STATUS = {500, 502, 503, 504}

# Webex API max time range per request, by aggregation. The API limits are
# exclusive (a span of exactly 48 hours is rejected with "Request time span is
# maximum 48 hours"), so we chunk just under the limit. Chunks are contiguous,
# so backing off by one aggregation interval introduces no gaps in the data.
HOURLY_MAX_RANGE = datetime.timedelta(hours=47)   # 'none' and 'hourly' aggregation (limit < 48h)
DAILY_MAX_RANGE = datetime.timedelta(days=29)     # 'daily' aggregation (limit < 30d)

class Webex(object):

    def __init__(self, clientId, clientSecret, workspaceIntegrationJwt, debug=True):
        self.clientId = clientId
        self.clientSecret = clientSecret
        self.workspaceIntegrationJwt = workspaceIntegrationJwt
        self.jwtDecoded = jwt.decode(workspaceIntegrationJwt, options={"verify_signature": False}, algorithms=["HS256"])
        self.refreshToken = self.jwtDecoded['refreshToken']
        self.oauthUrl = self.jwtDecoded['oauthUrl']
        self.appUrl = self.jwtDecoded['appUrl']
        self.debug = debug

        # Shared rate-limit gate used by all ThreadPoolExecutor workers.
        # _rate_limit_until is a time.monotonic() timestamp; 0 = no active cooldown.
        self._rate_limit_lock = threading.Lock()
        self._rate_limit_until = 0.0
        

    def getAccessToken(self):
        print('--------------------------------')
        print('Getting Webex Workspace Integration Access Token')

        payload = json.dumps({
        "grant_type": "refresh_token",
        "client_id": self.clientId,
        "client_secret": self.clientSecret,
        "refresh_token": self.refreshToken
        })
        
        headers = {'Content-Type': 'application/json'}
        response = requests.request("POST", self.oauthUrl, headers=headers, data=payload)
        body = response.json()

        if (self.debug):
            # Redact secrets (access/refresh tokens) before logging the response.
            redacted = dict(body) if isinstance(body, dict) else body
            if isinstance(redacted, dict):
                for secret_key in ('access_token', 'refresh_token'):
                    if secret_key in redacted:
                        redacted[secret_key] = '***REDACTED***'
            print('Access Token Response Status: ' + str(response.status_code))
            print('Access Token Response: ' + str(redacted))
        
        if response.status_code == 200:
            self.accessToken = body['access_token']
            print('Access Token Generated Successfully')
            print('--------------------------------')
        else: 
            sys.exit('Error getting Access Token - Error Code: ' + str(response.status_code))


    def activateIntegration(self):
        print('--------------------------------')
        print('Activating Webex Workspace Integration')

        payload = json.dumps({"provisioningState": "completed"})
        response = self.webexAPI('PATCH', self.appUrl, data=payload)
       
        if response.status_code == 200:
            print('Workspace Integration Activated Successfully')
            print('--------------------------------')
            return 
        else:
            sys.exit('Failed to Activate Workspace Integration - Error Code: ' + str(response.status_code))

       

    def listAllWorkspaces(self, supportedDevices='collaborationDevices') -> list:
        print('--------------------------------')
        print('Discovery all Workspaces in Webex Org')
        workspaces = []
        url = 'https://webexapis.com/v1/workspaces?supportedDevices='+supportedDevices+'&start=0&max=1000'
        while True:
            response = self.webexAPI('GET', url)
            if response.status_code != 200:
                sys.exit('Error Getting Workspaces - Status Code: ' + str(response.status_code))
            body = response.json()
            workspaces = workspaces + body['items']

            if 'link' in response.headers:
                # Request next list of Workspaces if there are more
                url = response.links['next']['url']
            else:
                # If there are no more Workspaces to discovery exit loop
                break
        
         
        print('Number of Workspaces found:', len(workspaces))
        print('--------------------------------')

        return workspaces

    def _format_key(self, key):
        # Convert an API key into spaced Title Case so it aligns with the
        # "Workspace Name" / "Workspace Id" columns.
        # "deviceId" -> "Device Id", "start" -> "Start", "timestamp" -> "Timestamp"
        spaced = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', key).replace('_', ' ')
        return spaced.title()

    def _getWorkspaceMetric(self, query):
        print('Getting '+ query['metricName']+ ' Metrics for Workspace: ' + query['workspace']['displayName'])
        response = self.webexAPI('GET', query['url'])

        try:
            body = response.json()
        except ValueError:
            body = None

        # The metrics payload should contain an 'items' list. If it's missing,
        # the request likely failed (non-2xx) or returned an unexpected shape.
        # Log enough context to diagnose instead of crashing on KeyError, and
        # treat this chunk as having no data so the rest of the export proceeds.
        if not isinstance(body, dict) or 'items' not in body:
            print("WARNING: No 'items' in response for Workspace: '{}' (Id: {})".format(
                query['workspace']['displayName'], query['workspace']['id']))
            print('  Status Code: ' + str(response.status_code))
            print('  Request URL: ' + query['url'])
            print('  Response Body: ' + str(body if body is not None else response.text))
            return []

        # Long/tidy format: one row per data point, including every field
        # present in the item. This avoids the wide timestamp-as-columns
        # layout and keeps all returned metric values without selecting one.
        rows = []
        for item in body['items']:
            row = {
                "Workspace Name": query['workspace']['displayName'],
                "Workspace Id": query['workspace']['id'],
            }
            for key, val in item.items():
                row[self._format_key(key)] = val
            rows.append(row)
        return rows

    def getWorkspaceMetrics(self, workspaces, args):
        print('--------------------------------')
        print('Getting Workspace Metrics')
        print('Metric Name: '+ args.metricName)
        print('Aggregation: '+ args.aggregation) 
        print('--------------------------------')
        queries = self.buildQueries(workspaces, args)

        start = time.time()

        # 
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self._getWorkspaceMetric, queries))
        end = time.time()

        print("Took {} seconds to get {} Workspace Metric requests.".format(round(end - start, 2), len(queries)))

        # Flatten per-request row lists into a single long-format table.
        rows = [row for result in results for row in result]

        report = pd.DataFrame.from_records(rows)

        if not report.empty:
            # Sort by whichever workspace/identity/time columns are present so
            # the result adapts to the fields returned by the chosen aggregation.
            sort_cols = [c for c in
                         ['Workspace Name', 'Workspace Id', 'Device Id', 'Start', 'Timestamp']
                         if c in report.columns]
            report = report.sort_values(by=sort_cols).reset_index(drop=True)

        return report


    
    def _split_time_range(self, start, end, max_delta):
        # Split [start, end] into contiguous chunks no larger than max_delta.
        ranges = []
        chunk_start = start
        while chunk_start < end:
            chunk_end = min(chunk_start + max_delta, end)
            ranges.append((chunk_start, chunk_end))
            chunk_start = chunk_end
        return ranges

    def buildQueries(self, workspaces, args):
        endpoint = 'workspaceMetrics'

        if (args.metricName == 'timeused' or args.metricName == 'timebooked'):
            endpoint = 'workspaceDurationMetrics'

        # 'daily' aggregation allows up to 30 days per request; 'none'/'hourly' up to 48 hours.
        max_delta = DAILY_MAX_RANGE if args.aggregation == 'daily' else HOURLY_MAX_RANGE
        ranges = self._split_time_range(args.start, args.end, max_delta)

        queries = []

        for workspace in workspaces:
            for chunk_start, chunk_end in ranges:
                url = 'https://webexapis.com/v1/'+endpoint+'?workspaceId='+ workspace['id'] +'&metricName='+args.metricName+'&aggregation='+args.aggregation+'&from='+chunk_start.strftime('%Y-%m-%dT%H:00:00Z')+'&to='+chunk_end.strftime('%Y-%m-%dT%H:00:00Z')
                queries.append({
                    'workspace':workspace,
                    'url':url,
                    'metricName': args.metricName})

        return queries

    def _await_rate_limit(self):
        # Block while a shared cooldown (set by a 429 on any thread) is active.
        while True:
            with self._rate_limit_lock:
                wait = self._rate_limit_until - time.monotonic()
            if wait <= 0:
                return
            time.sleep(wait)

    def _trip_rate_limit(self, retry_after):
        # Register a cooldown window shared by all threads. The longest
        # Retry-After wins so no thread shortens another thread's window.
        with self._rate_limit_lock:
            self._rate_limit_until = max(
                self._rate_limit_until, time.monotonic() + retry_after
            )

    def webexAPI(self, method, url, params=None, data={}) -> requests.Response:

        headers = {'Authorization': 'Bearer '  + self.accessToken}

        if method in ['POST', 'PATCH']:
            headers['Content-Type'] = 'application/json'

        for attempt in range(MAX_ATTEMPTS):
            # Respect any cooldown currently in effect before sending.
            self._await_rate_limit()

            try:
                if (self.debug):
                    print('Making Webex API Call: ' + url)
                response = requests.request(method, url, headers=headers, params=params, data=data)
            except requests.RequestException as e:
                # Network-level error: back off and retry.
                print(e)
                if attempt == MAX_ATTEMPTS - 1:
                    raise RuntimeError('Error making Webex API Request: ' + str(e))
                backoff = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** attempt)) + random.uniform(0, 1)
                print('Request error, retrying in {} seconds'.format(round(backoff, 2)))
                time.sleep(backoff)
                continue

            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', BACKOFF_BASE))
                print('Rate limited (429), pausing all requests for {} seconds'.format(retry_after))
                self._trip_rate_limit(retry_after)
                continue

            if response.status_code in RETRYABLE_STATUS:
                if attempt == MAX_ATTEMPTS - 1:
                    return response
                backoff = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** attempt)) + random.uniform(0, 1)
                print('Transient error ({}), retrying in {} seconds'.format(response.status_code, round(backoff, 2)))
                time.sleep(backoff)
                continue

            # Success or non-retryable status: let the caller inspect status_code.
            return response

        raise RuntimeError('Webex API Request failed after {} attempts: {}'.format(MAX_ATTEMPTS, url))