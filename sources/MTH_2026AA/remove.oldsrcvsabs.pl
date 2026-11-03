#!/usr/bin/perl
#
# e.g.: remove.oldsrcvsabs.pl classes_atoms.src.orig >classes_atoms.src

die "usage: $0 classes_atoms.src.orig, stopped" if $#ARGV != 0;

# force removal of CCS_2005 SRC atoms that mmsys erroneously fails to delete
# $rmCODE{"V-CCS_2005"} = 1;

$mapfile = "bin/sab.vsab.map";
open(MAP, $mapfile);
while (<MAP>) {
    ($RSAB, $oldVSAB, $newVSAB) = split(/[|\n]/);
    $rmCODE{"V-" . $oldVSAB} = 1 if $oldVSAB ne $newVSAB &&
        $newVSAB ne 'same' && $oldVSAB ne 'MTH';
}

while (<>) {
    @f = split(/[|\n]/);
    # fields: src_atom_id,VSAB,termgroup,CODE,status,tbr,released,STR,SUPPRESS,
    #         SAUI,SCUI,SDUI,LAT,order_id,CUI
    #
    next if $f[1] eq 'SRC' && $rmCODE{$f[3]};
    next if $f[15] eq 'C1976636';  # remove "LOINCPARTS" concept
    print $_;
}
