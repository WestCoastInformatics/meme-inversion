#!/usr/bin/perl
# %W%	    %G%
# QA for MEME3 .src files
#
#### NEEDS
#
# - make a set of check files to check that all tests work. bad & good
# - fix rel checks
# - add check for SAID. if SAID used in rel, merge & attrib, they should
#	 be checked against classes. Add. there may be SAIDs from other sources.
#	 can we check against termgroups file and report what sources?
# - add new ref. check
# - state file that holds the status of various conditions in the QA process
# - both read from & written to, provides a place of the source
#	 inverter to record comments on various issues
# - script to generate a blank template (or template plus current state?)
# - 0 & non 0 results are tracked
# - dev. simple prototype to test/demo the concept.
# - add state section to QA_FILE at top
# - looks like this?
#
#Test#|T_name |Res	|Comments
#	       1|Dup_Term|11234|BLARG02 allows for duplicate terms

# For Attributes:
# Contexts and lexical tags should be tbr 'n'
# Semantic Types should be Concept level
#
# For relationships:
# SFO/LFO should be tbr 'n'
# Source level rels never status N
# source-level relas can now be created outside of the 'official list'
# should show up as a warning but not an error
#
# check for the existance of the files termgroups.src and sources.src
#
#
# Subroutine count_bad_nts, line 40, only takes into account NT although it
# reports outcome as 'NT/BT Duplicates'.	Also, does not take in account
# rela field so valid relationships being reported as dups.
# On large files it quits early w/ mesg "Not enough space"
# when trying to cat the 2 tmp files and then rm the tmp file
# uses too much memory with hashes left in memory? forces
# the system to page out? and uses up swap space? (hmmm, then
# why does the file system fail on 'cat'?

# some file tests are inefficient and should be re-written


# see error_check() in QA_scan.pm

# Meta Year Specific Stuff
# 1. Semantic Types are checked against a file in METAXX by the
#	subroutine valid_stys()
#	see the file METAXX/valid.sty for location information
#
# 2. Relas are checked against a file in META00
# 	/lti10f/META00/valid.relas.99
#	this is done in get_relas() in ./perl/QA_Utilities.pm

# set autoflush (turn off block buffering for file writes)
$| = 1;

#look in this dir for library (.pm) files
use lib "$ENV{INV_HOME}/lib";
use open ":utf8";

# uses copies of orig modules for dev.
## use QA4_util;	        #general and counting subroutines
## use QA4;		     #error-checking subroutines

require "QA4_util.pm";	        #general and counting subroutines
require "QA4.pm";		     #error-checking subroutines

#$ENV{"LANG"} = "en_US.UTF-8";
$ENV{"LC_COLLATE"} = "C";

#### Initialize GlobalLocal Variables
local(%said_class);
local($limit) = 10;	# Set a limit on output display of errors

# these files are created by the script 'make_new_valid_files.csh'
# do not edit the files by hand, re-create as needed
local($valid_langs = "$ENV{INV_HOME_OLD}/etc/valid_langs");
local($valid_stys = "$ENV{INV_HOME_OLD}/etc/valid_stys");
local($valid_relas = "$ENV{INV_HOME_OLD}/etc/valid_relas");
local($termids_file = "$ENV{INV_HOME_OLD}/etc/source_atom_ids");

use Getopt::Std;
use integer;

%option = ();	    #new hash for options

# pre-declare some vars
my(%obsolete_tty);
my($termgroups,$source);
local(%said_err, @tid);
%said_class = ();
%tid = ();

# f - specify a file to check
# h - print help
# d - specify another dir
# n - use alternate file NCI termids file for IDs
# s - user supplied SAB
# t - suppress checking of TreePos.dat
# d, f, & s take an arg
getopts("hns:td:f:", \%option);	#get options

## &print_options();
## print "Exiting early for testing\n\n";
## exit;

if ($option{h}){	            #if option -h print README.QA and exit
	open (README, "<$ENV{INV_HOME}/etc/README.QA");
	while (<README>){print}
	exit(0);
 }

# set termids file for NCI sources
# NO NEED FOR THIS
#if($option{n}){
#	$termids_file = "/d1/nci/projects/mgmt/source_atom_ids";
#	$valid_relas = "/d1/nci/projects/valid_relas";
#}
print "Using VALID_RELAS: $valid_relas\n";
print "Using TERMIDs: $termids_file\n";

#print "Only checking $option{f}\n" if ($option{f});
#print "Only Error Checking\n" if ($option{e});
#print "Only Running Counts\n" if ($option{c});

$dir = $option{d} || ".";	    #Directory for src files is current one unless -d
$date = `date`;
$time = time;
#$src_dir = &getcurrdir();
$print_dir = `pwd`;
chomp($print_dir);

if($option{'s'}){	# user has provided the SAB
	$SAB++;
	$sab = $option{'s'};
}

#$login = getlogin || (getpwuid($<)) [0] || "Intruder!!";
#@user = getpwnam($login);

$info = `ls -l $dir/*.src`;	                          #get files info on src files
opendir(DIR, "$dir") || die "Can't open $dir : $!";

if ($option{f}){	# change output file names if -f
	#$LOG = "ERROR_LOG_$option{f}";
	#$LOG =~ s/\.src//;
	#$FI = "QA_FILE_$option{f}";
	$FI = "$dir/../etc/QA_FILE.$$.$time.tmp";
	$FI =~ s/\.src//;
	$SUMM = "$dir/../etc/QA_SUM.$$.$time.tmp";
	#$SUMM = "ERROR_SUMMARY_$option{f}";
	#$SUMM=~s/\.src//;
	$ERR = "ERROR_$option{f}";
	$ERR =~ s/\.src//;
	$out = "$dir/../etc/QA_FILE_$option{f}";
	$out =~ s/\.src//;
	$fflg = 1;	  # flag for per file vs. all files
 }
else {
	$FI = "$dir/../etc/QA_FILE.$$.$time.tmp";
	$SUMM = "$dir/../etc/QA_SUM.$$.$time.tmp";
	$ERR = "$dir/ERROR_LOG";
	$out = "$dir/QA_FILE";
 }

(open(SUMM, ">$SUMM") || die "Can't open ERROR_SUMMARY: $!") unless $option{c};
(open(ERROR,">$ERR") || die "Can't open ERROR_LOG: $!") unless $option{c};
(open(FILE, ">$FI") || die "Can't open QA_FILE: $!") unless $option{e};

$fh_summ = *SUMM;
$fh_err = *ERROR;
$fh_file = *FILE;

@dir_tmp = $option{f} || (grep /\.src$/, readdir(DIR)); #make array of a src file names
@dir_list = sort(@dir_tmp);

# add in source_atoms.dat if there is a /cxt dir
# it's assumed that there should be a treepos.dat (below) if
# there is a source_atoms.dat

if(-e "$dir/../cxt" && (!$option{t})){
	push(@dir_list, "$dir/../cxt/source_atoms.dat");
}

# makes an array of arrays from /u/umls/termids
# unless the 'process single file' flag is set
# $fflg is true if we are only checking one file
unless($fflg){
	&make_tid_AoA();

	# hash is '%said_class'
	# flag is set to tell subs that the hash of saids exists
	# don't need this if the only file is classes
	unless($file =~ /class/){
		$said_flg = &make_said_hash();	 # returns TRUE for success
	}
}

# print Report Header
 &print_header();

print FILE "\n\nDETAILED REPORT\n";

#if($option{b}){ goto START}

foreach $file (@dir_list){	 #for each file in the array do the following:
	next if($file=~/^QA/);	# otherwise files like QA_FILE_classes
	$ucfile = $file;		# get run as well
	$ucfile =~ tr/a-z/A-Z/;
	print FILE "\n$ucfile\n";
	#print "\nFile: $file \n";
	unless ($option{c}){ 		#unless only run counts
	 }
	next if($option{e}); 		#skip to next file if only error checking
	print "\n\nChecking: $file:\n";
	print SUMM "\n\n$file\n";

	if($file =~ /class/){
		#&ck_field_lens($file);
		#&error_check($file);
		&check_class($file);
		#&count_dups($file);
		&quick_char_count($file);
		#&checkfields($file);
		&tally("class", $file);
	 }

	elsif($file =~ /relat/){
		#&ck_field_lens($file);
		&check_rels($file);
		#&count_bad_nts($file);
		#&count_mult_rels($file);
		&quick_char_count($file);
		#&checkfields($file);
		&tally("rel", $file);
	 }

	elsif($file =~ /attr/){
		#&ck_field_lens($file);
		&check_attr($file);
		&quick_char_count($file);
		#&checkfields($file);
		&tally("attr", $file);
	 }

	elsif($file =~ /merge/){
		#&ck_field_lens($file);
		&quick_char_count($file);
		&check_merge($file);
		#&checkfields($file);
		print "***BAC1\n";
		&count_self_merge($file);
		print "***BAC2\n";
		&tally("merge", $file);
	 }
	elsif($file eq "sources.src"){
		&check_source($file);
		#&checkfields($file);
		++$sources;
	 }
	elsif($file eq "termgroups.src"){
		&check_termgroup($file);
		&checkfields($file);
		++$termgroups;
	 }
	elsif($file eq "contexts.src"){
		#print "\n\nChecking for contexts.src is turned off\n\n"
		print "\nChecking contexts.src\n\n";
		&check_contexts($file);
	 }

	elsif($file =~ /source_atoms.dat/){
		if(-e "$dir/../cxt/source_atoms.dat"){
			print "Checking $dir/../cxt/source_atoms.dat\n";
			&check_source_atoms("$dir/../cxt/source_atoms.dat");
			&checkfields("$dir/../cxt/source_atoms.dat");

			if(-e "$main::dir/../cxt/treepos.dat"){
				print "Checking $dir/../cxt/treepos.dat\n";
				&check_treepos("$dir/../cxt/treepos.dat");
				&checkfields("$dir/../cxt/treepos.dat");
			}
			else{
				print "No 'treepos.dat' file\n";
				print "You must fix this.\n";
				print FILE "No treepos.dat file, you need to fix this\n";
			}
		}
		else{
			print "NO source_atoms.dat file\n";
			print "Fix this and re-run\n";
			print FILE "NO source_atoms.dat file\n";
			print FILE "Fix this and re-run\n";
		}
}	# end of elseif($source_atoms.dat)

	else{
		print "$file wasn't checked\n";
		#&quick_char_count($file);
		#&error_check($file);
	 }

	#print "Finished Checking: $file...\n\n" if $option{p};

 }	# end of foreach $file(@dir)
unless($fflg){
	print "\nNo TERMGROUPS.SRC file found,\nYOU NEED TO FIX THIS!!!\n" unless $termgroups;}

unless($fflg){
	print "\nNo SOURCES.SRC file found,\nYOU NEED TO FIX THIS!!!\n" unless $sources;
	# check for a raw3 file and print a warning if the contexts.src file
	&ck4raw3();
}

$date = `date`;
print FILE "\tFinished at: $date\n";
	
close (SUMM);
close (FILE);
close (ERROR);

print "\n";
print "Done with file checks\n";
print "Making OUT file\n";
`cat $SUMM $FI > $out`;
print "$!\n" if($?);
print "Removing tmp files\n";
#print "SUMM: $SUMM	 \n\$FI: $FI\n";
`rm -f $SUMM $FI`;
print "$!\n" if($?);

sub print_header{
	$login = getlogin || (getpwuid($<)) [0] || "Intruder!!";
	@user = getpwnam($login);
	print "\n\nCreating QA Report on: $print_dir\n";
	print "For: $user[5]\n\n";
	print "This is MEME4 Format\n";
	print "Options Chosen:\n";
	#if($option{p}){ print "\tPrinting Progress Messages\n"}
	#if($option{c}){ print "\tCreating Only QA_FILE for output\n"}
	#if($option{e}){ print "\tCreating Only ERROR file\n"}
	if($option{f}){ print "\tChecking $option{f} only\n"}
	print "\n";
	print "Use \"-h\" to see Help Message\n\n";
	#print "See QA Report in $FI\n";
	print "See QA Report in $out\n";
	print "See Errors in $ERR\n";
	#print "See Error Summary	in $SUMM\n";
	#print "See Error Details in $LOG\n\n";
	print SUMM "\n\tQA Report on $print_dir\n";
	print SUMM "\tFor user: $user[5]\n";
	print SUMM "\tCreated on: $date\n";
	print SUMM "\nErrors are in $ERR\n\n";
	print SUMM "Dir Info :\n", $info;
	print SUMM "\n\nSUMMARY INFORMATION";
 }

sub print_options{
	my ($x);
	foreach $x (keys %option){
		print "$x ";
	}
	print "\n";
 }
