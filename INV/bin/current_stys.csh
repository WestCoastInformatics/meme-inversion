#!/bin/tcsh -f
#
# 12/01/2006 TTN (1-CDMK9): Initial version
#
# This script generates the list of current semantic types for specified source.
#
# File:    current_stys.csh
# Author:  Tun Tun Naing
#
# Usage:
#     current_stys.csh [-d <db>] <SAB>
#
# Options:
#     -d <db>	: database
#     <SAB>     : versioned source abbreviation
#     -v version: Version information
#     -h help:    On-line help
#
# Version Info
set release="2"
set version="1.1"
set version_authority="TTN"
set version_date="11/16/2006"

#
# Set environment (if configured)
#
if ($?ENV_FILE == 1 && $?ENV_HOME == 1) then
    source $ENV_HOME/bin/env.csh
endif

#
# Check required environment variables
#
if ($?MEME_HOME == 0) then
    echo "\$MEME_HOME must be set"
    exit 1
endif

#
# Set variables
#

#
# Parse arguments
#
if ($#argv == 0) then
    echo "Error: Bad argument"
    echo "Usage: $0 [-d <db>] <SAB>"
    exit 1
endif

set i=1

while ($i <= $#argv)
    switch ($argv[$i])
        case '-*help':
            echo "Usage: $0 [-d <db>] <SAB>"
            echo "Version $version, $version_date ($version_authority)"
            exit 0
        case '-v':
            echo $version
            exit 0
        case '-version':
            echo "Version $version, $version_date ($version_authority)"
            exit 0
        default:
            breaksw
    endsw
    set i=`expr $i + 1`
end

set db=`$MIDSVCS_HOME/bin/midsvcs.pl -s editing-db`;

#
# Check arguments
#
if ($#argv == 1) then
    set sab=$1
else if ($#argv == 3 && "$argv[1]" =~ -[d]  ) then
    set db=$2
    set sab=$3
else
    echo "Error: Bad argument"
    echo "Usage: $0 [-d <db>] <SAB>"
    exit 1
endif

#
# Begin program logic
#
#echo "----------------------------------------------"
#echo "Starting $0 ... `/bin/date`"
#echo "----------------------------------------------"
#echo "SAB: $sab"

# TODO: get src_atom_id, sty, ischem from attributes for this source
$MEME_HOME/bin/dump_table.pl -d $db -u $user -q \
	"select distinct b.source_row_id as src_atom_id, c.attribute_value as sty, d.is_chem \
	from classes a, source_id_map b, attributes c, semantic_types d \
	where a.atom_id = b.local_row_id \
   	and a.source = '$sab' \
   	and a.concept_id = c.concept_id \
   	and c.attribute_name='SEMANTIC_TYPE' \
   	and c.attribute_value = d.semantic_type"
   
  
#echo ""
#echo "----------------------------------------------"
#echo "Finished $0 ... `/bin/date`"
#echo "----------------------------------------------"




