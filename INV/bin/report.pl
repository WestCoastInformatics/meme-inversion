#!/usr/bin/perl
#
# File: report.pl
# Author: Brian Carlsen
# Summary: Concept reporter
# Usage: report.pl -t {CODE,SAID,SCUI,SDUI,SAUI} [-v{1,2,3}] <id>
#
# CHANGES
# 02/29/2008 BAC (1-DG8I1): Use SrcReport.pm library
# 02/07/2008 BAC (1-DG8I1): first version
#
#################################################################

#---------------------
# Configure libraries 
#---------------------
use FindBin qw($Bin);
use lib "$ENV{INV_HOME}/lib";
use lib "$Bin/../lib";
use strict 'vars';
use strict 'subs';
use SrcReport;
use Getopt::Long;


#---------------------
# Initialize vars
#---------------------
our $dir = "";
our $interactive = 0;
our $type = "SAID";

#---------------------
# Process Options
#---------------------
GetOptions(q{-help|?|h} => sub { printHelp();},
           q{-i} => sub { $interactive = 1;  }, 
           q{-v} => sub { SrcReport::setVerbose(1); }, 
           q{-vv} => sub { SrcReport::setVerbose(2); }, 
           q{-vvv} => sub { SrcReport::setVerbose(3); }, 
           q{-dir=s} => \$dir,
           q{-type=s} => \$type );

#---------------------
# Run the program
#---------------------
our ($id) = @ARGV;
if (!$id && !$interactive) {
    die "Must pass id parameter\n";
}
if ($dir) {
    SrcReport::setDir($dir);
    my $vsab = $dir;
    $vsab =~ s/.*\/(.*)\/.*/$1/;
    SrcReport::setVsab($vsab);
}
SrcReport::cacheData();
SrcReport::indexData();
SrcReport::openFiles();
SrcReport::setType($type);
if ($interactive) {

    while (1) {
	print "$type %: ";
	$_ = <STDIN>;
	chop;
	$id = $_;
	SrcReport::setId($id);
	if ($id eq "-v") {
	    SrcReport::setVerbose(1);
	    print "verbose = 1\n"; next;
	}
	if ($id eq "-vv") {
	    SrcReport::setVerbose(2);
	    print "verbose = 2\n"; next;
	}
	if ($id eq "-vvv") {
	    SrcReport::setVerbose(3);
	    print "verbose = 3\n"; next;
	}
	if ($id eq "-t") {
	    print "Enter new type [SAID,CODE,SAUI,SCUI,SDUI]: ";
	    $_ = <STDIN>; chop;
	    if ($_ =~ /^(SAID|CODE|SAUI|SCUI|SDUI)$/) {
		SrcReport::setType($_);
	    } else {
		print "Invalid type :$_\n";
	    }
	    print "Type = $_\n";
	    next;
	}
	if ($id eq "q" || $id eq "quit") {
	    print "Exiting... \n\n"; exit 0;
	}
        SrcReport::printReport($id);
	print "\n--------------------------------------\n\n";

    }

} else {
    my $flag = 0;
    foreach $id (sort split /,/, $id) {
	if ($flag++) {
	    print "\n--------------------------------------\n\n";
	}
	SrcReport::printReport($id);
    }
}

exit 0;

#-----------------------
# Print usage.
#-----------------------
sub printUsage {
    print "Usage: report.pl [-v[vv]] -t {CODE,SCUI,SDUI,SAUI,SAID} [-i|<id>]\n";
}

#-----------------------
# Print help.
#-----------------------
sub printHelp {
  printUsage();
  print qq{
  Tool for generating SRC reports based on CODE, SAUI, SCUI, SDUI
  or SAID (src_atom_id).  Run from a directory containing .src files.
  Can be run against one id, a list of ids, or interactively.  For example,

  % report.pl -t SAUI 128394233     # generates report for a source atom id
  % report.pl 128394233             # generates report for a source atom id (default type)
  % report.pl -t CODE D0923,D0432   # generates a report for 2 codes
  % report.pl -t SCUI -i            # interactive mode using SCUI id types

  In interactive mode, -v[vv] can be used to change verbosity.
  In interactive mode, -t can be used to change the identifier type.
  Interactive mode is more efficient because it has to cache the data
  files only once for all requests.  Same with the multiple-ui mode.

  Options:
    -i:        Interactive mode
    -t <type>: Set identifier type: CODE, SDUI, SCUI, SAUI, SAID
    -h:        Prints this help message
    -v[vv]:    Verbose, more verbose, most verbose

};
  exit 0;
}

