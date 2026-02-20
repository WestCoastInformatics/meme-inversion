#!/site/bin/perl

#validate external codes (e.g., ICD10CM, ICD9CM, MDR) used in the P395 property (target code)  
#update source filename and MRCONSO directory

open (MRCONSO, "</meme_archive/mr/current/201908/META/MRCONSO.RRF") || die "can't open MRCONSO\n";

while(<MRCONSO>){
	chomp;
	($cui,$lat,$ts,$lui,$stt,$sui,$ispref,$aui,$saui,$scui,$sdui,$sab,$tty,$code,$str,$srl)=split(/\|/);
	$hash{$code}++;
}
close(MRCONSO);

open (CLASS, "</meme_work/inv/sources/NCI_2019_09E/orig/fromprovider/classDeclaration-20190930.txt") || die "can't open CLASS\n";

while(<CLASS>){
    chomp;
    ($cui,$property,$value,$qual1,$val1,$qual2,$val2,$qual3,$val3,$qual4,$val4)=split(/\|/);
	if($val3 ne ''){
		if($hash{$val3}){		#valid code
		}
		else{
			print "Error: invalid P395/target-code value: $val3|$val4\n";
    	}
	}
	else{
	}
}
close(CLASS);
