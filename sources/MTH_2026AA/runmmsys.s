#!/bin/tcsh -f
#
# This script runs MMSYS to create three subsets and their MRCXT files:
#
# 1. MSH,
# 2. SNOMEDCT or SCTSPA (generally one of the two since their updates are
#    staggered), and
# 3. MTH and other sources besides MSH and whichever of SNOMEDCT/SCTSPA was
#    updated.
#
# Note: as of 2022AB, set build.sibs=false due to huge numbers of SIBS in LNC,
# NCBI, and to a lesser extent, OMIM.

# incantation to fix broken "sort" command:
setenv _POSIX2_VERSION 1

set release=2026AA

setenv METADIR /local/content/MEME/MEME5/mr/umls/${release}/DVDIMAGE

setenv DESTPREFIX $METADIR/../subset
#setenv MMSYS_HOME /h1/meme/meme_work/umls/code/SMMS/MMSYS
setenv MMSYS_HOME $METADIR
set here = `pwd`


# make subsets

setenv CLASSPATH "${MMSYS_HOME}:${MMSYS_HOME}/lib/jpf-boot.jar"

#mkdir ${DESTPREFIX}1
#mkdir ${DESTPREFIX}1/METASUBSET
#chmod o+w ${DESTPREFIX}1/METASUBSET
#ln -s ${DESTPREFIX}1/METASUBSET METASUBSET1
#ln -s METASUBSET1 Meta1
#pushd $MMSYS_HOME >& /dev/null
#$MMSYS_HOME/jre/linux/bin/java -Djava.awt.headless=true -Djpf.boot.config=$MMSYS_HOME/etc/subset.boot.properties -Dlog4j.configuration="file://$MMSYS_HOME/etc/subset.log4j.properties" -Dscript_type=.sh -Dfile.encoding=UTF-8 -Dinput.uri=$METADIR -Doutput.uri=${DESTPREFIX}1/METASUBSET -Dmmsys.config.uri=$here/ncimsh.prop -Xms300M -Xmx1000M org.java.plugin.boot.Boot
#popd >& /dev/null

#mkdir ${DESTPREFIX}2
#mkdir ${DESTPREFIX}2/METASUBSET
#chmod o+w ${DESTPREFIX}2/METASUBSET
#ln -s ${DESTPREFIX}2/METASUBSET METASUBSET2
#ln -s METASUBSET2 Meta2
#pushd $MMSYS_HOME >& /dev/null
#$MMSYS_HOME/jre/linux/bin/java -Djava.awt.headless=true -Djpf.boot.config=$MMSYS_HOME/etc/subset.boot.properties -Dlog4j.configuration="file://$MMSYS_HOME/etc/subset.log4j.properties" -Dscript_type=.sh -Dfile.encoding=UTF-8 -Dinput.uri=$METADIR -Doutput.uri=${DESTPREFIX}2/METASUBSET -Dmmsys.config.uri=$here/ncisct.prop -Xms300M -Xmx1000M org.java.plugin.boot.Boot
#popd >& /dev/null

mkdir ${DESTPREFIX}3
mkdir ${DESTPREFIX}3/METASUBSET
chmod o+w ${DESTPREFIX}3/METASUBSET
ln -s ${DESTPREFIX}3/METASUBSET METASUBSET3
ln -s METASUBSET3 Meta3
pushd $MMSYS_HOME >& /dev/null
$MMSYS_HOME/jre/linux/bin/java -Djava.awt.headless=true -Djpf.boot.config=$MMSYS_HOME/etc/subset.boot.properties -Dlog4j.configuration="file://$MMSYS_HOME/etc/subset.log4j.properties" -Dscript_type=.sh -Dfile.encoding=UTF-8 -Dinput.uri=$METADIR -Doutput.uri=${DESTPREFIX}3/METASUBSET -Dmmsys.config.uri=$here/ncirest.prop -Xms300M -Xmx1000M org.java.plugin.boot.Boot
popd >& /dev/null


# add ALL MTH rels to subset3
mv Meta3/MRREL.RRF{,.raw}
awk -F\| '$11=="MTH"' Meta/MRREL.RRF |sed "s/MTH|/MTH_${release}|/g" |sort -u - Meta3/MRREL.RRF.raw -o Meta3/MRREL.RRF


# make MRCXTs

cd $MMSYS_HOME
setenv JAVA_HOME jre/linux
chmod a+x $JAVA_HOME/bin/java

#$MMSYS_HOME/jre/linux/bin/java -Djava.awt.headless=true \
#    -Djpf.boot.config=$MMSYS_HOME/etc/cxt.boot.properties \
#    -Dfile.encoding=UTF-8 -Xms300M -Xmx1000M -Dbuild.sibs=true \
#    -Dbuild.children=true -Dcompute.xc=true -Dversioned.sabs=true \
#    -Dadd.unicode.bom=false -Dwrite.mrcxt.file.statistics=false \
#    -Dmax.contexts=false -Dsource.dir=${DESTPREFIX}1/METASUBSET \
#    org.java.plugin.boot.Boot

#$MMSYS_HOME/jre/linux/bin/java -Djava.awt.headless=true \
#    -Djpf.boot.config=$MMSYS_HOME/etc/cxt.boot.properties \
#    -Dfile.encoding=UTF-8 -Xms300M -Xmx1000M -Dbuild.sibs=true \
#    -Dbuild.children=true -Dcompute.xc=true -Dversioned.sabs=true \
#    -Dadd.unicode.bom=false -Dwrite.mrcxt.file.statistics=false \
#    -Dmax.contexts=false -Dsource.dir=${DESTPREFIX}2/METASUBSET \
#    org.java.plugin.boot.Boot

$MMSYS_HOME/jre/linux/bin/java -Djava.awt.headless=true \
    -Djpf.boot.config=$MMSYS_HOME/etc/cxt.boot.properties \
    -Dfile.encoding=UTF-8 -Xms300M -Xmx1000M -Dbuild.sibs=false \
    -Dbuild.children=true -Dcompute.xc=true -Dversioned.sabs=true \
    -Dadd.unicode.bom=false -Dwrite.mrcxt.file.statistics=false \
    -Dmax.contexts=false -Dsource.dir=${DESTPREFIX}3/METASUBSET \
    org.java.plugin.boot.Boot
