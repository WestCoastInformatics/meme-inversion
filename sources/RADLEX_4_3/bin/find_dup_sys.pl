#!/usr/bin/perl
#
#3/25/2026 SLQ
#find duplicate SYs in field 78 (Synonyms) of Radlex.csv
#input: pipe-delimited file of SYs (e.g., tmp/sys)
#
use strict;
use warnings;

while (<>) {
    chomp;
    my $line = $_;

    # Split on pipe into all fields
    my @fields = split /\|/, $line;

    my %seen;
    my $has_dup = 0;

    for my $field (@fields) {
        # Trim whitespace
        $field =~ s/^\s+//;
        $field =~ s/\s+$//;

        next if $field eq '';  # ignore empty fields

        if ($seen{$field}++) {
            $has_dup = 1;
            last;
        }
    }

    print "$line\n" if $has_dup;
}
