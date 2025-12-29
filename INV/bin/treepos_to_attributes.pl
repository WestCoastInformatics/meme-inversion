#!/usr/bin/perl
#
# File:    treepos_to_attributes.pl
# Author:  Tim Kao (1/2007)
#
# REMARKS: This script loads the treepos.dat and source_atoms.dat
#          and calls the context processing functions.  It then makes
#          attributes.cxt.src.
#
# CHANGES
# 10/24/2007 BAC (1-FLHKX): Move use open ":utf8" directive.
# 08/29/2007 BAC (1-D9NBZ): put back into repos.
# 01/24/2007 TK (1-D9NBZ): rewrite to process in memory

BEGIN {
unshift @INC, "$ENV{ENV_HOME}/bin";
require "env.pl";
unshift @INC, "$ENV{INV_HOME}/lib";
}

use open ":utf8";

#
# Set variables
#
$|                 = 1;
$ENV{"LANG"}       = "en_US.UTF-8";
$ENV{"LC_COLLATE"} = "C";
my $ignore_rela = 0;
my $id          = 0;
my $dir = ".";
my $generate_sibs = 1;

#
# Parse arguments
#
while (@ARGV) {
  $arg = shift(@ARGV);

  push (@ARGS, $arg) && next unless $arg =~ /^-/;

  if ( $arg eq "-version" ) {
    $print_version = "version";
  }
  elsif ( $arg eq "-v" ) {
    $print_version = "v";
  }
  elsif ( $arg eq "-help" || $arg eq "--help" ) {
    $print_help = 1;
  }
  elsif ( $arg eq "-d" ) {
    $dir = shift(@ARGV);
    print "Reading SA/TP from: $dir\n";

  } elsif ( $arg eq "-nosib" ) {
    $generate_sibs = 0;
  }
  elsif ( $arg =~ /^-ignore_rela$/ ) {
    $ignore_rela = 1;
  }
  elsif ( $arg =~ /^-id$/ ) {
    $id = shift(@ARGV);
  }
  else {
    $badargs   = 1;
    $badswitch = $arg;
  }
}

#
# Print Help/Version info, exit
#
&PrintHelp                    && exit(0) if $print_help;
&PrintVersion($print_version) && exit(0) if $print_version;

#
# Get arguments
#
if ($badargs) {
}
elsif (scalar(@ARGS) == 1) {
    ($source) = @ARGS;
}
else {
    $badargs = 2;
    $badopt = $#ARGS+1;
}

#
# Check dependencies
#
$badargs = 4 unless ( -e "$dir/treepos.dat" );
$badargs = 5 unless ( -e "$dir/source_atoms.dat" );

#
# Print bad argument errors if any found
#
if ($badargs) {
  %errors = (
    1 => "Illegal switch: $badswitch",
    2 => "Bad number of arguments: $badopt",
    4 => "Cannot find required file: $dir/treepos.dat.",
    5 => "Cannot find required file: $dir/source_atoms.dat.",
  );
  &PrintUsage;
  print "\n$errors{$badargs}\n";
  exit(0);
}

#
# Program logic
#
use Contexts;

print "-------------------------------------------------------\n";
print "Starting ...",scalar(localtime),"\n";
print "-------------------------------------------------------\n";
print "Source:              $source\n";
&Contexts::configure( $dir, ".", $ignore_rela, 0, 1 );
&Contexts::printConfiguration;
&Contexts::cacheAtoms;
&Contexts::cacheTreepos;

if ( !&Contexts::checkTreepos ) {
  print "    Treepos check failed ...", scalar(localtime), "\n";
  foreach $error ( sort &Contexts::getErrors ) {
    print "      $error";
  }
}
else {
  print "    Treepos check completed successfully ...", scalar(localtime), "\n";
  if (!$id) {
    print "    Starting id not set, looking up ../src/attributes.src ...", scalar(localtime), "\n";
    $x = `tail -1 ../src/attributes.src`;
    if ($? != 0) {
      print "      Error looking up ../src/attributes.src\n";
      $id = 0;
    }
    ($id) = split /\|/, $x;
  } 
  print "      starting id = ".($id+1)."\n";

  if ( &Contexts::treeposToAttributesFile($generate_sibs, $id,$source) ) {
    print "    Completed successfully ...", scalar(localtime), "\n";
  }
  else {
    print "    Completed with errors...", scalar(localtime), "\n";
    foreach $error ( sort &Contexts::getErrors ) {
      print "      $error";
    }
  }
}    

print "-------------------------------------------------------\n";
print "Finished ...", scalar(localtime), "\n";
print "-------------------------------------------------------\n";
exit(0);

####### Local Procedures #######

sub PrintVersion {
  my ($type) = @_;
  return 1;
}

sub PrintUsage {

  print qq{ This script has the following usage:
 Usage: treepos_to_attributes.pl [-d <dir>] [-ignore_rela] [-nosib] [-id=<src_attr_id>] <source>
    };
}

sub PrintHelp {
  &PrintUsage;
  print qq{
  This script loads the treepos.dat and source_atoms.dat
  and calls the context processing functions.  It then makes
  attributes.src.

  Options:
         -d <dir>                Override default directory setting
         -nosib:                 No siblings.
         -ignore_rela:           Do not use RELA values in trees         -ignore_rela:           Do not use RELA values in trees
                                 when computing children and siblings.
         -id				 	 the starting integer value for the source_attribute_id
         -v[ersion]:             Print version information
         -[-]help:               On-line help
};
  &PrintVersion("version");
  return 1;
}

