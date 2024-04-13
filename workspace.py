from datetime import datetime
from dotenv import load_dotenv
from scripts.webex import Webex
from scripts.parameters import CONSOLE_ARGS
from pathlib import Path
import sys
import os

args = CONSOLE_ARGS

if(args.start > args.end):
    sys.exit('To Timestamp can\'t be greater than the From timestamp')

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

report = connection.getWorkspaceMetrics(workspaces, args)



print('Saving Export to:', output_dir / output_file )
# Save Export to CSV file
report.to_csv(output_dir / output_file, index=False)  

sys.exit('Finished')


# sys.exit('Finished')
# Get Metrics for all workspaces
report = connection.getMetrics(workspaces, args.metricName, args.start, args.end, args.aggregation, args.value)


sys.exit('Finished')
print('Saving Export to:', output_dir / output_file )
# Save Export to CSV file
report.to_csv(output_dir / output_file, index=False)  

