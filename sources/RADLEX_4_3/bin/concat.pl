#!/usr/bin/perl

#created by SLQ 04/23/2019
#rm extra end of line characters within entries
#substitutes tab w/ space

open (IN,"<../orig/fromprovider/RADLEX_no_german.csv") or die "can't open IN, $!";
binmode(IN, ":utf8");
open (OUT,">../tmp/RadLex_modified.csv") or die "can't open OUT, $!";
binmode(OUT, ":utf8");

while(<IN>){
	chomp;
	s/\t/ /g;
	if(/^http/){
	#if(/.*?\|.*/){
       print OUT "$prev\n";
       $prev='';
	}
    $prev.="$_";
}
print OUT "$prev\n";
close (IN);
