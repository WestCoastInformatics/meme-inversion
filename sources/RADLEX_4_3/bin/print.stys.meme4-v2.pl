#!/usr/bin/perl

#01/23/2006 - SLQ
#changed SAB to E-SAB

# 09/26/2003 - WAK
# updated to MEME4 File Format
# added hashcode field

# 02/14/2005 - SSL
# changed SOURCE_ATOM_ID to SRC_ATOM_ID

use Getopt::Std;
use integer;
use Digest::MD5 qw(md5_hex);

# make the status field setable from the command line

# this script is run after the default STYs have been created by the
# script 'default.stys.pl'
# use it to append Semantic Types to the attributes.src file

unless ($#ARGV == 2){
print <<EOT;

   usage:  $0 SRC_ABRV STATUS <sty_file> 

   This is MEME4 format, an MD5 hash value is created.

   Second argument is the name of the source.
   Use "E-<SRC>" for MTH defaulted STYS.

   Third argument is the status value, 'R' or 'N', usually
   'N' for SEMANTIC_TYPEs.

EOT
	exit;
}

# where sty_file is source_atom_id|default sty

$src = $ARGV[0];
$status = $ARGV[1];
$file = $ARGV[2];
$outfile = "../src/attributes.add";
$found = 0;
$not_found = 0;

# get last 'source_attribute_id' from attributes.src
$lastline = `tail -1 ../src/attributes.src`;
($id) = split(/\|/,$lastline);
unless($id){print "Whoops, no 'Source_Attribute_ID' in ../src/attributes.src\nAre you sure you've got a MEME4 file?\n\n "; exit}
$id++;

print STDERR "\n\t$0  \n\tSRC = $src, STATUS = $status, and source = $file\n\n";
print STDERR "\tStarting Source_attribute ID at $id\n";
print STDERR "\tWriting output to '$outfile'\n";
print STDERR "\n";

open (IN, "$file") or die "Can't open $file, $!";
open (OUT, ">$outfile") or die "Can't open $outfile, $!";

while (<IN>) {
	chomp;
	@fields=split(/\|/);
	if($fields[1] =~ /STY NOT FOUND/){
		$not_found++;
	}
	else {
		$found++;
		$md5 = md5_hex($fields[1]);
		#print OUT "$fields[0]|C|SEMANTIC_TYPE|$fields[1]|$status|$src|N|Y|N\n";
		# meme3
		#print OUT "$id|$fields[0]|C|SEMANTIC_TYPE|$fields[1]|$src|$status|Y|N|N|SOURCE_ATOM_ID||\n";
		# meme4
		print OUT "$id|$fields[0]|C|SEMANTIC_TYPE|$fields[1]|E-$src|$status|Y|N|N|SRC_ATOM_ID|||$md5|\n";
		$id++;
	}
}
close IN;
#print "\n\t$found default STYs Assigned\n\t$not_found Not Found\n\n"; 
printf "%s%8d  %-s\n", "\t", $found, "Default STYs Assigned";
printf "%s%8d  %-s\n", "\t", $not_found, "Not Found";
print "\n";
print "\tOutput file is: $outfile\n\n";

