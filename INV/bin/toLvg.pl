#!/usr/bin/perl
#
use Getopt::Std;
use lib "$ENV{INV_HOME}/lib";
use LVG;


my %options=();
getopts("hi:o:t:", \%options);

if (defined $options{h}) {
  print "Usage: findSrcStats.pl -ifh\n";
  print " This method produces statistics from the supplied source files.\n";
  print "\t-i inputDirectory where the source files are\n";
  print "\t-f outputFile where results are saved.\n";
  print "\t-m mode [0 - normal; 1 - extensive]\n";
  print "\t-h prints this message.\n";
  exit;
}

my $lvg = new LVG();
$lvg->doFile("lvgin", "lvgout", 2, 1, 2, 3);
print "Done Processing lvg\n";
