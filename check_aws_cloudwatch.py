#!/usr/bin/env python
""" Plugin for Icinga / Nagios to monitor AWS Cloudwatch Metrics

https://github.com/UranusBytes/icinga-plugins

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Foobar.  If not, see <http://www.gnu.org/licenses/>.
"""

__author__ = "Jeremy Phillips"
__contact__ = "jeremy@uranusbytes.com"
__license__ = "GPLv2"
__version__ = "0.1.0"

import argparse
import boto3
from datetime import datetime, timedelta
import sys
import logging
import traceback
import operator

# Constants
###############################################################################
_STDERR_OUTPUT_LEVEL = logging.CRITICAL  # Leave at logging.CRITICAL unless doing debugging
_PRINT_STACKTRACE_ON_ERROR = False  # Show stacktrace to stderr on error
_EXIT_OK = [0, 'OK']
_EXIT_WARNING = [1, 'WARNING']
_EXIT_CRITICAL = [2, 'CRITICAL']
_EXIT_UNKNOWN = [3, 'UNKNOWN']


# Functions
###############################################################################
def _get_logger():
  _root_logger = logging.getLogger()
  _root_logger.setLevel(logging.DEBUG)
  _formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  _stderr_logger = logging.StreamHandler()
  _stderr_logger.setFormatter(_formatter)
  _stderr_logger.setLevel(_STDERR_OUTPUT_LEVEL)
  _root_logger.addHandler(_stderr_logger)
  _root_logger.info('Logger to StdErr Setup; root logger disabled')
  # Disable noisy libraries
  logging.getLogger("urllib3").setLevel(logging.WARNING)
  logging.getLogger("botocore").setLevel(logging.WARNING)
  return _root_logger


def _get_args():
  def _update_logging_level():
    if _args.verbose:
      _logger.setLevel(logging.INFO)
      _logger.info('Logger level set to INFO')
    elif _args.verboseverbose:
      _logger.setLevel(logging.DEBUG)
    _logger.info('Logger level set to DEBUG')
    return

  try:
    _logger.info('Parse arguments')
    _parser = argparse.ArgumentParser(description='Check an AWS CloudWatch Metric.')
    _parser.add_argument('-n', '--namespace', metavar='NAMESPACE', required=True, action='store', help='Namespace of the Cloudwatch metric (Example: AWS/RDS)', dest='namespace', type=str)
    _parser.add_argument('-d', '--dimensions', metavar='DIMENSIONS', required=True, action='store', help='Cloudwatch dimensions as NAME=VALUE (Example: DBInstanceIdentifier=myDbName)', dest='dimensions', type=str)
    _parser.add_argument('-M', '--metric', metavar='METRIC', required=True, action='store', help='Cloudwatch metric (Example: FreeStorageSpace)', dest='metric', type=str)
    _parser.add_argument('-s', '--statistic', metavar='STATISTIC', action='store', help='Cloudwatch statistic (default: %(default)s) (choices: %(choices)s)', dest='statistic', type=str,
                         choices=['SampleCount', 'Average', 'Sum', 'Minimum', 'Maximum'], default='Average')
    _parser.add_argument('-P', '--period', metavar='PERIOD', help='Period (SECONDS) for statistics range (default: %(default)s)', dest='period', type=int, default=300)
    _parser.add_argument('-w', '--warning', metavar='WARNING', required=True, action='store', help='Value (FLOAT) for WARNING status/exit', dest='warning', type=float)
    _parser.add_argument('-c', '--critical', metavar='CRITICAL', required=True, action='store', help='Value (FLOAT) for WARNING status/exit', dest='critical', type=float)
    _parser.add_argument('-C', '--comparator', metavar='COMPARATOR', required=True, action='store', help='Comparator for the WARNING/CRITICAL against returned value for metric (choices: %(choices)s)', dest='comparator', type=str,
                         choices=['gt', 'ge', 'lt', 'le', 'eq', 'ne'])
    _parser.add_argument('-r', '--aws_region', metavar='AWS_REGION', required=True, action='store', help='AWS region (Example: us-east-1)', dest='aws_region', type=str)
    _parser.add_argument('-p', '--aws_profile', metavar='AWS_PROFILE', action='store', help='AWS profile', dest='aws_profile', type=str)
    _parser.add_argument('-v', '--verbose', required=False, action='store_true', help='Verbose output to stderr', dest='verbose')
    _parser.add_argument('-vv', '--verboseverbose', required=False, action='store_true', help='Debug output to stderr', dest='verboseverbose')
    _args = _parser.parse_args()
    _update_logging_level()
    _logger.debug('Args: {0}'.format(vars(_args)))
    return _args
  except Exception as err:
    _print_stacktrace(err)
    _print_result([_EXIT_UNKNOWN, 'Unknown error parsing arguments'])


def _get_aws_client(_args):
  try:
    _logger.info('Get AWS client')
    _session_args = {
      'region_name': _args.aws_region
    }
    if hasattr(_args, 'aws_profile'):
      _session_args['profile_name'] = _args.aws_profile

    _logger.debug('Session args: {0}'.format(_session_args))
    _session = boto3.Session(**_session_args)
    _client = _session.client(service_name='cloudwatch')
    _logger.info('AWS client created')
    return _client
  except Exception as err:
    _print_stacktrace(err)
    _print_result([_EXIT_UNKNOWN, 'Unknown error getting AWS client'])


def _get_check_result(_args, _aws_client):
  def _build_dimensions():
    _dimensions = []
    for _dimension_set in _args.dimensions.split(','):
      _parts = _dimension_set.split('=')
      _dimensions.append({
        'Name': _parts[0],
        'Value': _parts[1]
      })
      _logger.debug('Dimensions: {0}'.format(_dimensions))
    return _dimensions

  try:
    _logger.info('Get check result')
    _response = _aws_client.get_metric_statistics(
      Namespace=_args.namespace,
      MetricName=_args.metric,
      Dimensions=_build_dimensions(),
      StartTime=datetime.utcnow() - timedelta(seconds=_args.period),
      EndTime=datetime.utcnow(),
      Period=_args.period,
      Statistics=[_args.statistic]
    )
    _logger.debug('Response Datapoints: {0}'.format(_response['Datapoints']))
    return _response['Datapoints']
  except Exception as err:
    _print_stacktrace(err)
    _print_result([_EXIT_UNKNOWN, 'Unknown error getting cloudwatch metric'])


def _print_result(_result):
  sys.stdout.write('CLOUDWATCH {status} - {info_text}'.format(status=_result[0][1], info_text=_result[1]))
  sys.exit(_result[0][0])


def _print_stacktrace(_stacktrace):
  if _PRINT_STACKTRACE_ON_ERROR:
    traceback.print_exc(file=sys.stderr)


def _analyze_result(_args, _check_result):
  _logger.info('Analyze results')
  _result_txt = '{metric}: {metric_value} {metric_unit} '.format(metric=_args.metric, metric_value=_check_result[0][_args.statistic], metric_unit=_check_result[0]['Unit'])
  _comparator = getattr(operator, _args.comparator)
  if _comparator(_check_result[0][_args.statistic], _args.critical):
    return [_EXIT_CRITICAL, _result_txt]
  elif _comparator(_check_result[0][_args.statistic], _args.warning):
    return [_EXIT_WARNING, _result_txt]
  else:
    return [_EXIT_OK, _result_txt]


# Main
###############################################################################
def _main():
  _logger.info('Begin main')
  _args = _get_args()
  _aws_client = _get_aws_client(_args)
  _check_result = _get_check_result(_args, _aws_client)
  _analyzed_result = _analyze_result(_args, _check_result)
  _print_result(_analyzed_result)
  _logger.info('Finish main')
  return


if __name__ == '__main__':
  try:
    _logger = _get_logger()
    _main()
  except Exception as err:
    _print_stacktrace(err)
    _print_result([_EXIT_UNKNOWN, 'Unknown error in main'])
