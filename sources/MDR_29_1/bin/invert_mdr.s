#!/bin/tcsh -f

echo "starting inversion"
date

echo "creating *.src files"
invert_mdr.pl

echo "appending ATN = PT_IN_VERSION to attributes.src"
append_atn.pl

echo "creating MRDOC.RRF"
$INV_HOME/bin/makeDoc.pl

echo "running QA"
cd ../src
#$INV_HOME/bin/srcQa.pl -c ../etc/*cfg -i ../src -o ../etc/qa -w31
$INV_HOME/bin/srcQa.pl -c ../etc/*cfg 

echo "running statistics"
#$INV_HOME/bin/findQaStats.pl -i ../src
$INV_HOME/bin/findQaStats.pl

echo "inversion finished"
date
