from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests
import time
import json
import jwt
import sys

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

    def webexAPI(self, method, url, params=[], data={}) -> requests.Response:
        
        headers = {'Authorization': 'Bearer '  + self.accessToken}
        
        if method in ['POST', 'PATCH']:
            headers['Content-Type'] = 'application/json'

        while True:
            try:
                if (self.debug):
                    print('Making Webex API Call: ' + url)
                response = requests.request(method, url, headers=headers, params=params, data=data)
                if response.status_code == 429:
                    print('Sleeping for ' + response.headers['Retry-After'] +' seconds')
                    time.sleep(response.headers['Retry-After'])
                else:
                    break
            except Exception as e:
                print(e)
                sys.exit('Error making Webex API Request')
                
        return response