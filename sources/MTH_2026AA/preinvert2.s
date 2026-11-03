#!/bin/tcsh -f
#
# run preinvert{1,2}.s before running invert.s
#
# After running preinvert1.s, edit ncisources.spec as needed, and
# then run preinvert2.s
#
# BEFORE RUNNING THIS, the UMLS release we're inverting must be in
# /local/content/MEME/MEME5/mr/umls/20##Ax/DVDIMAGE, and ALSO the full 
# MRREL.RRF and MRSAB.RRF
# files for that release must be in 
# /local/content/MEME/MEME5/umls/mr/20##AX/META (which must
# be linked to from ./Meta)
#
# And, configure ncisources.spec to remove atoms with TTY="XM" (in any source)
# so these XM concepts (whose MRMAP data isn't being inverted) will be removed.
#
# ALSO (if it's not already there, which starting in 2021AB it was) add this
# line to Meta/../DVDIMAGE/config/20##Ax/mrpluscolsfiles.dat:
# "MRCXT.RRF|MRFILES|CUI,SUI,AUI,SAB,CODE,CXN,CXL,RANK,CXS,CUI2,AUI2,HCD,RELA,XC,CVF|Concept Contexts|"

# incantation to fix broken "sort" command:
setenv _POSIX2_VERSION 1


# create ncimid.sources & ncimid.termgroups files
(echo ' SAB| VSAB'; $INV_HOME/bin/api_metadata.sh current_sources --quiet) |sort -t\| +0 -1 >ncimid.sources
$INV_HOME/bin/api_metadata.sh precedence --quiet |sort -t\| +1 -2n >ncimid.termgroups

awk -F\| '$2=="KEEP" || $2 == "UPDATE"{print $1}' ncisources.spec |sort -u >sources.expected
set bad=`cut -d\| -f1 ncimid.sources |sort |comm -23 sources.expected -`
rm -f sources.expected
if ("$bad" != "") then
  echo "First change the following sources to 'EXCLUDE' or 'REMOVE' in ncisources.spec:"
  echo $bad
  exit 1
endif

eval `grep 'set release' runmmsys.s`

cp -p /local/content/MEME/MEME5/mr/umls/${release}/DVDIMAGE/config/$release/user.a.prop template.prop

./genmmsysconfigs.pl
./runmmsys.s >& runmmsys.log
# what was done by fix.mthsab.s is now done by updatevsabs.s (and MMSYS)
#./fix.mthsab.s

mv Meta3/MRCONSO.RRF{,.orig}
./fix.vsrc.atoms.pl Meta3/MRCONSO.RRF.orig >Meta3/MRCONSO.RRF
rm Meta3/MRCONSO.RRF.orig

# change SF of CCS_10 and CCSR_10 from "CCS" to "CCS_10"
mv Meta3/MRSAB.RRF{,.orig}
./fix.ccs.sf.pl Meta3/MRSAB.RRF.orig >Meta3/MRSAB.RRF
rm Meta3/MRSAB.RRF.orig
