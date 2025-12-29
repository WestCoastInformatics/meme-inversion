#!/usr/bin/perl
#
#
use Getopt::Std;
use lib "$ENV{INV_HOME}/lib";
use SrcStats;


my %options=();
getopts("i:f:m:h", \%options);

if (defined $options{h}) {
  print "Usage: findSrcStats.pl -ifh\n";
  print " This method produces statistics from the supplied source files.\n";
  print "\t-i inputDirectory where the source files are\n";
  print "\t-f outputFile where results are saved.\n";
  print "\t-m mode [0 - normal; 1 - extensive]\n";
  print "\t-h prints this message.\n";
  exit;
}

local $inDir;
if (defined $options{i}) { $inDir = $options{i}; }
else { $inDir = "../src"; }

local $ofile;
if (defined $options{f}) { $ofile = $options{f}; }
else { $ofile = '../tmp/stats.out' }

local $mode;
if (defined $options{m}) { $mode = $options{m}; }
else { $mode = 1; }

print "inDir => $inDir\n";
print "outfile => $ofile\n";
print "mode => $mode\n";

my $stats = new SrcStats();
$stats->setMode($mode);
$stats->process($inDir, $ofile);
print "Done Processing Statistics\n";
