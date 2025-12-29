#!/usr/bin/perl
# print_contexts_meme4.pl
# 
# WAK 08/06/03
# this script takes a command line arg of the SAB
# in the form:
# print.contexts.pl ./path_to_file/whatever.all
# appends to the file 'attributes.src'
# uses the MEME3 format

#$ENV{"LANG"} = "en_US.UTF-8";
#$ENV{"LC_COLLATE"} = "C";

use open ":utf8";

# used to make MD5 hashes
use Digest::MD5 qw(md5_hex);
use Encode qw(encode_utf8);

#used to get the command line options
use Getopt::Std;

# valid options are 's & f'
getopts('hf:s:', \%opts);

$file=$opts{'f'};
$SAB=$opts{'s'};

use File::Copy;

if($opts{'h'}){ &print_help; exit}

unless($opts{'s'} && $opts{'f'}){
	&print_help;
	exit;
}

print "\n\t.all file: $file\n\t      SAB: $SAB\n\n";

$attrib = '../src/attributes.src';
#$attrib = 'attributes.src';
#$attrib = 'attributes.test';

# does attributes.src exist?
if(-e $attrib){
	print "\tFound '$attrib'\n"; 
	# get last 'source_attribute_id' from attributes.src
	$lastline = `tail -1 ../src/attributes.src`;
	die "Attempt to read $attrib exited funny" if($?);
	($id) = split(/\|/,$lastline);
	if($id =~ /\D/ || $id !~ /\d/){
		print "Whoops, last id number [$id] is not a valid number in ../src/attributes.src\n";
		print "Are you sure you've got a correct MEME3 file?\n\n "; 
		exit;
	}
	print "\n\n\tCopying old '$attrib' to /var/tmp\n";
	copy("$attrib", "/var/tmp/attributes.src") or die "copy failed $!";
	#copy("$attrib", "/var/tmp/$attrib") or die "copy failed $!";
	$id++;
}
else{
	print "\tNo '$attrib' file found\n";
	print "\tCreating a new '$attrib'\n";
	`touch $attrib`;
	die "Attempt to 'touch' $attrib exited funny" if($?);
	$id = 1;
}

print "\tStarting numbering at: $id\n";

open (IN,"<$file") or die "can't open $file, $!";
binmode(IN, ":utf8");
open (OUT, ">>$attrib") or die "can't open attribute file";
binmode(OUT, ":utf8");

print "\tAppending data from $file to $attrib\n\n";

while (<IN>){
	chomp;
	@fields=split(/\|/);
	$att_val = "$fields[1]\t$fields[2]\t$fields[3]";
	$md5 = md5_hex(encode_utf8($att_val));
	print OUT "$id|$fields[0]|S|CONTEXT|$att_val|$SAB|R|n|N|N|SRC_ATOM_ID|||$md5|\n";
	$id++;
}

close IN;
close OUT;

exit;


sub print_help{
print <<EOT;
   
  usage: $0 -s SAB -f path/to/.allfile
  
             *** MEME3 format ***

  Run this from the directory that holds ../src/attributes.src

  the .all file is appended to the attributes file
  a copy of which is saved in /var/tmp


EOT

}
