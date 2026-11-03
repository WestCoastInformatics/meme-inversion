#!/usr/bin/perl

#one time patch 
#change source of definitions from 'NCI-DEFCURATOR' to 'NCI' and insert

use File::Copy;
use Digest::MD5 qw(md5_hex);

$attr_line = `tail -1 ../src/attributes.src`;
if($?){ warn "system call failed"; exit 1}
$attr_line =~ /^(\d*)\|/;
$attr_id = $1;

open (DEF, "<../tmp/nci-defcurator.txt") || die "can't open DEF\n";
open (OUT, ">../src/defcurator_defs.txt") || die "can't open OUT\n";

while(<DEF>){
	chomp;
	($file,$pcode,$def)=split(/\|/);
	($label,$code)=split(/\:/, $file);
    $attr_id++;
	$hashcode = md5_hex($def);
	print OUT "$attr_id|$code|S|DEFINITION|$def|NCI_2017_06D|R|Y|N|N|SOURCE_CUI|NCI_2017_06D||$hashcode|\n";
} 
close(DEF);
