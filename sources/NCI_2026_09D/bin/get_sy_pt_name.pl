#!/usr/bin/perl

#change UTF-8 to ascii

open (OWL, "<../tmp/nci_sy_pt_properties.tmp") || die "can't open OWL\n";
open (OUT, ">../tmp/nci_sy_pt_properties2.tmp") || die "can't open OUT\n";

while (<OWL>){
	chomp;
	($str,$cui,$sabtty,$code)=split(/\|/);
	$str=~s/\&amp;/&/g;
	$str=~s/\&lt;/</g;
	$str=~s/\&gt;/>/g;
	$str=~s/\&quot;/"/g;
	$str=~s/\&apos;/'/g;
	$str=~s/\&#8217;/'/g;
	$str=~s/\&#176;/ degrees/g;
	$str=~s/\&#39;/'/g;

	if($sabtty=~/(MedDRA)(...)/){
		$sab=$1;
		$tty=$2;
	}
	elsif($sabtty=~/(GENC)(...)/){
		$sab=$1;
		$tty=$2;
	}
	elsif($sabtty=~/(...........)(..)/){
		$sab=$1;
		$tty=$2;
	}
	elsif($sabtty=~/(.........)(..)/){
		$sab=$1;
		$tty=$2;
	}
	elsif($sabtty=~/(........)(..)/){
		$sab=$1;
		$tty=$2;
	}
	elsif($sabtty=~/(.......)(..)/){
		$sab=$1;
		$tty=$2;
	}
	elsif($sabtty=~/(.....)(..)/){
		$sab=$1;
		$tty=$2;
	}
	elsif($sabtty=~/(NCI)(...)/){
		$sab=$1;
		$tty=$2;
	}
	elsif($sabtty=~/(....)(..)/){
		$sab=$1;
		$tty=$2;
	}
	elsif($sabtty=~/(...)(...)/){
		$sab=$1;
		$tty=$2;
	}
	elsif($sabtty=~/(...)(..)/){
		$sab=$1;
		$tty=$2;
        	if(($sab eq 'NCI') && ($tty eq 'PT')){
			print OUT "$cui|Preferred_Name|$str|\n";
			next;
        	}
	}
	if(($sab eq 'NCI') && ($tty ne 'PT')){
		if($code ne ''){
			print OUT "$cui|FULL_SYN|$str|Syn_Source\\$sab\\Syn_Term_Type\\$tty\\Syn_Source_Code\\$code\n";
		}
		if($code eq ''){
			print OUT "$cui|FULL_SYN|$str|Syn_Source\\$sab\\Syn_Term_Type\\$tty\n";
		}
	}
	elsif($sab ne 'NCI'){
		if(($sab =~ /SEER/) && ($str eq 'District of Columbia')){
			#do nothing b/c there is a matching NCI/SY atom
		}
		elsif(($sab =~ /SEER/) && ($code ne '')){
			print OUT "$cui|FULL_SYN|$str|Syn_Source\\$sab\\Syn_Term_Type\\$tty\\Syn_Source_Code\\$cui\n";
		}
		elsif($code ne ''){
			print OUT "$cui|FULL_SYN|$str|Syn_Source\\$sab\\Syn_Term_Type\\$tty\\Syn_Source_Code\\$code\n";
		}
		elsif($code eq ''){
			print OUT "$cui|FULL_SYN|$str|Syn_Source\\$sab\\Syn_Term_Type\\$tty\n";
		}
	}
}
close(OWL);
