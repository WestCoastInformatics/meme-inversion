#!/bin/tcsh -f
#
# This script is used to pull/download inversion source folders or release packages from s3
# Usage examples:
# ./pull_s3.csh inv NCI_2022_09D
# ./pull_s3.csh ncim 202208
# ./pull_s3.csh umls 2022AB
# ./pull_s3.csh inv NCI_2026_10D --keep-archive
# ./pull_s3.csh inv NCI_2026_10D --download-only
#

set rootdir = `dirname $0`
set abs_rootdir = `cd $rootdir && pwd`

setenv usage 'pull_s3.csh {inv|ncim|umls} {source_name|release_date} [--keep-archive|--download-only]'
setenv S3_BUCKET s3://nci-evs-meme
# AWS_PROFILE is supplied by the calling environment when a named profile is needed.
set awsbin = '/usr/bin/aws'
if ($?AWS_BIN) then
    set awsbin = "$AWS_BIN"
endif
set keep_archive = 0
set download_only = 0

echo "--------------------------------------------------------"
echo "Starting `/bin/date`"
echo "--------------------------------------------------------"

if ($#argv == 2 || $#argv == 3) then
    setenv INV_OR_MR $1
    setenv TARGET_NAME $2
    if ($#argv == 3) then
        if ("$3" == "--keep-archive") then
            set keep_archive = 1
        else if ("$3" == "--download-only") then
            set keep_archive = 1
            set download_only = 1
        else
            echo "ERROR: Unknown option $3"
            exit 1
        endif
    endif
else
    echo "ERROR: Wrong number of parameters"
    echo "usage: $usage"
    exit 1
endif

echo "INV_OR_MR:    $INV_OR_MR"
echo "TARGET_NAME: 	$TARGET_NAME"

if ($INV_OR_MR != 'inv' && $INV_OR_MR != 'ncim' && $INV_OR_MR != 'umls') then
    echo "ERROR: inv or ncim or umls must be specified as first parameter"
	echo "ERROR: $usage"
    exit 1
endif
if ($INV_OR_MR != 'inv' && $keep_archive == 1) then
    echo "ERROR: Archive-retention options apply only to inversion archives."
    exit 1
endif

if ($INV_OR_MR == 'inv') then 
	setenv TARGET_PATH /local/content/MEME/MEME5/inv/sources
else
	setenv TARGET_PATH /local/content/MEME/MEME5/mr
endif


if (! -e $TARGET_PATH) then
    echo "ERROR: $TARGET_PATH must exist."
	exit 1
endif

cd $TARGET_PATH
if ( $INV_OR_MR == 'inv' && $download_only == 0 && -e $TARGET_PATH/$TARGET_NAME) then
    echo "ERROR: $TARGET_PATH/$TARGET_NAME already exists.  To refresh, please delete the folder and run the pull again."
	exit 1
endif
if ( $INV_OR_MR == 'ncim' && -e $TARGET_PATH/ncim/$TARGET_NAME) then
    echo "ERROR: $TARGET_PATH/ncim/$TARGET_NAME already exists.  To refresh, please delete the folder and run the pull again."
	exit 1
endif
if ( $INV_OR_MR == 'umls' && -e $TARGET_PATH/umls/$TARGET_NAME) then
    echo "ERROR: $TARGET_PATH/umls/$TARGET_NAME already exists.  To refresh, please delete the folder and run the pull again."
	exit 1
endif

echo "    Download data from s3 and decompress it... `/bin/date`"
if ($INV_OR_MR == 'inv') then
    $awsbin s3api head-object --bucket nci-evs-meme --key inv/sources/$TARGET_NAME.tgz > /dev/null
    if ($status == 0) then
        set archive_name = "$TARGET_NAME.tgz"
    else
        $awsbin s3api head-object --bucket nci-evs-meme --key inv/sources/$TARGET_NAME.tar.gz > /dev/null
		if ($status == 0) then
            set archive_name = "$TARGET_NAME.tar.gz"
		else
			echo "    Neither $TARGET_NAME.tar.gz nor $TARGET_NAME.tgz could be accessed. Exiting..."
		    exit 1
		endif
    endif
    if (-e "$archive_name") then
        echo "ERROR: $archive_name already exists; verify or explicitly retire it before downloading."
        exit 1
    endif
    echo "    Downloading $archive_name"
    $awsbin s3 cp "$S3_BUCKET/inv/sources/$archive_name" . --no-progress
    if ($status != 0) then
        echo "ERROR: Archive download failed; no extraction was attempted."
        exit 1
    endif
    if (! -f "$archive_name" || -z "$archive_name") then
        echo "ERROR: Archive download did not produce a nonempty file."
        exit 1
    endif
    if ($download_only == 1) then
        echo "    Preserved $archive_name for inspection; no extraction was performed."
        exit 0
    endif
    echo "    Extracting $archive_name"
    tar -xvf "$archive_name"
    if ($status != 0) then
        echo "ERROR: Extraction failed; $archive_name has been retained."
        exit 1
    endif
    if ($keep_archive == 0) then
        rm -f "$archive_name"
    else
        echo "    Preserved $archive_name"
    endif

else if ($INV_OR_MR == 'ncim') then
    set fileExists = `$awsbin s3api head-object --bucket nci-evs-meme --key mr/ncim/$TARGET_NAME/$TARGET_NAME.zip | grep Metadata | wc -l `
	if ($fileExists == 1) then
	    echo "    Downloading $TARGET_NAME"
    	mkdir $TARGET_PATH/ncim/$TARGET_NAME
	    cd $TARGET_PATH/ncim/$TARGET_NAME
        $awsbin s3 cp $S3_BUCKET/mr/ncim/$TARGET_NAME . --recursive
 	else
		echo "    $TARGET_NAME was not found.  Exiting..."
	    exit 1
    endif	
else if ($INV_OR_MR == 'umls') then
    set fileExists = `$awsbin s3api head-object --bucket nci-evs-meme --key mr/umls/$TARGET_NAME/META/MRSAB.RRF | grep Metadata | wc -l `
	if ($fileExists == 1) then
	    echo "    Downloading $TARGET_NAME"
    	mkdir $TARGET_PATH/umls/$TARGET_NAME
		cd $TARGET_PATH/umls/$TARGET_NAME
        $awsbin s3 cp $S3_BUCKET/mr/umls/$TARGET_NAME . --recursive
    	
        rm -rf $TARGET_PATH/umls/$TARGET_NAME/DVDIMAGE/jre
    	
 	else
		echo "    $TARGET_NAME was not found.  Exiting..."
	    exit 1
    endif	
endif


echo ""


echo "-----------------------------------------------------"
echo "Finished $0 ... `/bin/date`"
echo "Check $TARGET_PATH/$TARGET_NAME for results"
echo "-----------------------------------------------------"
