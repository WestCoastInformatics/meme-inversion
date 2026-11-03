#!/usr/bin/perl

# reads the properties file and check for NCI-GLOSS DEFs in concepts with no
# note that NCI-GLOSS DEFs are actually ALT_DEFs
# 
#     1 ALT_DEFINITION|CDISC
#   201 ALT_DEFINITION|CSP2000
#    26 ALT_DEFINITION|CSP2002
#   139 ALT_DEFINITION|CSP2003
#   748 ALT_DEFINITION|FDA
#     6 ALT_DEFINITION|ICDO3
#     1 ALT_DEFINITION|MCI
#   432 ALT_DEFINITION|MMHCC
#   827 ALT_DEFINITION|MSH2001
#     1 ALT_DEFINITION|MSH2002
#   463 ALT_DEFINITION|MSH2002_06_01
#  1140 ALT_DEFINITION|MSH2003_2003_05_12
#     1 ALT_DEFINITION|MSH2004_2003_12_12
#     1 ALT_DEFINITION|MTH
#     1 ALT_DEFINITION|NCI
#  2438 ALT_DEFINITION|NCI-GLOSS
#     1 ALT_DEFINITION|UMD2001
#     3 ALT_DEFINITION|UWDA142
#  25090 DEFINITION|NCI
#   244 LONG_DEFINITION|NCI

# DEFs also have in many cases, a Definition_Attribution value
# |Definition_Source\NCI\Definition_Attribution\http://www.geocities.com/HotSprings/9190/glossary.html


while (<>) {
	chomp;
	($cname,$pname,$pval,$qual)=split(/\|/);
	if ($pname eq "FULL_SYN") {
		$src = $tty = $src_code = '';
		# split the qualifier field on '\'
		@P = split(/\\/, $qual);
		# @P contains all fields in pairs
		# go through the array, jumping 2 elements instead of the std. 1
		for($i=0;$i<$#P;$i++,$i++){
			$qualifier = $P[$i];
			$value = $P[$i+1];
			# figure out what we've got
			# qualifiers aren't guaranteed to be in a predictable order
			SWITCH:{
				if($qualifier eq "Syn_Source"){$src = $value; last SWITCH}
				if($qualifier eq "Syn_Term_Type"){$tty = $value; last SWITCH}
				if($qualifier eq "Syn_Source_Code"){$src_code = $value; last SWITCH}

				# if we made this far, we don't know what this qualifier is
				print "Error: Unknown qualifier - $qualifier\n";
				print "$.:$_\n";
			}
		}
#		$str = "$cname|$pname|$pval|Syn_Term_Type\\$tty\\Syn_Source\\$src";
#		if($src_code){
#			$str .= "\\Syn_Source_Code\\$src_code";
#		}
#		print "$str\n";

		if ($src eq "NCI-GLOSS" && $tty eq "PT") {
			$nciglosspt{$cname}++;
			$nciglossall{$cname}++;
		}
		if ($src eq "NCI-GLOSS" && $tty eq "SY") {
			$nciglossall{$cname}++;
		}
	}
	if ($pname =~ /DEFINITION/) {
		($cname,$pname,$pval,$qual)=split(/\|/);
		($null,$def_src,$null,$def_attr) = split(/\\/,$qual);
		if ($def_src eq "NCI-GLOSS") {
			#print "DEF: $cname\n";
			#print "$_\n";
			push (@defnames, $cname);
		}
	}
}
#foreach $x (@defnames) {
#	unless($nciglosspt{$x}) {
#		print "$x\n";
#	}
#}

foreach $x (@defnames) {
 unless($nciglossall{$x}) {
	 print "$x\n";
	}
}



