#!/usr/bin/perl

#remove duplicate lines in *TREF files 

open (MRCONSO, "<../tmp/MRCONSO.TREF.tmp") || die "can't open MRCONSO\n";
open (OUT, ">../orig/MRCONSO.TREF") || die "can't open OUT\n";

while (<MRCONSO>){
	chomp;
	($aui,$str,$cui,$dui,$tg,$sourcecode)=split(/\|/);
	$sourcecode=~s/caDSR//;

	if(($tg=~/NCI/) && ($sourcecode eq 'TCGA')){ #NCI atoms use CUI not sourcecode for the code
		$sourcecode=~s/TCGA//;
	}
	if($str ne ''){
		if($hash{"$aui|$str|$cui|$dui|$tg|$sourcecode"}){  #duplicate entry, do not process
		}
		else{
			print OUT "$_\n";
			$hash{"$aui|$str|$cui|$dui|$tg|$sourcecode"}++;
		}
	}
	else{
	}
}
close(MRCONSO);

open (MRREL, "<../tmp/MRREL.TREF.tmp") || die "can't open MRREL\n";
open (OUT, ">../orig/MRREL.TREF") || die "can't open OUT\n";

while (<MRREL>){
    chomp;
    ($rui,$id1,$type1,$rsab,$rel,$rela,$id2,$type2)=split(/\|/);
	    if($id1 ne ''){
			if($hash{$_}){  #duplicate entry, do not process
	        }
	        else{
	            print OUT "$_\n";
	            $hash{$_}++;
	        }
	    }
	    else{
	    }
}
close(MRREL);

open (MRSAT, "<../tmp/MRSAT.TREF.tmp") || die "can't open MRSAT\n";
open (OUT, ">../orig/MRSAT.TREF") || die "can't open OUT\n";

while (<MRSAT>){
    chomp;
    ($atui,$id,$type,$atn,$atv)=split(/\|/);
	    if($id ne ''){
			if($hash{$_}){  #duplicate entry, do not process
	        }
	        else{
	            print OUT "$_\n";
	            $hash{$_}++;
	        }
	    }
	    else{
	    }
}
close(MRSAT);
