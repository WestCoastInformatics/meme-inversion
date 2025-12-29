#!/bin/tcsh -f

# make_new_valid_files.csh - Fri Jan 9 13:35:44 PST 2004 - WAK
# 
# CHANGES
#  06/20/2007 SLQ (1-EJJW7): new script added.

set bin = "$MEME_HOME/bin"
set db=`$MIDSVCS_HOME/bin/midsvcs.pl -s editing-db`
set user=`$MIDSVCS_HOME/bin/get-oracle-pwd.pl -d $db`

set date = `date`
cat << EOR >! valid_relas
# used by QA*.pl
# Created by: $0
# Created on: $date
# From DB: $db
#
# blank and commented lines are ignored
#
EOR

echo "Getting RELAs..."
$bin/dump_table.pl -u $user -d $db -q "select relationship_attribute from inverse_rel_attributes" >> valid_relas

if($status)then
        echo "dump_table.pl failed, correct and re-run"
        exit
endif

$bin/dump_table.pl -u $user -d $db -q "select inverse_rel_attribute from inverse_rel_attributes" >> valid_relas

if($status)then
        echo "dump_table.pl failed, correct and re-run"
        exit
endif

cat << EOS >! valid_stys
# used by QA*.pl
# Created by: $0
# Created on: $date
# From DB: $db
#
# blank and commented lines are ignored
#
EOS

echo "Getting STYs..."
$bin/dump_table.pl -u $user -d $db -q "select semantic_type from semantic_types" | sort >> valid_stys
if($status)then
        echo "dump_table.pl failed, correct and re-run"
        exit
endif

echo "$0 finished sucessfully"
echo ""

