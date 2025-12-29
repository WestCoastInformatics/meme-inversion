#!/usr/bin/perl

open(IN,"ATOMS") || die "Can't open ATOMS file";
open(OUT,">ATOMS.SY") || die "Can't open output file";

while(<IN>) {
  print;
  chop;
  ($id,$group,$code,$term)=split(/\|/);
  if (($sy=$term)=~s/^(\[[A-Z]*\] *)//) {
    ($sygrp=$group)=~s#RCD95#RCDSY#;
    print OUT "$id|$group|$code|$term|$sy\n";
    print "$id|$sygrp|$code|$sy\n";
   }
 }

close(IN);
close(OUT);
