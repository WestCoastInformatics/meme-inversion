#!/usr/bin/perl
#
# counts all non-alphanumeric characters, prints out list 
unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';
use CharCount;
use Logger;

use Getopt::Std;
my %options=();
getopts("hf:m:a:", \%options);
if (defined $options{h}) {
  print "Usage: charCount.pl -ciowh\n";
  print "This method counts the chars in a file.\n";
  print "\t-f - name of the file\n";
  print "\t-m - file mode (format) - supports any Encode->encodings. [utf8]\n";
  print "\t-a - report charcounts whose ord is > the given number. [127]\n";
  print "\t-h - prints this help message.\n";
}

if (!defined $options{f}) {
  print "Must supply a file via the -f option.\n";
  exit;
}

our $cc = new CharCount;
our $ans = 0;
if (!defined $options{m}) { $ans = $cc->doFile($options{f}); }
else { $ans = $cc->doFile($options{f}, $options{m}); }
if ($ans == 1) {
  open (OUT, '>-');
  if (!defined $options{a}) { $cc->report(\*OUT);}
  else { $cc->report(\*OUT, $options{a}); }
  close(OUT);
}

