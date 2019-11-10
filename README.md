# icinga-plugins

## Table of Contents
* [Description](#description)
* [check_aws_cloudwatch](#check_aws_cloudwatch)
* [License](#license)

## Description
These plugins are for monitoring various services in icinga or nagios.  Plugins have gone thru basic testing sufficient for my environment (CentOS 7) and usage.

## check_aws_cloudwatch
### Syntax
```
usage: check_aws_cloudwatch.py [-h] -n NAMESPACE -d DIMENSIONS -M METRIC
                               [-s STATISTIC] [-P PERIOD] -w WARNING -c
                               CRITICAL -C COMPARATOR -r AWS_REGION
                               [-p AWS_PROFILE] [-v] [-vv]

Check an AWS CloudWatch Metric.

optional arguments:
  -h, --help            show this help message and exit
  -n NAMESPACE, --namespace NAMESPACE
                        Namespace of the Cloudwatch metric (REQUIRED) Example:
                        AWS/RDS
  -d DIMENSIONS, --dimensions DIMENSIONS
                        Cloudwatch dimensions
  -M METRIC, --metric METRIC
                        Cloudwatch metric
  -s STATISTIC, --statistic STATISTIC
                        Cloudwatch statistic (default: Average) (choices:
                        SampleCount, Average, Sum, Minimum, Maximum)
  -P PERIOD, --period PERIOD
                        Period (SECONDS) for statistics range (default: 300)
  -w WARNING, --warning WARNING
                        Value (FLOAT) for WARNING status/exit
  -c CRITICAL, --critical CRITICAL
                        Value (FLOAT) for WARNING status/exit
  -C COMPARATOR, --comparator COMPARATOR
                        Comparator for the WARNING/CRITICAL against returned
                        value for metric (choices: gt, ge, lt, le, eq, ne)
  -r AWS_REGION, --aws_region AWS_REGION
                        AWS region
  -p AWS_PROFILE, --aws_profile AWS_PROFILE
                        AWS profile
  -v, --verbose         Verbose output to stderr
  -vv, --verboseverbose
                        Debug output to stderr
```
### Example
This is to check the FreeStorageSpace of an RDS instance named myRdsInstance, with a warning when the metric is less than 20GB and critical when the metric is less than 10GB (Note: the unit for this metric is Byte)
```
./check_aws_cloudwatch.py --profile myProfileName --aws_region us-east-1 --namespace AWS/RDS --dimensions Name=DBInstanceIdentifier,Value=myRdsInstance --metric FreeStorageSpace --statistic Average --period 600 --warning 20000000000  --critical 10000000000 --comparator le
```

### Troubleshooting
There are two constants defined at the top of the plugin that can be used to facilitate debugging

`_STDERR_OUTPUT_LEVEL` Change to `logging.INFO` for verbose output to stderr (same as `-v/-verbose`) or to `logging.DEBUG` for debug output to stderr (same as `-vv/--verboseverbose`)

`_PRINT_STACKTRACE_ON_ERROR` Change to `True` to have the python stacktrace output to stderr when an error occurs

## License
All content is GPLv2
