
import os
from datetime import datetime
from dotenv import load_dotenv
from scripts.webex import Webex
from pathlib import Path


load_dotenv()

# Create export filename and directory
reportDataTime = datetime.now().strftime('%Y-%m-%d-%H:00:00')
output_file = 'workspace-metrics-'+reportDataTime+'.csv'
output_dir = Path('./exports')
output_dir.mkdir(parents=True, exist_ok=True)

# Load Workspace Integration ENV variables
clientId = os.getenv("CLIENT_ID")
clientSecret = os.getenv("CLIENT_SECRET")
jwt = os.getenv("JWT")

# Construct Workspace Integration connection
connection = Webex(clientId, clientSecret, jwt)

# Get Access Token and Activate Integration
connection.getAccessToken()
connection.activateIntegration()

# Query all Workspaces in Webex Org
workspaces = connection.listWorkspaces()

print('Number of Workspaces found:', len(workspaces) )

# Get Metrics for all workspaces
report = connection.getMetrics(workspaces, 'peopleCount', 'hourly')


print('Saving Export to:', output_dir / output_file )
# Save Export to CSV file
report.to_csv(output_dir / output_file, index=False)  

