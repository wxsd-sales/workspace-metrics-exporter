import argparse
import datetime

def _valid_date(s: str) -> datetime.datetime:
    try: 
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a valid date: {s!r}")
    

def _add_sub_arguments(parser: argparse.ArgumentParser):

    parser.add_argument('-a', '--aggregation', choices=['hourly', 'daily'],  default='hourly',
                        help='Time unit over which to aggregate measurements - default = hourly.')
    
    parser.add_argument('-f', '--from', dest='start',  type=_valid_date,
                        help='From Time 2024-04-09T17:21:00Z')
    
    parser.add_argument('-t', '--to', dest='end' ,type=_valid_date,
                        help='To Time ISO 2024-04-09T17:21:00Z')
    
    parser.add_argument('-d', '--debug', dest='debug' , action='store_true', default=False,  
                        help='Enable Debug mode for this script')
    

def _add_buckets(parser: argparse.ArgumentParser):
    parser.add_argument('-v', '--value', dest='value', choices=['mean', 'max', 'min'],  default='max',
                        help='Values you want to store')
    


def _parse_arguments():
    parser = argparse.ArgumentParser(prog='UCM_Updater', 
                                 description='This Scripts lets you bulk export Workspace Metrics for your Webex Org')

    subparsers = parser.add_subparsers(dest='metricName', title='Metric Name', description='The type of data to extract.',
                                        help="asdf", required=True)
    

    parser_soundLevel = subparsers.add_parser('soundlevel', help='Estimated averaged sound level in the workspace')
    parser_ambientNoise = subparsers.add_parser('ambientnoise', help='Estimated stationary ambient noise level in the workspace (background noise level)')
    parser_temperature = subparsers.add_parser('temperature', help='Ambient temperature in the workspace')
    parser_humidity = subparsers.add_parser('humidity', help='Relative humidity in the workspace')
    parser_tvoc = subparsers.add_parser('tvoc', help='(Total Volatile Organic Compounds) - Indoor Air Quality')
    parser_peopleCount = subparsers.add_parser('peoplecount', help='Number of detected people in the workspace')
    parser_timeUsed = subparsers.add_parser('timeused', help='Duration for which the workspace has been used')
    parser_timeBooked = subparsers.add_parser('timebooked', help='Duration for which the workspace has been booked')

    _add_sub_arguments(parser_soundLevel)
    _add_sub_arguments(parser_ambientNoise)
    _add_sub_arguments(parser_temperature)
    _add_sub_arguments(parser_humidity)
    _add_sub_arguments(parser_tvoc)
    _add_sub_arguments(parser_peopleCount)
    _add_sub_arguments(parser_timeUsed)
    _add_sub_arguments(parser_timeBooked)

    parser_temperature.add_argument('-u', '--unit', dest='unit' ,choices=['celsius', 'fahrenheit'], default='celsius',
                        help='Temperature units - default = celsius')
    

    _add_buckets(parser_soundLevel)
    _add_buckets(parser_ambientNoise)
    _add_buckets(parser_temperature)
    _add_buckets(parser_humidity)
    _add_buckets(parser_tvoc)
    _add_buckets(parser_peopleCount)

    parser_timeUsed.add_argument('-v', '--value', dest='value', action='store_const', const='duration', default='duration',
                        help='To Time ISO 2024-04-09T17:21:00Z')
    parser_timeBooked.add_argument('-v', '--value', dest='value', action='store_const', const='duration', default='duration',
                        help='To Time ISO 2024-04-09T17:21:00Z')



    # parser.add_argument('type', choices=['metrics', 'durationmetrics'])

    return parser.parse_args()


    subparsers = parser.add_subparsers(dest='command', required=True)

    parser_survey = subparsers.add_parser('survey', help='Identify mislabeled Speed Dials and genearte a report')

    parser_survey.add_argument('-d', '--debug', dest='debug', action='store_true', default=False,
                        help='Show debug logs')

    parser_survey.add_argument('--debug-soap', dest='soapDebug', action='store_true', default=False,    
                        help='Show SOAP Debug Logs')

    parser_survey.add_argument('--min-digits', dest='minDigits', action='store_const', const=4, default=4,
                        help='Minimum number of Speed Dial Digits which will be updated (default: 4)')

    parser_survey.add_argument('--max-digits', dest='maxDigits', action='store_const', const=4, default=4,
                        help='Maximum number of Speed Dial Digits which will be updated (default: 4)')

    parser_survey.add_argument('--replacement-token', dest='replacementToken', action='store_const', const='N/A', default='N/A',
                        help='Text to replace unfound Speed Dial Extensions (default: \'N/A\')')

    parser_update = subparsers.add_parser('update', help='Identify mislabeled Speed Dials and update them')

    parser_update.add_argument('-f','--force', dest='forceUpdate', action='store_true',
                        help='Perform Speed Dial updates without confirmation prompt')
    
    parser_update.add_argument('-d', '--debug', dest='debug', action='store_true', default=False,
                        help='Show debug logs')
    
    parser_update.add_argument('--debug-soap', dest='soapDebug', action='store_true', default=False,
                        help='Show SOAP Debug Logs')

    parser_update.add_argument('--min-digits', dest='minDigits',  default=4, type=int,
                        help='Minimum number of Speed Dial Digits which will be updated (default: 4)')
    parser_update.add_argument('--max-digits', dest='maxDigits',  default=4, type=int,
                        help='Maximum number of Speed Dial Digits which will be updated (default: 4)')

    parser_update.add_argument('--replacement-token', dest='replacementToken', action='store_const', const='N/A', default='N/A',
                        help='Text to replace unfound Speed Dial Extensions (default: \'N/A\')')

    parser_restore = subparsers.add_parser('restore', help='Restore Speed Dials from Backup')

    parser_restore.add_argument(dest='filename',  type=argparse.FileType('r'), help='Speed Dials Backup Filename')

    #parser_restoreFile = filesubparsers.add_argument('filename', type=argparse.FileType('r'), help='Speed Dials Backup Filename')

    #parser_restoreFile.add_argument('filename', dest='forceUpdate', action='store_true',
    #                    help='Perform Speed Dial restore without confirmation prompt')

    parser_restore.add_argument('-f', '--force', dest='forceUpdate', action='store_true',
                        help='Perform Speed Dial restore without confirmation prompt')
    
    parser_restore.add_argument('-d', '--debug', dest='debug', action='store_true', default=False,
                        help='Show debug logs')
    
    parser_restore.add_argument('--debug-soap', dest='soapDebug', action='store_true', default=False,
                        help='Show SOAP Debug Logs')

 

    return parser.parse_args()

CONSOLE_ARGS =  _parse_arguments()

# optional: delete function after use to prevent calling from other place
del _parse_arguments

