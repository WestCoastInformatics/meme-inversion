#!/bin/csh -f

# script to create file of MDR CODE|version present in

echo "MDR8.0"
grep '|MDR|PT|' /umls_arc/release_root/2005AC/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|8.0")}' >> mdr_by_version.txt

echo "MDR8.1"
grep '|MDR|PT|' /umls_arc/release_root/2006AA/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|8.1")}' >> mdr_by_version.txt

echo "MDR9.0"
grep '|MDR|PT|' /umls_arc/release_root/2006AC/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|9.0")}' >> mdr_by_version.txt

echo "MDR9.1"
grep '|MDR|PT|' /umls_arc/release_root/2007AA/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|9.1")}' >> mdr_by_version.txt

echo "MDR10.0"
grep '|MDR|PT|' /umls_arc/release_root/2007AB/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|10.0")}' >> mdr_by_version.txt

echo "MDR10.1"
grep '|MDR|PT|' /umls_arc/release_root/2008AA/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|10.1")}' >> mdr_by_version.txt

echo "MDR11.0"
grep '|MDR|PT|' /umls_arc/release_root/2008AB/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|11.0")}' >> mdr_by_version.txt

echo "MDR11.1"
grep '|MDR|PT|' /umls_arc/release_root/2009AA/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|11.1")}' >> mdr_by_version.txt

echo "MDR12.0"
grep '|MDR|PT|' /umls_arc/release_root/2009AB/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|12.0")}' >> mdr_by_version.txt

echo "MDR12.1"
grep '|MDR|PT|' /umls_arc/release_root/2010AA/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|12.1")}' >> mdr_by_version.txt

echo "MDR13.0"
grep '|MDR|PT|' /umls_arc/release_root/2010AB/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|13.0")}' >> mdr_by_version.txt

echo "MDR13.1"
grep '|MDR|PT|' /umls_arc/release_root/2011AA/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|13.1")}' >> mdr_by_version.txt

echo "MDR14.0" 
grep '|MDR|PT|' /umls_arc/release_root/2011AB/Full/RRF/META/MRCONSO.RRF | gawk -F\| '{print($14"|14.0")}' >> mdr_by_version.txt

echo "MDR14.1"
grep 'MDR14_1/PT' /umls_arc/src_root/SABS/MDR/MDR14_1/src/classes_atoms.src | gawk -F\| '{print($4"|14.1")}' >> mdr_by_version.txt

echo "MDR15.0"
grep 'MDR15_0/PT' /umls_s/src_root/MDR15_0/src/classes_atoms.src | gawk -F\| '{print($4"|15.0")}' >> mdr_by_version.txt

echo "MDR15.1"
grep 'MDR15_1/PT' /umls_s/src_root/MDR15_1/src/classes_atoms.src | gawk -F\| '{print($4"|15.1")}' >> mdr_by_version.txt

echo "MDR16.0 (not yet released)"
grep 'MDR16_0/PT' /umls_s/src_root/MDR16_0/src/classes_atoms.src | gawk -F\| '{print($4"|16.0")}' >> mdr_by_version.txt

sort -u mdr_by_version.txt -o mdr_by_version.txt

cut -f1 -d\| mdr_by_version.txt | sort -u > mdr_allcodes.txt

sort -t\| +3 -4 /umls_s/src_root/MDR16_0/src/classes_atoms.src | join -t\| -j1 4 -j2 1 -o 1.4 1.3 - mdr_allcodes.txt > mdr_allcodes.tty

sort -t\| +3 -4 /umls_s/src_root/MDR16_0/src/classes_atoms.src | join -t\| -j1 4 -j2 1 -o 2.1 -v 2 - mdr_allcodes.txt > mdr_missingcodes


