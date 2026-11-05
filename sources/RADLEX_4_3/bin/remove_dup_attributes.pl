#!/usr/bin/perl

use strict;
use warnings;

my $infile  = "../src/attributes.src";
my $uniqout = "../tmp/attributes_unique.txt";
my $dupesout = "../tmp/attributes_dupes.txt";

open my $IN,  "<", $infile  or die "Cannot open $infile: $!";
open my $UO,  ">", $uniqout or die "Cannot write $uniqout: $!";
open my $DO,  ">", $dupesout or die "Cannot write $dupesout: $!";

my %seen;

while (<$IN>) {
    chomp;
        my @f = split(/\|/, $_, -1);

            # Fields: 0-based indexing
                 #Field 2 = $f[1] code
                 # Field 4 = $f[3] ATN
                 # Field 5 = $f[4] ATV

                      my $key = join("||", $f[1], $f[3], $f[4]);

			if ($seen{$key}++) {
				print $DO "$_\n";   # duplicate
			} 
			else {
				print $UO "$_\n";   # unique
			}
}
close $IN;
close $UO;
close $DO;
