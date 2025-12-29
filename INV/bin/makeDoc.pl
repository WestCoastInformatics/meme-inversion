#!/usr/bin/perl
#
unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";

use Getopt::Std;
my %options=();
getopts("i:h", \%options);

use MakeDoc;

use strict 'vars';
use strict 'subs';


if (defined $options{h}) {
  print "Usage: makeDoc.pl -ih\n";
  print "  This method creates an MRDOC.RRF if one does not exist.\n";
  print "  In doing so, it reads existing information from the db and \n";
  print "  also scans the .src files and creates the MRDOC.RRF file.\n";
  print "  Any missing information is flagged with ### in the created file.\n";
  print "  The user is then supposed to fill in this information.\n";
  print "\n\t-i input directory were .src files are\n";
  print "\t-h prints this help message.\n\n";
  exit;
}

my $inDir;
if (defined $options{i}) { $inDir = $options{i}; }
else { $inDir = "../src"; }

print "input Directory = $inDir\n";
print $INC{'MakeDoc.pm'};
print "*\n";
MakeDoc::makeMrDoc($inDir, $inDir);
print "Done creating MRDOC.RRF\n\n";



