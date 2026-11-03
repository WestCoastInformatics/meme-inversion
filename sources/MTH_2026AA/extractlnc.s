#!/bin/tcsh -f

# incantation to fix broken "sort" command:
setenv _POSIX2_VERSION 1

set release=2020AB

setenv METADIR /local/content/MEME/MEME5/mr/umls/${release}/DVDIMAGE
setenv DESTPREFIX $METADIR/../subset
#setenv MMSYS_HOME /meme_work/umls/code/SMMS/MMSYS
setenv MMSYS_HOME $METADIR
set here = `pwd`


# make subsets

setenv CLASSPATH "${MMSYS_HOME}:${MMSYS_HOME}/lib/jpf-boot.jar"

mkdir ${DESTPREFIX}4
mkdir ${DESTPREFIX}4/METASUBSET
chmod o+w ${DESTPREFIX}4/METASUBSET
ln -s ${DESTPREFIX}4/METASUBSET METASUBSET4
ln -s METASUBSET4 Meta4
pushd $MMSYS_HOME >& /dev/null
$MMSYS_HOME/jre/linux/bin/java -Djava.awt.headless=true -Djpf.boot.config=$MMSYS_HOME/etc/subset.boot.properties -Dlog4j.configuration="file://$MMSYS_HOME/etc/subset.log4j.properties" -Dscript_type=.sh -Dfile.encoding=UTF-8 -Dinput.uri=$METADIR -Doutput.uri=${DESTPREFIX}4/METASUBSET -Dmmsys.config.uri=$here/ncilnc.prop -Xms300M -Xmx1000M org.java.plugin.boot.Boot
popd >& /dev/null

# make MRCXTs

cd $MMSYS_HOME
setenv JAVA_HOME jre/linux

$MMSYS_HOME/jre/linux/bin/java -Djava.awt.headless=true \
    -Djpf.boot.config=$MMSYS_HOME/etc/cxt.boot.properties \
    -Dfile.encoding=UTF-8 -Xms300M -Xmx1000M -Dbuild.sibs=true \
    -Dbuild.children=true -Dcompute.xc=true -Dversioned.sabs=true \
    -Dadd.unicode.bom=false -Dwrite.mrcxt.file.statistics=false \
    -Dmax.contexts=false -Dsource.dir=${DESTPREFIX}4/METASUBSET \
    org.java.plugin.boot.Boot

cd $here/Meta4

mv MRSAB.RRF{,.orig}
awk 'BEGIN{FS=OFS="|"} $3 ~ /LNC_/{$5 = "LOINC, " substr($3,5,1) "." substr($3,7); $7 = substr($3,5)}{print $0}' MRSAB.RRF.orig >MRSAB.RRF
rm -f MRSAB.RRF.orig

mv MRCONSO.RRF{,.orig}
sed '/|SRC|V..|V-LNC/{; s/LNC\(.\)/LNC_\1_/g; s/LOINC, \(.\)/LOINC, \1./; }' MRCONSO.RRF.orig >MRCONSO.RRF
rm -f MRCONSO.RRF.orig
