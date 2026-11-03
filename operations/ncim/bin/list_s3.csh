#!/bin/tcsh -f
#
# This script is used to list the contents of s3
#

set rootdir = `dirname $0`
set abs_rootdir = `cd $rootdir && pwd`
set usage = 'list_s3.csh'
set awspath = '/usr/bin'

echo "--------------------------------------------------------"
echo "Starting `/bin/date`"
echo "--------------------------------------------------------"


#$awspath/aws rds describe-db-instances --profile meme --query "DBInstances[*].{DBInstance:DBInstanceArn}" | jq -r '.[].DBInstance' > /tmp/rdsArns.txt

  echo ""
  echo indexes
  echo "--------------------------------------------------------"
  $awspath/aws s3 ls "s3://nci-evs-meme/indexes/"

  echo ""
  echo mr/ncim
  echo "--------------------------------------------------------"
  $awspath/aws s3 ls "s3://nci-evs-meme/mr/ncim/"

  echo ""
  echo mr/umls
  echo "--------------------------------------------------------"
  $awspath/aws s3 ls "s3://nci-evs-meme/mr/umls/"

  echo ""
  echo inv/sources 
  echo "--------------------------------------------------------"
  $awspath/aws s3 ls "s3://nci-evs-meme/inv/sources/"

  echo ""
  echo snapshots
  echo "--------------------------------------------------------"
  $awspath/aws s3 ls "s3://nci-evs-meme/snapshots/"

  echo ""
  echo tmp
  echo "--------------------------------------------------------"
  $awspath/aws s3 ls "s3://nci-evs-meme/tmp/"



echo ""

echo "-----------------------------------------------------"
echo "Finished $0 ... `/bin/date`"
echo "-----------------------------------------------------"
