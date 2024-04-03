import requests
from datetime import datetime, timedelta
import pandas as pd
import json
import jwt

class Webex:

    def __init__(self, clientId, clientSecret, workspaceIntegrationJwt, debug=False):
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
        self.accessToken = body['access_token']



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


    def getMetrics(self, workspaces, metricName='peopleCount', aggregation='hourly' ):

        df = pd.DataFrame(columns=['Workspace Name','Workspace Id'])
        toDate = datetime.now()
        fromDate =  toDate - timedelta(hours=24)

        for workspace in workspaces:
            print('Getting metrics for '+ workspace['displayName'])
            data = self.getWorkspaceMetrics(workspace['id'], metricName, aggregation, toDate.strftime('%Y-%m-%dT%H:00:00Z'), fromDate.strftime('%Y-%m-%dT%H:00:00Z'))
            
            row = {
                "Workspace Name": workspace['displayName'],
                 "Workspace Id": workspace['id']}
            
            row.update(data)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        return df
            
        

    def getWorkspaceMetrics(self, workspaceId, metricName, aggregation, toDate, fromDate, value='max'):

        url = 'https://webexapis.com/v1/workspaceMetrics?workspaceId='+ workspaceId +'&metricName='+metricName+'&aggregation='+aggregation+'&from='+fromDate+'&to='+toDate+'&sortBy=oldestFirst'
        
        if (self.debug):
            print('Making Query: ' + url)

       
        payload = {}
        headers = {
        'Authorization': 'Bearer ' + self.accessToken
        }

        response = requests.request("GET", url, headers=headers, data=payload)
        body = response.json()
        data = {}

        if (self.debug):
            print('Returned Data for Workspace:')
            print(body['items'])

        for index, item in enumerate(body['items']):
            if value in item:
                data[item['start']] = item[value]
            else:
                data[item['start']] = 0
        
        return data