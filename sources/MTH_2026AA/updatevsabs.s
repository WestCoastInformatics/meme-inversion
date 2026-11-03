#!/bin/tcsh -f
#
# This script updates the VSABs in $METADIR/20##xx-1-meta.nlm using sab.vsab.map

eval `grep 'set release' runmmsys.s`
set lcrelease = `echo $release | tr '[A-Z]' '[a-z]'`

setenv METADIR /local/content/MEME/MEME5/mr/umls/${release}/DVDIMAGE
set here = `pwd`

if (-f $METADIR/vsab.update.is.complete) then
    echo "VSAB update is already done, not re-running it"
    exit 0
endif

/usr/bin/unzip -U $METADIR/$lcrelease-1-meta.nlm $release/META/MRSAB.RRF.gz >& /dev/null
gunzip $release/META/MRSAB.RRF.gz
mv $release/META/MRSAB.RRF{,.orig}
(./updatevsabs.pl sab.vsab.map $release/META/MRSAB.RRF.orig >$release/META/MRSAB.RRF) >& updatevsabs.log
if (`wc -l <updatevsabs.log` != 0) then
    cat updatevsabs.log
    rm -f $release/META/MRSAB.RRF{.orig,}
    rmdir $release/META
    rmdir $release
    exit 1
endif
rm -f $release/META/MRSAB.RRF.orig

cp -p $release/META/MRSAB.RRF Meta
cp -p $release/META/MRSAB.RRF $METADIR/config/$release

gzip $release/META/MRSAB.RRF
/local/home/tomcata/bin/zip $METADIR/$lcrelease-1-meta.nlm $release/META/MRSAB.RRF.gz |& grep -v 'updating: .*stored '
touch $METADIR/vsab.update.is.complete

rm -f $release/META/MRSAB.RRF.gz
rmdir $release/META
rmdir $release
