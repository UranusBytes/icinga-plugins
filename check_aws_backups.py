#!/usr/bin/env python
""" Plugin for Icinga / Nagios to monitor AWS Backups

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
    _parser = argparse.ArgumentParser(description='Check an AWS Backup Jobs.')
    _parser.add_argument('-ra', '--resource_arn', metavar='RESOURCE-ARN', action='store', help='Limit backup jobs to a resource Arn', dest='resource_arn', type=str)
    _parser.add_argument('-rt', '--resource_type', metavar='RESOURCE-TYPE', action='store', help='Limit backup jobs to a resource type (choices: %(choices)s)', dest='resource_type', type=str, choices=['EBS', 'SGW', 'RDS', 'DDB', 'EFS'])
    _parser.add_argument('-bvn', '--backup_vault_name', metavar='BACKUP-VAULT', action='store', help='Limit backup jobs to a backup vault', dest='backup_vault_name', type=str)
    _parser.add_argument('-P', '--period', metavar='PERIOD', help='Period (HOURS) to go back for jobs (default: %(default)s)', dest='period', type=int, default=24)
    _parser.add_argument('-w', '--warning', metavar='WARNING', action='store', help='Value (INT) for WARNING if greater than FAILED count (default: %(default)s)', dest='warning', type=int, default=0)
    _parser.add_argument('-c', '--critical', metavar='CRITICAL', action='store', help='Value (INT) for WARNING if greater than FAILED count (default: %(default)s)', dest='critical', type=int, default=0)
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
  try:
    _logger.info('Get check result')
    _request_args = {
      'MaxResults': 1000
    }
    if _args.resource_arn is not None:
      _request_args['ByResourceArn'] = _args.resource_arn
    if _args.backup_vault_name is not None:
      _request_args['ByBackupVaultName'] = _args.backup_vault_name
    if _args.resource_type is not None:
      _request_args['ByResourceType'] = _args.resource_type
    _request_args['ByCreatedAfter'] = datetime.utcnow() - timedelta(hours=_args.period)

    _backup_jobs = []
    while True:
      _response = _aws_client.list_backup_jobs(**_request_args)
      _logger.debug('Response BackupJobs: {0}'.format(_response['BackupJobs']))
      _backup_jobs.extend(_response['BackupJobs'])
      if 'NextToken' in _response:
        _request_args['NextToken'] = _response['NextToken']
      else:
        break
    return _backup_jobs
  except Exception as err:
    _print_stacktrace(err)
    _print_result([_EXIT_UNKNOWN, 'Unknown error getting backup job list'])


def _print_result(_result):
  sys.stdout.write('AWS-BACKUP {status} - {info_text}'.format(status=_result[0][1], info_text=_result[1]))
  sys.exit(_result[0][0])


def _print_stacktrace(_stacktrace):
  if _PRINT_STACKTRACE_ON_ERROR:
    traceback.print_exc(file=sys.stderr)


def _analyze_result(_args, _check_result):
  _logger.info('Analyze results')
  _result_counts = {}
  for _result in _check_result:
    if _result['State'] in _result_counts:
      _result_counts[_result['State']] += 1
    else:
      _result_counts[_result['State']] = 1

  _result_txt = '{count} in last {period} hours'.format(count=_result_counts, period=_args.period)
  if 'FAILED' in _result_counts and _result_counts['FAILED'] > _args.critical:
    return [_EXIT_CRITICAL, _result_txt]
  elif 'FAILED' in _result_counts and _result_counts['FAILED'] > _args.warning:
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
