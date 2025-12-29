#!/usr/bin/perl
#
#
use Getopt::Std;
use lib "$ENV{INV_HOME}/lib";
use QaStats;


my %options=();
getopts("i:h", \%options);

if (defined $options{h}) {
  print "Usage: findSrcStats.pl -ifh\n";
  print " This method produces statistics from the supplied source files.\n";
  print "\t-i inputDirectory where the source files are\n";
  print "\t-h prints this message.\n";
  exit;
}

local $inDir;
if (defined $options{i}) { $inDir = $options{i}; }
else { $inDir = "../src"; }

print "inDir => $inDir\n";

my $stats = new QaStats();
$stats->process($inDir);
print "Done Processing Statistics\n";
