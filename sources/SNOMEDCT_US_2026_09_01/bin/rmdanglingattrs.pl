#!/usr/bin/perl
#
# e.g.:
#
# % mv ../src/attributes.src{,.old}
# % rmdanglingattrs.pl ../src/attributes.src.old >../src/attributes.src
# % rm ../src/attributes.src.old

open(INPUT, "../src/classes_atoms.src");
while (<INPUT>) {
    @f = split(/[|\n]/, $_);
    $descId{$f[9]} = 1;
}

while (<>) {
    @f = split(/[|\n]/, $_);
    if ($f[10] eq 'SOURCE_AUI') {
        if ($descId{$f[1]}) {
            print $_;
        }
    } else {
        print $_;
    }
}
