#!/bin/tcsh -f
#
# run preinvert{1,2}.s before running invert{1,2}.s
#
# Before running this:
# - >>> update sab.vsab.map to set the proper version (VSAB) for the MTH RSAB.
# - update the "set release" line in runmmsys.s (it's used by updatevsabs.s),
# - create the old/ and Meta/ links and make sure Meta/MRSAB.RRF exists,
# - pre-run "./updatevsabs.s" to make updatevsabs.log listing needed updates,
# - update sab.vsab.map (as necessary according to updatevsabs.log: update the
#   UMLS VSABs to be correct and update the corresponding NCI-formated VSABs
#   accordingly) for the current release's sources
#
# After running preinvert1.s, edit ncisources.spec as needed, and
# then run preinvert2.s

# incantation to fix broken "sort" command:
setenv _POSIX2_VERSION 1

chmod a+w .
#chgrp memegrp .

./updatevsabs.s
./guess.ncisources.spec.pl >ncisources.spec
cp -p ncisources.spec{,.guessed}
