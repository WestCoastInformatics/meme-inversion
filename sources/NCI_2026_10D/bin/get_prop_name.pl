#!/usr/bin/perl

#convert UTF-8 to ascii

open (OWL, "<../tmp/nci_properties.tmp") || die "can't open OWL\n";
open (OUT, ">../tmp/nci_properties2.tmp") || die "can't open OUT\n";

while (<OWL>){
	chomp;
	($code,$atn,$atv)=split(/\|/);
	$qual = "";
	next  if ($atn eq "RELATIONSHIPGROUP");
	next if ($atn eq "OID");
	if ($atn eq "DEFINITION"){
		if (/<def-definition>.*<\/def-definition>/){
			$atv=$&;
                        $atv=~s/<def-definition>//;
                        $atv=~s/<\/def-definition>//;
			$atv=~s/\&amp;/&/g;
			$atv=~s/\&apos;/'/g;
			$atv=~s/\&lt;/</g;
			$atv=~s/\&gt;/>/g;
			$atv=~s/\&quot;/"/g;
			$atv=~s/\&amp;/&/g;
			$atv=~s/\&#8217;/'/g;
			$atv=~s/\&#176;/ degrees/g;
			$atv=~s/\&#39;/'/g;
		}
		if (/<def-source>.*<\/def-source>/){
                        $qual=$&;
                        $qual=~s/<def-source>//;
                        $qual=~s/<\/def-source>//;
                        $qual="Definition_Source\\".$qual;
		}	
		if (/<attr>.*<\/attr>/){ 
                        $attr=$&;
                        $attr=~s/<attr>//;
                        $attr=~s/<\/attr>/)/;
                        $qual=$qual."\\Definition_Attribution\\(".$attr if ($attr ne "");
		}
	}
	if ($atn eq "ALT_DEFINITION"){
		if (/<def-definition>.*<\/def-definition>/){
			$atv=$&;
			$atv=~s/<def-definition>//;
			$atv=~s/<\/def-definition>//;
			$atv=~s/\&amp;/&/g;
			$atv=~s/\&lt;/</g;
			$atv=~s/\&gt;/>/g;
			$atv=~s/\&apos;/'/g;
			$atv=~s/\&quot;/"/g;
			$atv=~s/\&amp;/&/g;
			$atv=~s/\&#8217;/'/g;
			$atv=~s/\&#176;/ degrees/g;
			$atv=~s/\&#39;/'/g;
		}
		if (/<def-source>.*<\/def-source>/){
			$qual=$&;
			$qual=~s/<def-source>//;
			$qual=~s/<\/def-source>//;
			$qual="Definition_Source\\".$qual;
		}
		if (/<attr>.*<\/attr>/){ 
			$attr=$&;
			$attr=~s/<attr>//;
			$attr=~s/<\/attr>/)/;
			$qual=$qual."\\Definition_Attribution\\(".$attr if ($attr ne "");
		}
	}
	if ($atn eq "GO_Annotation"){
		if (/<go-term>.*<\/go-term>/)
			{
			$atv=$&;
			$atv=~s/<go-term>//;
			$atv=~s/<\/go-term>//;
			$atv=~s/\&#39;/'/g;

			}
		if (/<go-id>.*<\/go-id>/)
			{
			$qual=$&;
			$qual=~s/<go-id>//;
			$qual=~s/<\/go-id>//;
			$qual="GO_ID\\".$qual;
			}
		if (/<go-source>.*<\/go-source>/)
			{
			$qual2=$&;
			$qual2=~s/<go-source>//;
			$qual2=~s/<\/go-source>//;
			$qual=$qual."\\GO_Source\\".$qual2;
			}
		if (/<go-evi>.*<\/go-evi>/)
			{
			$qual3=$&;
			$qual3=~s/<go-evi>//;
			$qual3=~s/<\/go-evi>//;
			$qual=$qual."\\GO_Evidence\\".$qual3;
			}
		if (/<source-date>.*<\/source-date>/)
			{
			$qual4=$&;
			$qual4=~s/<source-date>//;
			$qual4=~s/<\/source-date>//;
			$qual=$qual."\\GO_Source_Date\\".$qual4;
			}
		}
	if ($code ne ''){
		print OUT "$code|$atn|$atv|$qual\n";
	}
	else{
		print "ERROR: no code: $code|$atv|\n";
	}
}
close(OWL);

# Concept_Status
# Concept_Status  384
# DesignNote      1
# GO_Annotation   6344
# IND_Code        698
# Split_From      1

#ABCB1_wt_Allele|GO_Annotation|ATP-binding cassette (ABC) transporter activity|GO_ID\GO:0004009\GO_Source\CGAP\GO_Evidence\TAS\GO_Source_Date\29-SEP-2003
#ABCB1_wt_Allele|GO_Annotation|drug resistance|GO_ID\GO:0009315\GO_Source\CGAP\GO_Evidence\TAS\GO_Source_Date\29-SEP-2003
#cbioapp513.nci.nih.gov:/d3/inv/sources/NCI2008_09D/export-tref-compare:meme% grep GO_Ann owl_properties.txt | head -3
#ABCB1_wt_Allele|GO_Annotation|<go-id>GO:0004009</go-id><go-term>ATP-binding cassette (ABC) transporter activity</go-term><go-evi>TAS</go-evi><go-source>CGAP</go-source><source-date>29-SEP-2003</source-date>|
#
