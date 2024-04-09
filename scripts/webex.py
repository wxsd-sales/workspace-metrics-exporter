import requests
from datetime import datetime, timedelta
import pandas as pd
import json
import jwt
import sys

class Webex:

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
        
        headers = {
        'Content-Type': 'application/json'
        }

        response = requests.request("POST", self.oauthUrl, headers=headers, data=payload)

        body = response.json()

        if (self.debug):
            print('Access Token Response:')
            print(body)
        
        if 'access_token' in body:
            self.accessToken = body['access_token']
            print('Access Token Generated')
        else: 
            sys.exit('Error getting Access Token')




    def activateIntegration(self):
        payload = json.dumps({
        "provisioningState": "completed"
        })
        headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + self.accessToken
        }

        response = requests.request("PATCH", self.appUrl, headers=headers, data=payload)

        

    def listWorkspaces(self):
        url = "https://webexapis.com/v1/workspaces?supportedDevices=collaborationDevices"

        payload = {}
        headers = {
        'Authorization': 'Bearer '  + self.accessToken
        }

        response = requests.request("GET", url, headers=headers, data=payload)
        body = response.json()
        return  body['items']


    def getMetrics(self, workspaces, metricName='peopleCount', start= datetime.now(), end= datetime.now()- timedelta(hours=24), aggregation='hourly', value='duration'):

        print('Getting '+ metricName+ ' Metrics - Aggregation: '+ aggregation + ' - Value: ' + value)

        df = pd.DataFrame(columns=['Workspace Name','Workspace Id'])
        # toDate = datetime.now()
        # fromDate =  toDate - timedelta(hours=24)

        for workspace in workspaces:
            print('Getting metrics for '+ workspace['displayName'])
            data = self.getWorkspaceMetrics(workspace['id'], metricName, aggregation, start.strftime('%Y-%m-%dT%H:00:00Z'), end.strftime('%Y-%m-%dT%H:00:00Z'), value)
            
            row = {
                "Workspace Name": workspace['displayName'],
                 "Workspace Id": workspace['id']}
            
            row.update(data)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        return df
            
        

    def getWorkspaceMetrics(self, workspaceId, metricName, aggregation, start, end, value='max'):

        endpoint = 'workspaceMetrics'

        if (metricName == 'timeused' or metricName == 'timebooked'):
            endpoint = 'workspaceDurationMetrics'

        url = 'https://webexapis.com/v1/'+endpoint+'?workspaceId='+ workspaceId +'&metricName='+metricName+'&aggregation='+aggregation+'&from='+start+'&to='+end
        
        if (self.debug):
            print('Making Query: ' + url)

       
        payload = {}
        headers = {
        'Authorization': 'Bearer ' + self.accessToken
        }

        response = requests.request("GET", url, headers=headers, data=payload)
        body = response.json()
        data = {}

        if 'message' in body:
            sys.exit('Error: ' +body['message'])

        if (self.debug):
            print(response.json())
            print('Returned Data for Workspace:')
            print(body['items'])

        for index, item in enumerate(body['items']):
            if value in item:
                data[item['start']] = item[value]
            else:
                data[item['start']] = 0
        
        return data