#!/bin/tcsh -f
#
# File:   raw_to_contexts.csh
# Author: Brian Carlsen
#
# Remarks:  This script takes a directory containing *raw3 or *raw2 files
#           and produces a contexts.src file from it.  The context.src
#           format was updated on 4/04/2001 and this script
#           produces that updated format.
#
# Changes
# 08/18/2006 BAC(1-BVS6F): Better support for -i and -o
# 08/10/2006 BAC(1-BVS6F): Support -i and -o
# 
# Old Version info
# 04/12/2005 3.1: Ignore CHD (99) lines in .raw3 file
# 11/19/2004 3.0: Released, Better error handling doesn't bother with .raw2
# 12/19/2003 2.0: Supports "native identifiers" for context relationships
# 08/25/2003 1.2: More efficient sorting when building contexts
# 07/21/2003 1.1: Supports context.src format with 
#                 source_rui and relationship_group
#                 Properly maintains release mode
# 03/18/2003 1.0: Ported to MEME4
#
set release=4
set version="3.1"
set authority="BAC";
set date="04/12/2005";

#
# Set environment (if configured)
#
if ($?ENV_FILE == 1 && $?ENV_HOME == 1) then
    source $ENV_HOME/bin/env.csh
endif

#
# Change on release to NLM
#
set perl=$PATH_TO_PERL
set HUGETMP=.
set sort="/bin/sort -T $HUGETMP"
set awk=/bin/awk

if ($#argv > 0) then
    if ("x-version" == "x$argv[1]") then
	echo "Release ${release}: version $version, $date ($authority)"
	exit 0
    else if ("x$argv[1]" == "x-v") then
	echo "$version"
	exit 0
    else if ("x$argv[1]" == "x--help" || "x$argv[1]" == "x-help") then
    cat <<EOF
 This script has the following usage:
   Usage: $0 -o <output dir> -i <input dir>
   Usage: $0 <input dir>

    This script takes a directory containing *raw[23] files
    and produces a contexts.src file from it. The contexts.src
    format was updated on 04/04/2001 to include hcd and
    parent tree number information.  This script produces
    a contexts.src file in that new format when run.

EOF
    exit 0
    endif
endif

set out_dir=.
if ($#argv == 1) then
  set in_dir = $1
else if ($#argv == 4) then
  if ("x$argv[1]" == "x-o" && "x$argv[3]" == "x-i") then
    set out_dir = $2
    set in_dir = $4
  else if ("x$argv[3]" == "x-o" && "x$argv[1]" == "x-i") then
    set out_dir = $4
    set in_dir = $2
  else
    echo "Usage: $0 -o <output dir> -i <input dir>"
    echo "Usage: $0 <input dir>"
    exit 1
  endif
else
    echo "Usage: $0 -o <output dir> -i <input dir>"
    echo "Usage: $0 <input dir>"
    exit 1
endif

if (! (-d $in_dir)) then
    echo "$in_dir must be a directory."
    exit 1
endif

echo "--------------------------------------------------------------"
echo "Starting `/bin/date`"
echo "--------------------------------------------------------------"
echo "in dir:          $in_dir"
echo "out dir:         $out_dir"
echo "raw3 files:      `ls $in_dir/*raw3`"

# 
# Sort file on source, then first 5 fields
echo "Generate (raw3) contexts.src format ...`/bin/date`"

# Write perl script
# Format of raw3 is from: /MEME/Data/src_format.html#contexts
cat >! /tmp/t.$$.pl <<EOF
#!$perl 
# map mrrel_flag|mrcxt_flag to a tbr value 
#%tbr_map = ( 
#	    "11" => "Y", 
#	    "10" => "y", 
#	    "01" => "?", 
#	    "00" => "n" ); 
\$prev_key=""; 
while (<>) { 
    chop; 
    @f=split /\|/; 
    (\$hsr,\$sg_id_1,\$sg_type_1,\$sg_qualifier_1,\$sg_id_2,\$sg_type_2,\$sg_qualifier_2) = split /~/, \$f[7];
    (\$hcd,\$srui,\$rg) = split /:/,\$hsr;

    # Start over if id,cxn changes 
    if (\$prev_key ne "\$f[0]\$f[1]") { 
	\$treenum = "\$f[5]"; 
	\$parent_id = \$f[5]; 
	\$parent_sg_id = \$sg_id_2;
	\$parent_sg_type = \$sg_type_2;
	\$parent_sg_qualifier = \$sg_qualifier_2;
	\$prev_key = "\$f[0]\$f[1]"; 
    }; 

    # Build PAR rows from 0 to 50
    # If 50 row has no ancestor \$treenum will equal \$f[5]
    # for cases with no ancestors 
    if ((\$f[2] > 0 && \$f[2] <= 50) && \$treenum ne \$f[5]) {
      (\$sg_id_2,\$sg_type_2,\$sg_qualifier_2) = (\$f[5],"SRC_ATOM_ID","") unless \$sg_id_2;
      (\$parent_sg_id,\$parent_sg_type,\$parent_sg_qualifier) = (\$parent_id,"SRC_ATOM_ID","") unless \$parent_sg_id;
	print "\$f[5]|PAR|\$f[8]|\$parent_id|\$f[11]|\$f[11]|\$hcd|\$treenum|\$parent_release_mode|\$srui|\$rg|\$sg_id_2|\$sg_type_2|\$sg_qualifier_2|\$parent_sg_id|\$parent_sg_type|\$parent_sg_qualifier\n"; 
    }

    # build up treenum 
    # if \$treenum eq \$f[5] we are at the top of the tree 
    if (\$f[2] < 50 && \$treenum ne \$f[5]) { 
	\$treenum .= ".\$f[5]"; 
	\$parent_id = \$f[5]; 
	\$parent_sg_id = \$sg_id_2;
	\$parent_sg_type = \$sg_type_2;
	\$parent_sg_qualifier = \$sg_qualifier_2;
    } 

    # if cxl is 50: ignore 
    # if cxl is 60, print SIB row 
    if (\$f[2] eq "60") { 
      (\$sg_id_1,\$sg_type_1,\$sg_qualifier_1) = (\$f[0],"SRC_ATOM_ID","") unless \$sg_id_1;
      (\$sg_id_2,\$sg_type_2,\$sg_qualifier_2) = (\$f[5],"SRC_ATOM_ID","") unless \$sg_id_2;
     # Only print SIBs in one direction where atom_id_1 <= atom_id_2
     print "\$f[0]|SIB|\$f[8]|\$f[5]|\$f[11]|\$f[11]|||\$f[12]\$f[13]|||\$sg_id_1|\$sg_type_1|\$sg_qualifier_1|\$sg_id_2|\$sg_type_2|\$sg_qualifier_2\n" if (\$f[0] <= \$f[5]);
    } 

    \$parent_release_mode = "\$f[12]\$f[13]";
}
EOF
chmod 755 /tmp/t.$$.pl

# sort by source of context and then first 5 fields
$awk -F\| '$3!=99 {print $0}' $in_dir/*.raw3 |\
 $sort -t\| -k 12,12 -k 1,5  |\
 $perl /tmp/t.$$.pl |\
 $sort -u >! $out_dir/contexts.src
#$sort -u >! $in_dir/contexts.src 
if ($status != 0) then
    echo "Error generating contexts.src"
    exit 1
endif

# Cleanup
\rm -f $in_dir/$$.work
\rm -f /tmp/t.$$.pl

echo "--------------------------------------------------------------"
echo "Finished `/bin/date`"
echo "--------------------------------------------------------------"

