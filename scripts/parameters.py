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
                        help='Value you want to store')
    


def _parse_arguments():
    parser = argparse.ArgumentParser(prog='workspace.py', 
                                 description='This Scripts lets you bulk export Workspace Metrics for your Webex Org')

    subparsers = parser.add_subparsers(dest='metricName', help="asdf", description='The metric name you want to export',required=True)
    
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
                        help='Value you want to store - default = duration')
    parser_timeBooked.add_argument('-v', '--value', dest='value', action='store_const', const='duration', default='duration',
                        help='Value you want to store - default = duration')


    return parser.parse_args()



CONSOLE_ARGS =  _parse_arguments()

# optional: delete function after use to prevent calling from other place
del _parse_arguments

