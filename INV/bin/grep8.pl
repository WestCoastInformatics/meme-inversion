#!/usr/bin/perl

# Greps input for bytes with 8th bit set

use Getopt::Std;

getopts("c");

$n=0;
while (<>) {
  @bytes = unpack("C*", $_);
  foreach $b (@bytes) {
    next unless ($b>>7) > 0;
    if ($opt_c) {
      $n++;
    } else {
      print;
    }
    last;
  }
}
print $n, "\n" if $opt_c;
exit 0;
