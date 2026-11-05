#!/usr/bin/perl

#within field, pipes substituted with '__pipe__'.

use strict;
use warnings;
use Text::CSV;

my $csv = Text::CSV->new({
    binary   => 1,
    auto_diag => 1,
    sep_char => ',',   # input is comma-delimited
});

my $placeholder = '__pipe__';

open my $in,  "<:encoding(UTF-8)", "../tmp/RadLex_modified.csv" or die $!;
open my $out, ">:encoding(UTF-8)", "../orig/radlex_pipe.txt"  or die $!;

while (my $row = $csv->getline($in)) {

    # Replace internal pipes inside each CSV field
    for my $f (@$row) {
        $f =~ s/\|/$placeholder/g if defined $f;
    }

    # Output as pipe-delimited
    print $out join('|', @$row), "\n";
}

close $in;
close $out;
