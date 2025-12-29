#!/usr/bin/perl
#
unshift(@INC,"$ENV{INV_HOME}/bin");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";

use strict 'vars';
use strict 'subs';
use open ':utf8';

use NLMConfig;
use Logger;
use SrcDiffs;
use Getopt::Std;

my %options=();
getopts("hqc:a:b:o:w:", \%options);



if (defined $options{h}) {
  print "Usage: findSrcDiffs.pl -cabowh\n";
  print " This method produces file differences in two source directories\n";
  print " in the form of AmB_* and BmA_* for atoms/attrs/merges/rels.\n";
  print "\t-c - configuration file - defaults to none\n";
  print "\t-a - input directory of source A. Defaults to ../src_old\n";
  print "\t-b - input directory of source B. Defaults to ../src\n";
  print "\t-o - output directory. Defaults to ../tmp\n";
  print "\t-w - which ones to produce. uses the following bit flags.\n";
  print "\t\t 1 - atoms\n";
  print "\t\t 2 - attributes\n";
  print "\t\t 4 - merges\n";
  print "\t\t 8 - relationships\n";
  print "\t\t 16 - contexts\n";
  print "\t-h - prints this help message.\n";
  exit;
}

our ($Cfg, $Log, $cfgFile) = ('', '');

if (!defined $options{c}) {
  print "Must supply a valid config file as -c option.\n";
  exit;
}
$cfgFile = $options{c};

# create the config object
$Cfg = new NLMConfig($cfgFile);

# create the log object.
my $tdir = $Cfg->getEle('TEMPDIR', '../tmp');
my $vsab = $Cfg->getEle('VSAB', 'NONE');
my $lmode = $Cfg->getEle('LogMode', 'Append');
$Log = new Logger("$tdir/Qa_${vsab}.log", $lmode, 'INFO');

SrcDiffs->init(\$Log, \$Cfg);

our $diffs = new SrcDiffs();

# now set any command line parms overriding the ones in cfg file.
$diffs->setADir($options{a}) if (defined $options{a});
$diffs->setBDir($options{b}) if (defined $options{b});
$diffs->setODir($options{o}) if (defined $options{o});
$diffs->setWhich($options{w}) if (defined $options{w});
$diffs->process();
print "Done Processing Diffenrences\n";




