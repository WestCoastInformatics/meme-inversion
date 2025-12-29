#!/usr/bin/perl
#
# File:    bt_nt_to_treepos.pl
# Author:  Deborah Shapiro (6/2000)
#
# REMARKS: This script converts broader than/narrower than relationships
#          into the treepos format.  It starts by loading the bt_nt_rels.dat
#	   file and the source_atoms.dat file.  It creates the treepos.dat
#	   file at the end from the bt_nt_treepos table.  When the option
#	   -addroot is added, the user will be prompted for additional
#	   data regarding the root.
#
# Usage: bt_nt_to_treepos.pl [-addroot]
#
# Porting Status: Ported to oracle
#
# CHANGES
# 10/24/2007 BAC (1-FLHKX): Move use open ":utf8" directive.
# 05/31/2007 BAC (1-D9NBZ): in-memory algorithms.
# 11/13/2006 BAC (1-CDMK9): better support for managing multiple users.y
# 06/30/2000 (3.1.0) in progress
$release           = "3";
$version           = "1.0";
$version_authority = "DSS";
$version_date      = "06/14/2000";

BEGIN {
unshift @INC, "$ENV{ENV_HOME}/bin";
require "env.pl";
unshift @INC, "$ENV{INV_HOME}/lib";
}
use open ":utf8";

#
# Check required environment variables
# n/a

#
# Turn on auto-flush
#
$| = 1;

#
# Set variables
#
$dir = ".";

#
# Parse arguments
#
while (@ARGV) {
  $arg = shift(@ARGV);

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
    print "Using dir: '$dir'\n";
  }
  elsif ( $arg eq "-addroot" ) {    
    $addroot = "1";
    print "Please enter a src_atom_id: ";
    chop( $src_atom_id = <STDIN> );
    print "Please enter a hcd: ";
    chop( $hcd = <STDIN> );
    print "Please enter a code: ";
    chop( $code = <STDIN> );
    print "Please enter an atom name: ";
    chop( $string = <STDIN> );
    print "Please enter a termgroup: ";
    chop( $termgroup = <STDIN> );
    print "Do you want the root to be added to treepos.dat? (Y/N)";
    chop( $tmp = <STDIN> );
    $addroottreepos     = "0";
    $addrootsourceatoms = "0";

    if ( $tmp eq "Y" || $tmp eq "y" ) {
      $addroottreepos = "1";
    }
    else {
      $addroottreepos = "0";
    }
    print "\nNote: All atoms including the root must be in source atoms.dat.\n";
    print "Do you want the root to be added to source_atoms.dat? (Y/N)";
    chop( $tmp = <STDIN> );
    if ( $tmp eq "Y" || $tmp eq "y" ) {
      $addrootsourceatoms = "1";
    }
    else {
      $addrootsourceatoms = "0";
    }
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
# Check dependencies
#
$badargs = 4 unless ( -e "$dir/bt_nt_rels.dat" );
$badargs = 6 unless ( -e "$dir/source_atoms.dat" );

if ( $addroot && !$src_atom_id ) {
  $badargs = 8;
}

if ( $addroot && !$string ) {
  $badargs = 9;
}

print "badargs = $badargs \n";

#
# Print bad argument errors if any found
#
if ($badargs) {
  %errors = (
    1 => "Illegal switch: $badswitch",
    4 => "Cannot find required file: bt_nt_rels.dat.",
    6 => "Cannot find required file: $dir/source_atoms.dat.",
    8 => "src_atom_id must be entered.",
    9 => "string must be entered."
  );
  &PrintUsage;
  print "\n$errors{$badargs}\n";
  exit(0);
}

#
# Program logic
#
use Contexts;
print qq{
-------------------------------------------------
Starting ... }, scalar(localtime), qq{
-------------------------------------------------
};
&Contexts::configure( $dir, ".", 1, 0, 1 );
&Contexts::printConfiguration;
&Contexts::cacheAtoms;
&Contexts::cacheRels;

if ($addroot) {
  print qq{
    ADDROOT mode invoked
      src_atom_id:       $src_atom_id
      hcd:               $hcd
      termgroup:         $termgroup
      code:              $code
      string:            $string
      add treepos root:  }, ( ($addroottreepos)     ? "true" : "false" ), qq{
      add atom root:     }, ( ($addrootsourceatoms) ? "true" : "false" ), "\n";
  if (&Contexts::relsToTreepos) {
    print "    Completed Successfully ...", scalar(localtime), "\n";
  }
  else {
    print "    Completed with errors ...", scalar(localtime), "\n";
    foreach $error ( sort &Contexts::getErrors ) {
      print "      $error";
    }
  }
  &Contexts::configureRoot( $src_atom_id, $termgroup, $code, $string );
  if ($addroottreepos) {
    &Contexts::addTopLevelTreeposRela;
    &Contexts::addRootToTreepos;
  }
  if ($addrootsourceatoms) {
    &Contexts::appendRootToAtomsFile;
  }
  &Contexts::writeTreeposFile;
}
else {
  if (&Contexts::relsToTreeposFile) {
    print "    Completed Successfully ...", scalar(localtime), "\n";
  }
  else {
    print "    Completed with errors ...", scalar(localtime), "\n";
    foreach $error ( sort &Contexts::getErrors ) {
      print "      $error";
    }
  }
}

print qq{-------------------------------------------------
Finished ... }, scalar(localtime), qq{
-------------------------------------------------
};
exit 0;

####### Local Procedures #######

sub PrintVersion {
  my ($type) = @_;
  print "Release $release: version $version, "
    . "$version_date ($version_authority).\n"
    if $type eq "version";
  print "$version\n" if $type eq "v";
  return 1;
}

sub PrintUsage {

  print qq{ This script has the following usage:
 Usage: bt_nt_to_treepos.pl [-d <dir>] [-addroot]
    };
}

sub PrintHelp {
  &PrintUsage;
  print qq{
 This script converts broader than/narrower than relationships 
 into the treepos format.  It starts by loading the bt_nt_rels.dat
 file and the source_atoms.dat file. It creates the treepos.dat file 
 from the bt_nt_treepos table.  When the option -addroot is added, the 
 user will be prompted for additional information regarding the root. 

  Options:
         -d <dir>                Override default directory setting
         -v[ersion]:             Print version information
         -[-]help:               On-line help
};
  &PrintVersion("version");
  return 1;
}
