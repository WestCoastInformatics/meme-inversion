#!/usr/bin/perl 
# SRCbuilder4.pl
# Wed Jul  9 15:13:18 PDT 2003 - WAK 
# MEME4 version based on SRCbuilder.pl
#
# 04/30/04 - WAK
# changed output to use CODE/TERMGROUP rather than SAID
# as the default output
#
# 12/30/03 - WAK
# src_data file is optional
# 09/10/03 - WAK
# SOS is no longer a valid type for src_data
# and no SOS attributes are created.
# 03/19/03 - WAK
# added a test for "true" sources when reading 'sources.src'
# if the source != the normalized source the source is ignored
# this test was added specifically for MeSH sources like PA,FX,EC, etc.
#
#
# Rules:
# 1) requires a file 'src_data', which consists of:
# Source Name|Code|Type|Data|
# Source Name - matches the values in the sources.src file
# Code - either 'R' for Root or 'V' for versioned
# Type - SY, HT, SSN, 
# (Root atoms are created only if the -n flag is used)
#
# 2) Primary source is the first listed in sources.src
#
# Output
# Errors are written to STDERR
# Summary info is written to STDOUT and can be redirected to a file
# 
# Notes
# This script builds the files 'class_src', 'rel_src', 'attr_src',
# and 'merge_src'. These files contain all the necessary SRC bits
# in MEME3 format and can be prepended to the standard .src files.
#
# This script takes most all of what it needs from the 'sources.src'
# file, and therefore won't run without one. 
# Other stuff such as SY, HT, and SSN atoms require further
# information. This is in the 'src_data' file.

# what happens:
# read sources.src & make a hash of all SAB names
# 
# read src_data & check the contents of the file
# save the data in hashes with SAB as key
#
# read sources.src again
# and print the various bits for each source

use integer;
use Getopt::Std;
use Digest::MD5 qw(md5_hex);

$| = 1;
%opt = ();
$root_summ = 0;

$at_lncnt = 1;
$rel_lncnt = 1;

$class = "class_src";
$attr = "attr_src";
$rel = "rel_src";
$merge = "merge_src";
$src_data = "src_data";

# counts for the different bits
$rpt = $rab = $rssn = $rht = $rsy = $vpt = $vab = $vsy = 0;

# Command line Options
# s	starting SAID
# n	for new source

getopts("s:nth", \%opt);	# get options

if($opt{'h'}){&print_usage; &print_help; exit 1}

if($opt{'s'}){
	$said = $opt{'s'};
}
else{
	print STDERR "ERROR: no SAID assigned on the command line\n";
	&print_usage();
	exit 1;
}

if($opt{'n'}){
	#print "\t Making ROOT atoms and rels\n";
	$root++;
	if($opt{'t'}){ 
		print "\t Making Translation_of rel\n";
		$trans++;
	}
}
if($said){
	print "Starting SAIDs at $opt{'s'}\n";
}
else{
	print "\tNo SAID provided\n";
	&print_usage();
	exit 1;
}

open(ATTR, ">$attr") or die "Can't open $attr, $!";
open(CLASS, ">$class") or die "Can't open $class, $!";
open(REL, ">$rel") or die "Can't open $rel, $!";
open(MERGE, ">$merge") or die "Can't open $merge, $!";
open(SOURCE, "sources.src") or die "Can't open sources.src, $!";

# read sources.src for SABs
while(<SOURCE>){
	next if(/^#/);
	($src_name,$low_src,$rlev,$norm_src,$str_src,$ver,$src_fam,$off_name)=split(/\|/);
	if($src_name eq $norm_src){
		$SAB{$src_name}++;
	}
	else{
		print "*** Ignoring \"$src_name\", not a real source ***\n";
	}
}

# read the src_data file and check the contents
if(-e $src_data){
open(DATA, "$src_data") or warn "Can't find file: 'src_data', $!";
while(<DATA>){
	chomp;
	next if(/^#/);
	next if(/^\s*$/);
	# print "TEST: $_\n";
	($src,$code,$type,$data) = split(/\|/);
	unless($SAB{$src}){ 
		print STDERR "ERROR: SAB \"$src\" in $src_data \n$.: $_\nmust be in sources.src\n";
		exit 1;
	}
	unless($code =~ /R|V/){ 
		print STDERR "ERROR: Code \"$code\" in $src_data \n$.: $_\nmust be \"R\" or \"V\"\n";
		exit 1;
		}
	 # allowable types
	 unless($type =~ /STY|SSN|SY|HT/){ 
		print STDERR "ERROR: Type \"$type\: in $src_data \nmust be \"STY\", \"SSN\", \"SY\", or \"HT\"\n";
		exit 1;
	}

	if($code eq "R" && $type eq "STY"){
		if($rsty{$src}){
			print STDERR "ERROR: $code-$type duplicate \n$. : $_\nat line $. $src_data\n";
			exit 1;
		}
		else{$rsty{$src}=$data;}

	}
## 	elsif($code eq "R" && $type eq "SOS"){
## 		if($rsos{$src}){
## 			print STDERR "ERROR: $code-$type duplicate \n$. : $_\nat line $. $src_data\n";
## 			exit 1;
## 		}
## 		else{$rsos{$src}=$data}
##	}
	elsif($code eq "R" && $type eq "SSN"){
		if($rssn{$src}){
			print STDERR "ERROR: $code-$type duplicate \n$. : $_\nat line $. $src_data\n";
			exit 1;
		}
		else{$rssn{$src}=$data}
	}
	elsif($code eq "R" && $type eq "SY"){
	# having mult. SYs is legal
		print STDERR "Read: $src : $data\n";
		push(@{$R_HoA{$src}},$data);

 	}
	
	elsif($code eq "R" && $type eq "HT"){
		if($rht{$src}){
			print STDERR "ERROR: $code-$type duplicate \n$. : $_\nat line $. $src_data\n";
			exit 1;
		}
		else{$rht{$src}=$data}
	}
## 	}
	elsif($code eq "V" && $type eq "SY"){
		## mult SYs is legal
		push(@{$V_HoA{$src}},$data);
	}
	else{
		print STDERR "ERROR: \"$code-$type\" Not allowed. line $.\n$_\nin \"$src_data\"\n";
		exit 1;
	}
}	# end of while(<DATA>)
# print STDERR "END OF DATA FILE\n\n";
}
	else{
		print STDERR "No src_data file found\n";
		print STDERR "No SY, HT, or SSN created\n";
	}	# end of if(-e src_data)

# sources.src:
#  1 - source name
#  2 - low source
#  3 - restriction level
#  4 - normalized source
#  5 - stripped source
#  6 - version
#  7 - source family
#  8 - official name
# others are unused

# read sources.src again to process all the bits
seek(SOURCE,0,0);
while(<SOURCE>){
	next if(/^#/);
	chomp;
	($src_name,$low_src,$rlev,$norm_src,$str_src,$ver,$src_fam,$off_name,$nlm,$acq,$con,$lic,$inv,$contype,$url,$lang)=split(/\|/);
	next unless($src_name eq $norm_src);
	next if(/^\s*$/);
	unless($top_src){ $top_src = $src_name}
	$cnt++;
	# print STDERR "$cnt : $src_name\n";
	# done
	# CLASSES_ATOMS.SRC
	if($root){	# root is set if script was called with option 'n'
		$c_str = "$said|SRC|SRC/RPT|V-$str_src|N|Y|N|$off_name|N||||ENG||";
		$said_rpt = $said;
		# print STDERR "$c_str\n";
		print CLASS "$c_str\n";
		$said++;
		$rpt++;
		$c_str = "$said|SRC|SRC/RAB|V-$str_src|N|Y|N|$str_src|N||||ENG||";
		$said_rab = $said;
		print CLASS "$c_str\n";
		# print STDERR "$c_str\n";
		$said++;
		$rab++;
		## SSN (for Root)
		if($rssn{$src_name}){
			$c_str = "$said|SRC|SRC/SSN|V-$str_src|N|Y|N|$rssn{$src_name}|N||||ENG||";
			print CLASS "$c_str\n";
			$merge_str = "$said_rpt|SY|$said|SRC||N|N|$str_src-SRC|SRC_ATOM_ID||SRC_ATOM_ID||";
			print MERGE "$merge_str\n";
			$said++;
			$rssn++;
		}
		else{
			print STDERR "ERROR: SSN (Short Source Name) is required for ROOT of $src_name in $src_data\n";
			exit 1;
		}
		## RHT
		if($rht{$src_name}){
			$c_str = "$said|SRC|SRC/RHT|V-$str_src|N|Y|N|$rht{$src_name}|N||||ENG||";
			print CLASS "$c_str\n";
			$merge_str = "$said_rpt|SY|$said|SRC||N|N|$str_src-SRC|SRC_ATOM_ID||SRC_ATOM_ID||";
			print MERGE "$merge_str\n";
			$said++;
			$rht++;
		}
		## RSY (zero or more)
		for $i (0 .. ($#{$R_HoA{$src_name}})){
			$str = $R_HoA{$src_name}[$i];
			$c_str = "$said|SRC|SRC/RSY|V-$src_name|N|Y|N|$str|N||||ENG||";
			print CLASS "$c_str\n";
			print STDERR "$c_str\n";
			$merge_str = "$said_rpt|SY|$said|SRC||N|N|$str_src-SRC|SRC_ATOM_ID||SRC_ATOM_ID||";
			print MERGE "$merge_str\n";

			$said++;
			$rsy++;
		}
		

	}	# end of if($root)

	## VERSIONED Atoms
	$c_str = "$said|SRC|SRC/VPT|V-$src_name|N|Y|N|$off_name, $ver|N||||ENG||";
	$said_vpt = $said;
	print CLASS "$c_str\n";
	# print STDERR "$c_str\n";
	$said++;
	$vpt++;
	$c_str = "$said|SRC|SRC/VAB|V-$src_name|N|Y|N|$src_name|N||||ENG||";
	$said_vab = $said;
	print CLASS "$c_str\n";
	# print STDERR "$c_str\n";
	$said++;
	$vab++;
	# VSY (zero or more)
	for $i (0 .. ($#{$V_HoA{$src_name}})){
		$str = $V_HoA{$src_name}[$i];
		push(@vsy, "$str\n");
		$c_str = "$said|SRC|SRC/VSY|V-$src_name|N|Y|N|$str|N||||ENG||";
		print CLASS "$c_str\n";
		$merge_str = "$said_vpt|SY|$said|SRC||N|N|$str_src-SRC|SRC_ATOM_ID||SRC_ATOM_ID||";
		print MERGE "$merge_str\n";

		$said++;
		$vsy++;
	}
# 	if($vsy{$src_name}){
# 		$c_str = "$said|SRC|SRC/VSY|V-$src_name|N|Y|N|$vsy{$src_name}|N||||ENG||";
# 		print CLASS "$c_str\n";
# 		$said_vsy = $said;
# 		$said++;
# 		$vsy++;
# 		$merge_str = "$said_vpt|SY|$said_vsy|SRC||N|N|$top_src-SRC|SRC_ATOM_ID||SRC_ATOM_ID||";
# 		print MERGE "$merge_str\n";
# 
# 	}

	# done
	# ATTRIBUTES.SRC
	if($root){
		$md5 = md5_hex("Intellectual Product");
		$attr_str = "$at_lncnt|$said_rpt|C|SEMANTIC_TYPE|Intellectual Product|SRC|R|Y|N|N|SRC_ATOM_ID|||$md5|";
		print ATTR "$attr_str\n";
		$at_lncnt++;
	}
	# $md5 = md5_hex($vsos{$src_name});	
	# $attr_str = "$at_lncnt|$said_vpt|S|SOS|$vsos{$src_name}|SRC|R|Y|N|N|SRC_ATOM_ID|||$md5|";
	# print ATTR "$attr_str\n";
	# $at_lncnt++;
	$md5 = md5_hex("Intellectual Product");
	$attr_str = "$at_lncnt|$said_vpt|C|SEMANTIC_TYPE|Intellectual Product|SRC|R|Y|N|N|SRC_ATOM_ID|||$md5|";
	print ATTR "$attr_str\n";
	$at_lncnt++;

	# RELATIONSHIPS.SRC
	if($root){
		# rel between the Root concept and the UMLS Metathesaurus
		$rel_str = "$rel_lncnt|S|V-MTH|RT||V-$str_src|SRC|SRC|R|Y|N|N|CODE_TERMGROUP|SRC/RPT|CODE_TERMGROUP|SRC/RPT|||";
		print REL "$rel_str\n";
		$rel_lncnt++;
	}
		
	$rel_str = "$rel_lncnt|S|V-$src_name|BT|has_version|V-$str_src|SRC|SRC|R|Y|N|N|CODE_TERMGROUP|SRC/VPT|CODE_TERMGROUP|SRC/RPT|||";
	print REL "$rel_str\n";
	$rel_lncnt++;
	# 'translation_of' rel is between the ROOT atoms 
	if($trans){
		$str_src =~ /(\w*)(.{3})/;
		$eng_vcode = "V-".$1;

		$rel_str = "$rel_lncnt|S|$eng_vcode|RT|translation_of|V-$str_src|SRC|SRC|R|Y|N|N|CODE_TERMGROUP|SRC/RPT|CODE_TERMGROUP|SRC/RPT|||";
		$rel_lncnt++;
		print REL "$rel_str\n";
	}

	# MERGEFACTS.SRC
	if($root){
		$merge_str = "$said_rpt|SY|$said_rab|SRC||N|N|$str_src-SRC|SRC_ATOM_ID||SRC_ATOM_ID||";
	print MERGE "$merge_str\n";
	}	# end of if($root)

	$merge_str = "$said_vpt|SY|$said_vab|SRC||N|N|$str_src-SRC|SRC_ATOM_ID||SRC_ATOM_ID||";
	print MERGE "$merge_str\n";

	if($vsy{$src_name}){
		$merge_str = "$said_vab|SY|$said_vsy|SRC||N|N|$str_src-SRC|SRC_ATOM_ID||SRC_ATOM_ID||";
		print MERGE "$merge_str\n";
		$vsy++;
	}

	# print SUMMARY
	if($said_vpt && $said_vab){
print <<EOH;

Source - $src_name
EOH

	# print the root stuff only once, the first time through
	if(($root)&&($root_summ == 0)){
print <<EOR;
RPT: $off_name
RAB: $str_src
SSN: $rssn{$src_name}
RSY: $rsy_str
RHT: $rht{$src_name}
EOR
	$root_summ++;
	}
	print <<EOS;
VPT - SAID: $said_vpt - $off_name, $ver
VAB - SAID: $said_vab - $src_name
Version: $ver
Official Name: $off_name

EOS
	print "\n\n";

	}	$said_vpt = $said_vab = 0;
}	# end of while(<SOURCE>)

print  "Root Atoms\n";
print  "SRC/RPT $rpt\n";
print  "SRC/RAB $rab\n";
print  "SRC/RHT $rht\n";
print  "SRC/RSY $rsy\n";
print  "SRC/SSN $rssn\n";
print  "\n";

print  "Versioned Atoms\n";
print  "SRC/VPT $vpt\n";
print  "SRC/VAB $vab\n";
print  "SRC/VSY $vsy\n";
print  "\n";

print  "Use files:\n";
print  "\t$class\n";
print  "\t$attr\n";
print  "\t$rel\n";
print  "\t$merge\n";
print  "\n";
print  "Start new atoms at: ";
print "$said";
print  "\n\n";

# not very useful after all
print STDERR $said;

sub print_usage{

print  <<EOT;

	usage: $0 -s said [-n -t]
	said is the starting SAID to use
	-n if new rather than update
	-t if this is a translation 
	-h for help
	
EOT
}

sub print_help{
print STDERR <<EOH;

  To use this script you will need the following files in this
  directory:

  'sources.src' - a standard sources.src file. If you are building
  root atoms you don't need to include a Root version of the source.
  SRCbuilder will handle that automatically.
	
  'src_data'	- a file with one record for each SY, SSN or HT atom 
  that you wish to make. PTs, ABs, STYs, etc. are made automatically.
  You don't need SSN and HT lines if you are building versioned atoms.

  Comments and blank lines are ignored.
  'R' coded items are ignored unless the '-n' flag is used.

  The file looks like this:
  Source_Name|Code|Type|Data|
  Source_Name - must match the source_name (field 1) in sources.src 
  Code        - V|R (Root or Versioned)
  Type        - SY|HT|
  Data        - String to be used
  
  examples:
  ---- src_data -------------------------------------------------------
  # SRC data for HCPCS
  HCPCS03|R|SSN|Healthcare Common Procedure Coding System|

  # feel free to use comments and blank lines to make the file
  # more readable
  HCPCS03|V|SY|Health Care Financing Administration Common Procedure 
  Coding System, 2003|
  ---- end of src_data -------------------------------------------------

  
  The script returns the next SAID to be used
  
  The script creates the files "class_src", "attr_src", "rel_src",
  and "merge_src".

  See the files 'SRCtemplate.csh' and 'SRCtemplate.pl' for examples
  of how to incorporate this script into an inversion script.

  Screen output can be redirect to a log file for later review.
  All error messages are directed to the console via STDERR
  For "quiet" operation redirect to /dev/null

EOH

}
