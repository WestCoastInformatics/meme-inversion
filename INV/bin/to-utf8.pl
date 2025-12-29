#!/usr/bin/perl

# Converts from known encodings to UTF-8

# Command line options:
# -s <encoding> (source encoding - to see a full list use -e)
# -e (show all encodings)
# -d (ensure \r\n line termination)
# -u (ensure \n line termination)

# Standard source encodings:
# CP1252 -> cp1252
# ISO-8859-1

use Getopt::Std;
getopts("s:edu");

use Encode;
use Encode::Encoder;

# All available encodings
if ($opt_e) {
  print join("\n", Encode->encodings(":all")), "\n";
  exit 0;
}

die "Need a source encoding in -s\n" unless $opt_s;
die "Encoding: $opt_s not found\n" unless grep { $_ eq $opt_s } Encode->encodings(":all");

die "No encoder found for: $opt_s\n" unless find_encoding($opt_s)->perlio_ok;

#binmode(STDOUT, ":utf8");
while (<>) {
  die "Error in encoding" unless &Encode::from_to($_, $opt_s, 'utf8');
  if ($opt_d && !m/\r$/) {
    chomp;
    $_ .= "\r\n";
  } elsif ($opt_u && m/\r$/) {
    s/\r$//;
  }
  print;
}
exit 0;
