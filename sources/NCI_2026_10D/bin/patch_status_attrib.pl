#!/usr/bin/perl

#one time patch 
#in src/attributes.src, for SEMANTIC_TYPE change status from 'N' to 'R'
#for all except SRC atoms

use File::Copy;
use Digest::MD5 qw(md5_hex);

open (ATTRIB, "<../src/attributes.src") || die "can't open ATTRIB\n";
open (OUT, ">../test/attributes.src") || die "can't open OUT\n";

while(<ATTRIB>){
	chomp;
	($attr_id,$id,$lvl,$atn,$atv,$vsab,$status,$tbr,$rel,$suppr,$type,$qual,$atui,$hashcode)=split(/\|/);
	if($atn ne 'SEMANTIC_TYPE'){
			print OUT "$_\n";
	}	
	elsif($atn eq 'SEMANTIC_TYPE'){
		if($vsab eq 'SRC'){
			print OUT "$_\n";
		}
		else{
			print OUT "$attr_id|$id|$lvl|$atn|$atv|$vsab|R|$tbr|$rel|$suppr|$type|$qual|$atui|$hashcode|\n";
		}
	} 
}
close(ATTRIB);
