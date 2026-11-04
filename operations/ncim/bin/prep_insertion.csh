#!/bin/tcsh -f

############################################################
# Script: prep_insertion.csh
# Author: Joanne Wong (wongjf@mail.nih.gov)
# Notes:  9/5/17 (JFW): Ported to MEME5
#           v1.0 (JFW): Creates file structure and copies files for
#         real insertions.  Edit VARIABLES section if
#         paths change.
############################################################

#### CHECK USAGE ####

#default to real
set mode="real"
set sab="NOSAB"

if ($#argv < 1 || $#argv > 2) then
    echo "Usage: $0 [-t] <VSAB>"
    exit 1
else if ("$argv[1]" == "-t") then
    if ($#argv == 2) then
        set mode="test"
        set sab=$2
    else
        echo "Usage: $0 [-t] <VSAB>"
        exit 1
    endif
else if ($#argv == 1) then
    set mode="real"
    set sab=$1
else
    echo "Usage: $0 [-t] <VSAB>"
    exit 1
endif


#### VARIABLES ####

# parameters passed by script
set lc_sab=`perl -e "print lc($sab)"`

# location of src_root
set host = `hostname`
set src_root_dir = "/local/content/MEME/MEME5/inv/sources"

# subdirectory names
set src_dir="src"
set bin_dir="bin"
set insert_dir="insert"
set test_dir="test"

# user/group running the script
set exec_as_name="tomcata"

#### DETERMINE USAGE, SET TARGET ####

if ($mode == "test") then
  set target_dir = "$test_dir"
else
  set target_dir = "$insert_dir"
endif

#### MAIN ####

echo "---------------------------------------------------------------------------------"
echo "Starting ... `/bin/date`"
echo "---------------------------------------------------------------------------------"
echo "mode         = $mode"
echo "sab          = $sab"
echo "lc_sab       = $lc_sab"
echo "target_dir   = $target_dir"
echo "host         = $host"
echo "src_root_dir = $src_root_dir"
echo "exec_as_name = $exec_as_name"

if (-e "$src_root_dir/$sab") then

    if ( "$sab" !~ MTH* ) then

    echo "  Processing non-MTH source: $sab"
    # make directories for insertion
    echo "    make directories"
    cd $src_root_dir/$sab
    if (! -e $target_dir) then
        mkdir  $target_dir
    endif
    cd $target_dir

    # copy .src, .RRF files
    echo "    copy .src and .RRF files"
    cp $src_root_dir/$sab/$src_dir/*.src .
    cp $src_root_dir/$sab/$src_dir/*.RRF .

    # copy .csh recipe script and make it user,group executable/writeable
    # also fix group permissions so tomcata has access
    # echo "    copy script and make executable"
    # cp $src_root_dir/$sab/$bin_dir/$lc_sab.csh .
    # chmod 774 $lc_sab.csh

    echo "    fixing permissions so insertion can run as $exec_as_name"
    # fix permissions
    cd ..
    chgrp -R $exec_as_name $target_dir

    else
        echo "  Processing MTH source: $sab"
    # make directories for insertion
    cd $src_root_dir/$sab
    mkdir $target_dir
    cd $target_dir

    # the MTH insertion is now one part and includes bequeathal.relationships.src.
        cp $src_root_dir/$sab/src/*.src .
        cp $src_root_dir/$sab/src/MRDOC.RRF .

        cp $src_root_dir/$sab/src/umlscui.txt .


    # fix permissions
    cd ..
    chgrp -R $exec_as_name $target_dir

    endif
else
   echo "ERROR: required directory $src_root_dir/$sab does not exist."
   exit 1
endif

echo "---------------------------------------------------------------------------------"
echo "Done.  Please double-check directories created in $src_root_dir/$sab/$target_dir."
echo "---------------------------------------------------------------------------------"
