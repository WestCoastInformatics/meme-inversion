#!/usr/bin/perl

use strict;
use warnings;

my $mainfile   = "../src/classes_atoms.src";
my $mergefile  = "../src/mergefacts.src";

my $uniqout    = "../tmp/classes_unique.txt";
my $dupeout    = "../tmp/classes_dupes.txt";
my $mergeout   = "../tmp/mergefacts_new.txt";

open my $IN,  "<", $mainfile  or die "Cannot open $mainfile: $!";
open my $MF,  "<", $mergefile or die "Cannot open $mergefile: $!";

open my $UO,  ">", $uniqout   or die "Cannot write $uniqout: $!";
open my $DO,  ">", $dupeout   or die "Cannot write $dupeout: $!";
open my $MO,  ">", $mergeout  or die "Cannot write $mergeout: $!";

my %seen;
my %dupe_codes;   # store codes of duplicates so we can remove them from mergefacts

################################################
## PASS 1 — Process main file, detect duplicates
################################################

while (<$IN>) {
    chomp;
        my @f = split(/\|/, $_, -1);

            # Fields:
		# field 1 = said      = $f[0]
                # field 3 = termgroup = $f[2]
                # field 4 = code      = $f[3]
                # field 8 = string    = $f[7]

			my $key = join("||", $f[2], $f[3], $f[7]);

			if ($seen{$key}++) {
				print $DO "$_\n";      # duplicate
				$dupe_codes{$f[0]} = 1;  # mark said for removal in mergefacts
			} 
			else {
				print $UO "$_\n";      # unique
			}
}

close $IN;
close $UO;
close $DO;

#########################################################
## PASS 2 — Process mergefacts, remove rows with dupe code
##########################################################

while (<$MF>) {
	chomp;
	my @f = split(/\|/, $_, -1);

	#mergefacts format:
	#field 1 (index 0) = code we match against duplicates
	#field 3 (index 2) = code we match against duplicates
	my $code0 = $f[0];
	my $code2 = $f[2];

	if (($dupe_codes{$code0}) || ($dupe_codes{$code2})) {
		next;   # skip — this row belongs to a duplicate
	}

	print $MO "$_\n";   # keep
}

close $MF;
close $MO;

