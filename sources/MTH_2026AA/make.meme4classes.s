#!/bin/tcsh -f

# incantation to fix broken "sort" command:
setenv _POSIX2_VERSION 1

bin/get.saidpts.pl >said.ptsaid
sed 's/.*|//' said.ptsaid |sort -u -o ptsaid.order
cp -p classes_atoms.src classes_atoms.src.raw
#sed 's/|[^|]*|[^|]*|[^|]*$//' classes_atoms.src >classes_atoms3.src
#make.meme4classes.pl >classes_atoms.src
#gzip classes_atoms3.src classes_atoms.src.raw

# inv1.spec applies atom retention before identity-map generation. This step
# only converts the retained raw atom layout to the insertion atom layout.
sed 's/|[^|]*\(|[^|]*\)|[^|]*$/\1/' classes_atoms.src.raw >! classes_atoms.src
