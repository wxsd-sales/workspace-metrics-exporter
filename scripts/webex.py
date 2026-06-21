from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests
import threading
import random
import time
import json
import jwt
import sys

# Retry / rate-limit tuning
MAX_ATTEMPTS = 5            # total tries per request (covers repeated 429s and transient errors)
BACKOFF_BASE = 1.0         # base seconds for exponential backoff on transient errors
BACKOFF_MAX = 30.0         # cap on a single backoff sleep
RETRYABLE_STATUS = {500, 502, 503, 504}

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
            print('Access Token Response:')
            print(body)
        
        if response.status_code == 200:
            self.accessToken = body['access_token']
            print('Access Token Generated')
        else: 
            sys.exit('Error getting Access Token - Error Code: ' + str(response.status_code))


    def activateIntegration(self):
        payload = json.dumps({"provisioningState": "completed"})
        response = self.webexAPI('PATCH', self.appUrl, data=payload)
       
        if response.status_code == 200:
            print('Activation Completed')
            return 
        else:
            sys.exit('Failed to Activate Workspace Integration - Error Code: ' + str(response.status_code))

       

    def listAllWorkspaces(self, supportedDevices='collaborationDevices') -> list:
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

        return workspaces

    def _getWorkspaceMetric(self, query):
        print('Getting '+ query['metricName']+ ' Metrics for Workspace: ' + query['workspace']['displayName'])
        response = self.webexAPI('GET', query['url'])
        body = response.json()
        data = {}
        for index, item in enumerate(body['items']):
            if query['value'] in item:
                data[item['start']] = item[query['value']]
            else:
                data[item['start']] = 0
        return {
            "Workspace Name": query['workspace']['displayName'],
            "Workspace Id": query['workspace']['id'],
            **data}
    

    def getWorkspaceMetrics(self, workspaces, args):

        print('Getting '+ args.metricName+ ' Metrics - Aggregation: '+ args.aggregation + ' - Value: ' + args.value)
        queries = self.buildQueries(workspaces, args)
        
        start = time.time()

        # 
        with ThreadPoolExecutor(max_workers=10) as executor:
            report = list(executor.map(self._getWorkspaceMetric, queries))
        end = time.time()

        print("Took {} seconds to get {} Workspace Metrics.".format(round(end - start, 2), len(queries)))

        return pd.DataFrame.from_records(report)


    
    def buildQueries(self, workspaces, args):
        endpoint = 'workspaceMetrics'

        if (args.metricName == 'timeused' or args.metricName == 'timebooked'):
            endpoint = 'workspaceDurationMetrics'

        queries = [] 

        for workspace in workspaces:
            url = 'https://webexapis.com/v1/'+endpoint+'?workspaceId='+ workspace['id'] +'&metricName='+args.metricName+'&aggregation='+args.aggregation+'&from='+args.start.strftime('%Y-%m-%dT%H:00:00Z')+'&to='+args.end.strftime('%Y-%m-%dT%H:00:00Z')
            queries.append({
                'workspace':workspace, 
                'url':url,
                'metricName': args.metricName,
                'value': args.value})

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