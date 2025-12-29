#!/bin/tcsh -f
# Script accespts two args
# 1st argument : <VSAB>
# Input src dir is /umls_s/src_root/<VSAB i.e 1st arg>/src
# Make sure that .src files exist in /umls_s/src_root/<VSAB>/src
# If user wants to point to different dir other than the above dir, can pass it as second argument
# Make sure that .src files exist in <2nd arg>/src if there is second arg
# Output: lucene index files  will be generated in dir i.e /umls_s/umls_apps_linux_prod/lucene-src-gen/output/<VSAB i.e 1st arg>
# Copy these files to /umls_s/webapp_root_linux_prod/meme/www/viewStyData/<VSAB>/ to view the hierarchy in Hierarchy Viewer
#########################################################################

set lucene_src_gen_home="/umls_s/umls_apps_linux_prod/lucene-src-gen"
if (! -e $lucene_src_gen_home) then
	echo "ERROR: directory $lucene_src_gen_home must exist"
	exit 1
endif

set src_root = "/umls_s/src_root"
if (! -e $src_root) then
	echo "ERROR: directory $src_root must exist"
	exit 1
endif

if ($?INV_HOME == 0) then
	echo "ERROR: INV_HOME not set"
	exit 1
endif
setenv CLASSPATH "$INV_HOME/lib/lucene-core-2.3.1.jar:$INV_HOME/lib/lucene-demos-2.3.1.jar:$INV_HOME/lib/lucene_index_gen.jar:."

# JAVA_HOME should be set externally
# setenv JAVA_HOME 
if ($?JAVA_HOME == 0) then
	echo "ERROR: JAVA_HOME not set"
	exit 1
endif


set usage="USAGE: $0 <VSAB>"

if ( "-h" == "$1" ) then
	echo "--------------------------------------------------------------------------------------------------------------------"
 	echo "Script accepts two args. 1st argument : <VSAB>. Script looks for .src files exist in /umls_s/src_root/<VSAB>/src." 
 	echo "If user wants to point to different dir other than the above dir, can pass it as second argument." 
 	echo "Make sure that .src files exist in <2nd arg>/src." 
 	echo "Output: lucene index files  will be generated in dir i.e /umls_s/umls_apps_linux_prod/lucene-src-gen/output/<VSAB i.e 1st arg>"
 	echo "Copy these files to /umls_s/webapp_root_linux_prod/meme/www/viewStyData/<VSAB>/ to view the hierarchy in Hierarchy Viewer"
	echo "--------------------------------------------------------------------------------------------------------------------"
 	exit;
endif

if ( $#argv == 1) then
    set output_dir="$lucene_src_gen_home/output/$1"
    set src_dir="/umls_s/src_root/$1/src"

    if ( ! -e $src_dir ) then
       echo "ERROR: $src_dir is not a directory"
       exit 1
    endif

    #check files exist in output dir
    if ( -e $output_dir ) then
       set fileNum = `find $output_dir -type f | wc -l`
       if ( $fileNum > 0 ) then
        echo "ERROR: Files exist in output_dir. Verify and clean $output_dir"
        exit 1
       endif
    endif
else if ( $#argv == 2 ) then
    set output_dir="$lucene_src_gen_home/output/$1"
    set src_dir=$2

    if ( ! -e $src_dir ) then
       echo "ERROR: $src_dir is not a directory"
       exit 1
    endif

    #check files exist in output dir
    if ( -e $output_dir ) then
       set fileNum = `find $output_dir -type f | wc -l`
       if ( $fileNum > 0 ) then
        echo "ERROR: Files exist in output_dir. Verify and clean $output_dir"
        exit 1
       endif
    endif
else
    echo "ERROR:Wrong number of arguments"
    echo $usage
    exit 1
endif

#rm -rf $output_dir/*

echo "------------------------------------------------------------"
echo "Starting .. `/bin/date`"
echo "INPUT dir:          $src_dir"
echo "OUTPUT dir:         $output_dir"
echo "JAVA_HOME:          $JAVA_HOME"
echo "CLASSPATH:          $CLASSPATH"
echo "------------------------------------------------------------"

#$JAVA_HOME/bin/java gov.nih.nlm.index.TestBuildIndex index $src_dir
$JAVA_HOME/bin/java  -Xms200M -Xmx3000M gov.nih.nlm.index.TestBuildIndex $output_dir  $src_dir

if ($status != 0) then
    echo "Error generating lucene indexes"
endif


echo "-----------------------------------------------------------------------------------------"
echo "NOTE: COPY $output_dir to /umls_s/webapp_root_linux_prod/meme/www/viewStyData/ to view the source hierarchy"
echo "------------------------------------------------------------------------------------------"
