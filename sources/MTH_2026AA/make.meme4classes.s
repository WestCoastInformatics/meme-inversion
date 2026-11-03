#!/bin/tcsh -f

# incantation to fix broken "sort" command:
setenv _POSIX2_VERSION 1

bin/get.saidpts.pl >said.ptsaid
sed 's/.*|//' said.ptsaid |sort -u -o ptsaid.order
cp -p classes_atoms.src classes_atoms.src.raw
#sed 's/|[^|]*|[^|]*|[^|]*$//' classes_atoms.src >classes_atoms3.src
#make.meme4classes.pl >classes_atoms.src
#gzip classes_atoms3.src classes_atoms.src.raw

# edited the following to remove the V-CCS_2005 SRC lines that an mmsys bug
# leaves in MRCONSO, probably because they share a SF (source family) with
# CCS_10, which is included
sed 's/|[^|]*\(|[^|]*\)|[^|]*$/\1/' classes_atoms.src.raw |grep -v SRC/V...V-CCS_2005 >! classes_atoms.src
