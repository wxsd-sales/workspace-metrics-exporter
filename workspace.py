from datetime import datetime
from dotenv import load_dotenv
from scripts.webex import Webex
from scripts.createJwt import createJwt
from scripts.parameters import CONSOLE_ARGS
from pathlib import Path
import sys
import os

args = CONSOLE_ARGS

if(args.start > args.end):
    sys.exit('To Timestamp can\'t be greater than the From timestamp')

timeRange = args.end - args.start

print(args)

load_dotenv()

# Create export filename and directory
reportDataTime = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
output_file = 'workspace-metrics-'+args.metricName+'-'+args.value+'-'+reportDataTime+'.csv'
output_dir = Path('./exports')
output_dir.mkdir(parents=True, exist_ok=True)

# Load Workspace Integration ENV variables
clientId = os.getenv("CLIENT_ID")
clientSecret = os.getenv("CLIENT_SECRET")
jwt = os.getenv("JWT") 





# Construct Workspace Integration connection
connection = Webex(clientId, clientSecret, jwt, args.debug)

# Get Access Token and Activate Integration
connection.getAccessToken()
connection.activateIntegration()

# Query all Workspaces in Webex Org
workspaces = connection.listAllWorkspaces('collaborationDevices')

print('Number of Workspaces found:', len(workspaces) )

# Query each Workspaces metrics
report = connection.getWorkspaceMetrics(workspaces, args)


# Save Export to CSV file
print('Saving Export to:', output_dir / output_file )
report.to_csv(output_dir / output_file, index=False)  

sys.exit('Finished')