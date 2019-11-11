#!/usr/bin/env python
""" Plugin for Icinga / Nagios to monitor AWS GuardDuty

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


# noinspection DuplicatedCode
def _get_args():
  def _update_logging_level():
    if _args.verbose:
      _logger.setLevel(logging.INFO)
      _logger.info('Logger level set to INFO')
    elif _args.debug:
      _logger.setLevel(logging.DEBUG)
    _logger.info('Logger level set to DEBUG')
    return

  try:
    _logger.info('Parse arguments')
    _parser = argparse.ArgumentParser(description='Check an AWS GuardDuty.')
    _parser.add_argument('-P', '--period', metavar='PERIOD', help='Period (HOURS) to go back for updated findings (default: %(default)s)', dest='period', type=int, default=48)
    _parser.add_argument('-fte', '--finding_type_exclude', metavar='FINDING-TYPE-EXCLUDE', help='Comma separated list of finding types to exclude', dest='finding_type_exclude', type=str)
    _parser.add_argument('-w', '--warning', metavar='WARNING', action='store', help='Value (FLOAT) for WARNING if any findings with severity greater than', dest='warning', type=float, default=4)
    _parser.add_argument('-c', '--critical', metavar='CRITICAL', action='store', help='Value (FLOAT) for CRITICAL if any findings with severity greater than', dest='critical', type=float, default=7)
    _parser.add_argument('-r', '--aws_region', metavar='AWS_REGION', required=True, action='store', help='AWS region (Example: us-east-1)', dest='aws_region', type=str)
    _parser.add_argument('-p', '--aws_profile', metavar='AWS_PROFILE', action='store', help='AWS profile', dest='aws_profile', type=str)
    _parser.add_argument('-v', '--verbose', required=False, action='store_true', help='Verbose output to stderr', dest='verbose')
    _parser.add_argument('-vv', '--debug', required=False, action='store_true', help='Debug output to stderr', dest='debug')
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
    _client = _session.client(service_name='backup')
    _logger.info('AWS client created')
    return _client
  except Exception as err:
    _print_stacktrace(err)
    _print_result([_EXIT_UNKNOWN, 'Unknown error getting AWS client'])


def _get_check_result(_args, _aws_client):
  def _get_detector_ids():
    _logger.info('Get detector IDs')
    _request_args = {
      'MaxResults': 1000
    }
    _response = _aws_client.list_detectors(**_request_args)
    _logger.debug('Response Detectors: {0}'.format(_response['DetectorIds']))
    return _response['DetectorIds']

  def _get_findings():
    _detector_findings = []
    for _detector in _detector_ids:
      _logger.info('Get Findings for Detector {id}'.format(id=_detector))
      _request_args = {
        'DetectorId': _detector,
        'MaxResults': 1000,
        'FindingCriteria': {
          'Criteria': {
            'updatedAt': {
              'GreaterThanOrEqual': [
                datetime.utcnow() - timedelta(hours=_args.period)
              ]
            },
            'severity': {
              'GreaterThanOrEqual': [_args.warning]
            }
          }
        }
      }
      if _args.finding_type_exclude is not None:
        _request_args['FindingCriteria']['Criteria']['type'] = {
          'NotEquals': []
        }
        for _finding_type in _args.finding_type_exclude.split(','):
          _request_args['FindingCriteria']['Criteria']['type']['NotEquals'].append(_finding_type)

      while True:
        _response = _aws_client.list_findings(**_request_args)
        _logger.debug('Response GuardDuty Findings: {0}'.format(_response['FindingIds']))
        _detector_findings.extend(_response['Findings'])
        if 'NextToken' in _response:
          _request_args['NextToken'] = _response['NextToken']
        else:
          break
    return _detector_findings

  try:
    _detector_ids = _get_detector_ids()
    _findings = _get_findings()
    return _findings
  except Exception as err:
    _print_stacktrace(err)
    _print_result([_EXIT_UNKNOWN, 'Unknown error getting findings'])


def _print_result(_result):
  sys.stdout.write('AWS-BACKUP {status} - {info_text}'.format(status=_result[0][1], info_text=_result[1]))
  sys.exit(_result[0][0])


def _print_stacktrace(_stacktrace):
  if _PRINT_STACKTRACE_ON_ERROR:
    traceback.print_exc(file=sys.stderr)


def _analyze_result(_args, _check_result):
  _result_counts = {
    'Critical': {
      'Severity': _args.critical,
      'Count': 0
    },
    'Warning': {
      'Severity': _args.warning,
      'Count': 0
    }
  }
  for _result in _check_result:
    if _result['Service']['Archived']:
      continue
    if _result['Severity'] > _args.critical:
      _result_counts['Critical']['Count'] += 1
    elif _result['Severity'] > _args.warning:
      _result_counts['Warning']['Count'] = 1

  _result_txt = '{count} in last {period} hours'.format(count=_result_counts, period=_args.period)
  if _result_counts['Critical']['Count'] > 0:
    return [_EXIT_CRITICAL, _result_txt]
  elif _result_counts['Warning']['Count'] > 0:
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
