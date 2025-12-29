#!/usr/bin/perl
#!/usr/bin/perl
#

# fields
# 1  = source_attribute_id
# 2  = id
# 3  = attribute_level
# 4  = attribute_name
# 5  = attribute_value
# 6  = source
# 7  = status
# 8  = tobereleased
# 9  = released
# 10 = suppressible
# 11 = id_type
# 12 = ed_qualifier
# 13 = source_atui
# 14 = hashcode

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package QaAttrs;

use Digest::MD5 qw(md5_hex);
use Encode qw(encode_utf8);
use FldMon;
use LineMon;
use iutl;
use CharCount;
{
  my ($_theLog, $_theCfg, $_OUT, $_EOUT);
  my ($VlVsabRef, $VlAtnRef, $temp, $cfgvsab);
  my ($VlAttatn, $VlSubatn);
 
  my ($xmpTo, $xmpFr, $xmp);
  my %mons=();
  my %lmons=();

  my %errCount = ();
  my %Errors = ();
  my %wrngCount=();
  my %Warnings=();
  my %infoCount=();
  my %Information=();

  my %attrAtui = ();

  my %xmap3Attr=();
  my %xmap6Attr=();
  my %xmapToAttr=();
  my %xmapFromAttr=();
  my %vptSaidsForStyCheck=();
  #my %mrdocatn=();
  

  my $pat5 = qr{^(LAB|TRD)};
  my $pat8 = qr{^E\-};
  #my $pat9 = qr{&[[:alnum:]]+;};
  my $pat9 =  qr{&\#?[[:alnum:]]+;};

  my $pat10 = qr{^(SRC_ATOM_ID|SRC_REL_ID|CUI|AUI|RUI)$};
  #my $pat11 = qr(\s{2,});
  my $pat11 = qr(^\s|\s\s|\s$);
  my $pat100 = qr{^E\-(.*)$};
  my $pat101 = qr{^(XMAP|XMAPTO|XMAPFROM|COMPONENTHISTORY|DEFINITION|NON_HUMAN|LEXICAL_TAG|SEMANTIC_TYPE|CONTEXT|MTH_MAPSETCOMPLEXITY|MTH_MAPFROMCOMPLEXITY|MTH_MAPTOCOMPLEXITY|MAPSETVSAB|MAPSETRSAB|FROMVSAB|FROMRSAB|TOVSAB|TORSAB|MAPSETVERSION|MTH_MAPFROMEXHAUSTIVE|MTH_MAPTOEXHAUSTIVE|MAPSETTYPE)$};


  # tests BEGIN tests BEGIN tests BEGIN tests BEGIN tests BEGIN
  my @IL=();

  sub setMsgCountHashes {
	# use info as the default.
	my $type = shift;
	if ($type eq 'error') {
	  return (\%errCount, \%Errors);
	} elsif ($type eq 'wrng') {
	  return (\%wrngCount, \%Warnings);
	} else {
	  return (\%infoCount, \%Information);
	}
  }

  sub nullFunc { return; }

  # ILM_0: field count check.
  my $subref_checkFldCount= \&nullFunc;
  sub make_checkFldCount {
	my ($valFldCount, $msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkFldCount = sub {
	  if ($valFldCount != @IL) {
		if ($$countHash{"VFieldCount"}++ < 10) {
		  my $l = @IL;
		  $l -= 2;
		  $$msgHash{"VFieldCount_$IL[1]"} = $l;
		}
	  }
	}
  }

  # ILM_1: Semantic_Type attribute level must be C
  my $subref_checkNonCLvlStys = \&nullFunc;
  sub make_checkNonCLvlStys {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkNonCLvlStys = sub {
	  if ($IL[3] ne 'C' && $$countHash{'VNonCLvlStys'}++ < 10) {
		$$msgHash{"VNonCLvlStys_$IL[1]"} = "$IL[1]|$IL[3]";
	  }
	}
  }

  # ILM_2: attribute level must be S
  my $subref_checkCLvlNonStys = \&nullFunc;
  sub make_checkCLvlNonStys {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkCLvlNonStys = sub {
	  if ($IL[3] ne 'S'  && $$countHash{'VCLvlNonStys'}++ < 10) {
		$$msgHash{"VCLvlNonStys_$IL[1]"} = "$IL[1]|$IL[6]|$IL[4]|$IL[3]";
	  }
	}
  }

  # ILM_3: CONTEXT attributes are can not be releasable
  my $subref_checkTbrYCxts = \&nullFunc;
  sub make_checkTbrYCxts {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkTbrYCxts = sub {
	  if (uc($IL[8]) ne 'N' && $$countHash{'VTbrYCxts'}++ < 10) {
		$$msgHash{"VTbrYCxts_$IL[1]"} = "@IL[1]|@IL[6]";
	  }
	}
  }

  # ILM_4: invalid tbr/lexical_tag/TRD (if releasable, must have TRD as val)
  my $subref_checkInvTbrLexTrd = \&nullFunc;
  sub make_checkInvTbrLexTrd {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvTbrLexTrd = sub {
	  if ($IL[4] eq 'LEXICAL_TAG'
		  && (($IL[5] !~ /$pat5/)
			  || (uc($IL[8]) ne 'N' && $IL[5] ne 'TRD')
			  || (uc($IL[8]) eq 'N' && $IL[5] eq 'TRD'))
		  && $$countHash{'VInvTbrLexTrd'}++ < 10) {
		$Errors{"VInvTbrLexTrd_$IL[1]"} = "$IL[8]|$IL[4]|$IL[5]";
	  }
	}
  }

  # ILM_5: S level attributes can not have N status
  my $subref_checkStsNLvlS = \&nullFunc;
  sub make_checkStsNLvlS {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkStsNLvlS = sub {
	  if ($IL[3] eq 'S' && uc($IL[7]) eq 'N'
		  && $$countHash{'VStsNLvlS'}++ < 10) {
		$$msgHash{"VStsNLvlS_$IL[1]"} = "@IL[1]|@IL[6]";
	  }
	}
  }

  # ILM_6: non unique ATUIs (only for non cxt attributes)
  my $subref_checkNonUniqueAtuis = \&nullFunc;
  sub make_checkNonUniqueAtuis {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkNonUniqueAtuis = sub {
	  my $atui = "@IL[6]|@IL[4]|@IL[13]|@IL[14]|@IL[2]|@IL[11]|@IL[12]";
	  if (defined($attrAtui{"$atui"})) {
		if ($$countHash{'VNonUniqueAtui'}++ < 10) {
		  my $tmp = $attrAtui{"$atui"};
		  $$msgHash{"VNonUniqueAtui_$IL[1]"} = "<$tmp>: $atui";
		}
	  } else {
		$attrAtui{"$atui"} = $IL[1];
	  }
	}
  }

  # ILM_7: Source should be like E-* for non SRC stys.
  my $subref_checkNonSrcStysNonESrc = \&nullFunc;
  sub make_checkNonSrcStysNonESrc {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkNonSrcStysNonESrc = sub {
	  if ($IL[6] ne 'SRC' && $IL[7] eq 'N' &&  ($IL[6] !~ /$pat8/)
		  && $$countHash{'VNonSrcStysNonESrc'}++ < 10) {
		$$msgHash{"VNonSrcStyNonESrc_$IL[1]"} = "$IL[7]|$IL[6]";
	  }
	}
  }

  # ILM_8: check for XML chars - $pat9 = qr(&[[:alnum:]]+);
  my $subref_checkXMLChars = \&nullFunc;
  sub make_checkXMLChars {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkXMLChars = sub {
	  if (@IL[5] =~ /$pat9/ && $$countHash{'VXMLChars'}++ < 10) {
		$$msgHash{"VXMLChars_$IL[1]"} = "$IL[6]|@IL[5]";
	  }
	}
  }

  # ILM_9: non null satui - warning.
  my $subref_checkNonNullSAtui = \&nullFunc;
  sub make_checkNonNullSAtui {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkNonNullSAtui = sub {
	  if (@IL[13] ne '' && $$countHash{'VNonNullSAtui'}++ < 10) {
		$$msgHash{"VNonNullSAtui_$IL[1]"} = "$IL[6]|$IL[1]|$IL[13]";
	  }
	}
  }

  # ILM_10: null rela for XMAP RN rels
  my $subref_checkNullRelaForXmapRN = \&nullFunc;
  sub make_checkNullRelaForXmapRN {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkNullRelaForXmapRN = sub {
	  if ($IL[4] eq 'XMAP') {
		my @tmp = split(/\~/, @IL[5], 4);
		if ($tmp[2] eq 'RN' && $tmp[3] eq ''
			&& $$countHash{'VNullRelaForXmapRN'}++ < 10) {
		  $$msgHash{"VNullRelaForXmapRN_$IL[1]"} = "$IL[6]|$IL[1]|$IL[5]";
		}
	  }
	}
  }

  # ILM_11: white space in non CONTEXT attributes
  my $subref_checkWSinAttrVal = \&nullFunc;
  sub make_checkWSinAttrVal {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkWSinAttrVal = sub {
	  if ($IL[4] ne 'CONTEXT') {
		if ($IL[5] =~/$pat11/
			&& $$countHash{'VWSinAttrVal'}++ < 10) {
		  $$msgHash{"VWSinAttrVal_$IL[1]"} = "$IL[4]|$IL[5]";
		}
	  }
	}
  }



 # ILM_12: Check Vsab for Semantic Types
  my $subref_checkSTYVsab = \&nullFunc;
  sub make_checkSTYVsab {
        my ($msgType) = @_;
        my ($countHash, $msgHash) = &setMsgCountHashes($msgType);
        
        $subref_checkSTYVsab = sub {
        
         my $tmpvsab = "E-$cfgvsab";
             if ($IL[4] eq 'SEMANTIC_TYPE') {
                 if ($IL[6] ne $tmpvsab && $IL[6] ne 'SRC'
                        && $$countHash{'checkSTYVsab'}++ < 10) {
                  $$msgHash{"checkSTYVsab_$IL[1]"} = "$IL[6]";
               }
          }
        }
  }



  # IFM_1: validate sgId, sgType, sgQual
  my $subref_checkInvSgIdTypeQual = \&nullFunc;
  sub make_checkInvSgIdTypeQual {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvSgIdTypeQual = sub {
	  my $temp;
	  if ($temp = SrcQa->InvalidSg($IL[2], $IL[11], $IL[12])
		  && $$countHash{"$temp"}++ < 10) {
		$$msgHash{"${temp}_$IL[1]"} = "$IL[2]|$IL[11]|$IL[12]";
	  }
	}
  }

  # IFM_2: validate ATN
  my $subref_checkInvAttrName = \&nullFunc;
  sub make_checkInvAttrName {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvAttrName = sub {
	  if ((!defined($$VlAtnRef{"$IL[4]"}))
		  && ($IL[4] !~ /$pat101/)
		  && ($$countHash{'VInvAttrName'}++ < 10)) {
		$$msgHash{"VInvAttrName_$IL[1]"} = "$IL[4]";
	  }
	}
  }

  # IFM_3: STY attribute value must be in etc/valid_stys
  my $subref_checkInvSTY = \&nullFunc;
  sub make_checkInvSTY {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvSTY = sub {
	  if ((iutl->validStyP($IL[5]) != 1) && $$countHash{'VInvSTY'}++ < 10) {
		$$msgHash{"VInvSTY_$IL[1]"} = "ST: sty: $IL[5]";
	  }
	}
  }

  # IFM_4: check for valid vsab -  $pat100 = qr(^E\-([.]*)};
  my $subref_checkInvVsab = \&nullFunc;
  sub make_checkInvVsab {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkInvVsab = sub {
	  if (!defined($$VlVsabRef{"$IL[6]"})) {
		if ($IL[4] eq 'SEMANTIC_TYPE' && $IL[6] =~ /$pat100/) {
		  if (!defined($$VlVsabRef{"$1"})) {
			if ($$countHash{'VInvVSab'}++ < 10) {
			  $$msgHash{"VInvVSab_$IL[1]"} = "$IL[6]";
			}
		  }
		} else {
		  if ($$countHash{'VInvVSab'}++ < 10) {
			$$msgHash{"VInvVSab_$IL[1]"} = "$IL[6]";
		  }
		}
	  }
	}
  }

  # IFM_5: check XMAP/TO/FROM attributes
  my $subref_checkXMAPAttrs = \&nullFunc;
  sub make_checkXMAPAttrs {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);
	my $key;

	$subref_checkXMAPAttrs = sub {
	  # XMAP without XMAPTO attr
	  foreach $key (keys (%xmap6Attr)) {
		if ((!defined($xmapToAttr{"$key"}))
			&& $$countHash{'VMissingXmap2XToAttr'}++ < 10) {
		  $$msgHash{"VMissingXmap2XToAttr_$key"} = $xmap6Attr{"$key"};
		}
	  }

	  # XMAP without XMAPFROM attr
	  foreach $key (keys (%xmap3Attr)) {
		if ((!defined($xmapFromAttr{"$key"}))
			&& $$countHash{'VMissingXmap2XFromAttr'}++ < 10) {
		  $$msgHash{"VMissingXmap2XFromAttr_$key"} = $xmap3Attr{"$key"};
		}
	  }

	  # XMAPTO without XMAP attr
	  foreach $key (keys (%xmapToAttr)) {
		if ((!defined($xmap6Attr{"$key"}))
			&& $$countHash{'VMissingXTo2XmapAttr'}++ < 10) {
		  $$msgHash{"VMissingXTo2XmapAttr_$key"} = $xmapToAttr{"$key"};
		}
	  }

	  # XMAPFROM without XMAP attr
	  foreach $key (keys (%xmapFromAttr)) {
		if ((!defined($xmap3Attr{"$key"}))
			&& $$countHash{'VMissingXFrom2XmapAttr'}++ < 10) {
		  $$msgHash{"VMissingXFrom2XmapAttr_$key"} = $xmapFromAttr{"$key"};
		}
	  }
	}
  }

  # IFM_6: All VPT atoms have STY of Intl Prod.
  my $subref_checkVPTAtomWithNoSty = \&nullFunc;
  sub make_checkVPTAtomWithNoSty {
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkVPTAtomWithNoSty = sub {
	  my $key;
	  foreach $key (keys (%vptSaidsForStyCheck)) {
		if ($$countHash{'VVPTAtomWithNoSTY'}++ < 10) {
		  $$msgHash{"VVPTAtomWithNoSTY_$key"}++;
		}
	  }
	}
  }

# IFM_7: Check if MD5 value matches the ATV
  my $subref_checkMD5 = \&nullFunc;
  sub make_checkMD5{
	my ($msgType) = @_;
	my ($countHash, $msgHash) = &setMsgCountHashes($msgType);

	$subref_checkMD5 = sub{
	  my $tmp1;
	  if ($IL[14] ne ''){
	  $tmp1 = md5_hex(encode_utf8("$IL[5]"));
	   if (($IL[14] ne $tmp1)
	    && $$countHash{'MD5MisMatch'}++ < 10){
		$$msgHash{"MD5MisMatch_$IL[1]"} = "$IL[2]|$IL[14]|$tmp1";
	    }
	  }
    }
  }


  # tests END tests END tests END tests END tests END tests END tests END


  sub init {
	my ($self, $log, $cfg) = @_;
	$_theLog = $log;
	$_theCfg = $cfg;
	$_OUT = $$_theCfg->getEle('ofhReport');
	$_EOUT = $$_theCfg->getEle('errhReport');
        $cfgvsab = $$_theCfg->getEle('VSAB');
  }

  sub setValidRefs {
	my ($self, $l_valids) = @_;

	$VlAtnRef = $$l_valids{'Atn'};
	$VlVsabRef = $$l_valids{'Vsab'};
        
        $VlAttatn = $$l_valids{'attn'};
        $VlSubatn = $$l_valids{'subatn'};
        
 
	# here remember the VPT saids that must have a SEMANTIC_TYPE attr of
	# Intellectual Product. This is for Filemon 22.
	my ($key, $val);
	while (($key, $val) = each (%{$$l_valids{'SrcAtoms'}})) {
	  if ($key =~ /SRC\/VPT/) {
		$vptSaidsForStyCheck{"$val"}++;
	  }
	}
  }

  sub crTest {
	my ($mStr, $num, $mkFn, $str) = @_;
	my ($type);
	if ($$_theCfg->getEle("$mStr.$num.enable", 0) eq '1') {
	  $type = $$_theCfg->getEle("$mStr.1.type", 'info');
	  &$mkFn($type);
	  $$_theLog->logInfo("Enabled check $mStr.$num \n\t($str)\n");
	} else {
	  $$_theLog->logInfo("** Not checking $mStr.$num \n\t($str)\n");
	}
  }

  sub new {
	my $class = shift;
	my $ref = {};
	my ($i, $fnum, $tHash, $temp, $temp1);

	my $lmStr = "IlLineMon.Attribute";
	my $fmStr = "IlFileMon.Attribute";

	## 1. create FieldMons
	$tHash = \%{$$_theCfg->getHashRef('FieldMon.Attribute')};
	foreach $i (sort keys (%{$tHash})) {
	  $fnum = $$_theCfg->getEle("FieldMon.Attribute.$i.fieldNum", '0');
	  if ($fnum != 0) {
		$mons{$fnum} = new FldMon('Attribute', $i);
	  } else {
		$$_theLog->logError("Encountered invalid".
							"FieldMon.Attribute.$i.fieldNum\n");
	  }
	}

	## 2. create LineMons
	$tHash = \%{$$_theCfg->getHashRef('LineMon.Attribute')};
	foreach $i (sort keys(%{$tHash})) {
	  $lmons{$i} = new LineMon('Attribute',$i);
	}

	## 3. read inline LineMons and create the check functions
	# ILM_0: field count
	if (($temp = $$_theCfg->getEle("$lmStr.0.enable", 0)) == 1) {
	  $temp = $$_theCfg->getEle("$lmStr.0.fieldCt", 14);
	  if ($temp != 0) {
		$temp += 2;
		$temp1 = $$_theCfg->getEle("lmStr.0.type", 'info');
		&make_checkFldCount($temp, $temp1);
	  }
	}

	&crTest($lmStr, 1, \&make_checkNonCLvlStys,
			" ILM_1: Semantic_Type attribute level must be C");

	&crTest($lmStr, 2, \&make_checkCLvlNonStys,
			" ILM_2: attribute level must be S");

	&crTest($lmStr, 3, \&make_checkTbrYCxts,
			"ILM_3: CONTEXT attributes can not be releasable");

	&crTest($lmStr, 4, \&make_checkInvTbrLexTrd,
			"ILM_4: invalid tbr/lexical_tag/TRD (if releasable, must "
			."have TRD as val)");

	&crTest($lmStr, 5, \&make_checkStsNLvlS,
			"ILM_5: S level attributes can not have N status");

	&crTest($lmStr, 6, \&make_checkNonUniqueAtuis,
			"ILM_6: non unique ATUIs (only for non cxt attributes)");

	&crTest($lmStr, 7, \&make_checkNonSrcStysNonESrc,
			"ILM_7: Source should be like E-* for non SRC stys.");

	&crTest($lmStr, 8, \&make_checkXMLChars,
			"ILM_8: check for XML chars - $pat9 = qr(&[[:alnum:]]+);");

	&crTest($lmStr, 9, \&make_checkNonNullSAtui,
			"ILM_9: non null satui - warning.");

	&crTest($lmStr, 10, \&make_checkNullRelaForXmapRN,
			"ILM_10: null rela for XMAP RN rels");

	&crTest($lmStr, 11, \&make_checkWSinAttrVal,
			"ILM_11: white space in non CONTEXT attributes");

        &crTest($lmStr, 12, \&make_checkSTYVsab,
                        "ILM_12: check vsab for sty's");


	## 4. read inline FileMons and create the check functions
	&crTest($fmStr, 1, \&make_checkInvSgIdTypeQual,
			"IFM_1: validate sgId, sgType, sgQual");

	&crTest($fmStr, 2, \&make_checkInvAttrName,
			"IFM_2: validate ATN");

	&crTest($fmStr, 3, \&make_checkInvSTY,
			"IFM_3: STY attribute value must be in etc/valid_stys");

	&crTest($fmStr, 4, \&make_checkInvVsab,
			"IFM_4: check for valid vsab -  $pat100 = qr(^E\-([.]*)};");

	&crTest($fmStr, 5, \&make_checkXMAPAttrs,
			"IFM_5: check XMAP/TO/FROM attributes");

	&crTest($fmStr, 6, \&make_checkVPTAtomWithNoSty,
			"IFM_6: All VPT atoms have STY of Intl Prod.");
    
    &crTest($fmStr, 7, \&make_checkMD5,
			"IFM_7: check if MD5 value of ATV matches the hashcode.");

	return bless ($ref, $class);
  }



  sub process {
	@IL = @_;
	#my ($self, $recId, $id, $lvl, $nm, $vl, $src, $sts, $tbr, $rlsd, $sup,
	#$idt, $idq, $atui, $hscd) = @_;
	my @tmparray = @_;
        my @tempfield;
        
	my ($key, $ign, $tmp, @tmp);
        #my ($DocKey, $key1, $key2);
     
	## do FieldMon Checks
	foreach $key (keys (%mons)) {
	  $mons{"$key"}->process($_[$key], $IL[1]);
	}

	## do LineMon Checks
	foreach $key (keys (%lmons)) {
	  $lmons{"$key"}->process(@tmparray[1..$#tmparray]);
	}

	## other cross field checks go here.
	# ILM_0: field count check.
	&$subref_checkFldCount();


	## SEMANTIC_TYPE attrs checks
	if ($IL[4] eq 'SEMANTIC_TYPE') {

	  # ILM_1: Semantic_Type attribute level must be C
	  &$subref_checkNonCLvlStys();

	  # ILM_7: Source should be like E-* for non SRC stys.
	  &$subref_checkNonSrcStysNonESrc();

	  # processing for FileMon 6.VPT atoms must have an STY of Intel Prod.
	  if ($IL[11] eq 'SRC_ATOM_ID' && $IL[5] eq 'Intellectual Product'
		  && defined($vptSaidsForStyCheck{"$IL[2]"})) {
		delete $vptSaidsForStyCheck{"$IL[2]"};
	  }

	  # IFM_3: STY attribute value must be in etc/valid_stys
	  &$subref_checkInvSTY();

	} else {
	  # ILM_2: attribute level must be S
	  &$subref_checkCLvlNonStys();
	}


	if ($_[4] eq 'CONTEXT') {
	  # ILM_3: CONTEXT attributes are can not be releasable
	  &$subref_checkTbrYCxts();
	} else {
	  # ILM_6: non unique ATUIs (only for non cxt attributes)
	  &$subref_checkNonUniqueAtuis();
	}


	# ILM_4: invalid tbr/lexical_tag/TRD  (if releasable, must have TRD as val)
	&$subref_checkInvTbrLexTrd();


	# ILM_5: S level attributes can not have N status
	&$subref_checkStsNLvlS();


	# ILM_8: check for XML chars - $pat9 = qr(&[[:alnum:]]+);
	&$subref_checkXMLChars();

	# ILM_9: non null satui
	&$subref_checkNonNullSAtui();

	# ILM_10: null rela for XMAP RN rels
	&$subref_checkNullRelaForXmapRN();

	# ILM_11: white space in non CONTEXT attributes
	&$subref_checkWSinAttrVal();
        
        # ILM_12: check vsab for STY's
        &$subref_checkSTYVsab();

	# IFM_1: validate sgId, sgType, sgQual
	&$subref_checkInvSgIdTypeQual();

	# IFM_2: validate ATN
	&$subref_checkInvAttrName();

    # IFM_7: Check MD5 Mismatch
    &$subref_checkMD5();
    
	# IFM_4: check for valid vsab -  $pat100 = qr(^E\-([.]*)};
	&$subref_checkInvVsab();


	# Collect xmap info for FileMon IFM_5.
	if ($_[4] eq 'XMAP') {
	  ($ign, $ign, $xmpTo, $ign, $ign, $xmpFr) = split(/\~/, $_[5], 7);
	  $xmap3Attr{"$_[2]|$xmpTo"} = $_[1];
	  $xmap6Attr{"$_[2]|$xmpFr"} = $_[1];
	} elsif ($_[4] eq 'XMAPTO') {
	  ($xmpTo) = split(/\~/, $_[5], 2);
	  $xmapToAttr{"$_[2]|$xmpTo"} = $_[1];
	} elsif ($_[4] eq 'XMAPFROM') {
	  ($xmpFr) = split(/\~/, $_[5], 2);
	  $xmapFromAttr{"$_[2]|$xmpFr"} = $_[1];
	}


	##### other checks not in the inv file. 
	## if type is SRC_ATOM_ID, id must be digits.
	unless(iutl->checkId($_[2], $_[11])) {
	  if ($errCount{'EBadSaidType'}++ < 10) {
		$Errors{"EBadSaidType_$_[1]"} = "id: $_[2], idt: $_[11]";
	  }
	}

	## SYNTACTIC_CATEGORY attributes must have atlevel of C and must be
	# unreleasable
	if ($_[4] eq 'SYNTACTIC_CATEGORY' && 
		($_[3] ne 'C' || $_[8] ne 'N')) {
	  if ($errCount{'badSaids'}++ < 10) {
		$Errors{"VBadSYNCAT_$_[1]"} = "lvl: $_[3], tbr: $_[8]";
	  }
	}

	## if the attribute name is SOS, then source can not be SRC.
	if ($_[4] eq 'SOS' && $_[6] eq 'SRC') {
	  if ($errCount{'badSosSrc'}++ < 10) {
		$Errors{"VBadSosSrc_$_[1]"} = "<SOS><SRC>";
	  }
	}
        
       ###check for tabs in lines
        if ($_[1] ne ''){
          if ($_[4] ne 'CONTEXT'){
        my $full_line  = "$_[1]|$_[2]|$_[3]|$_[4]|$_[5]|$_[6]|$_[7]|$_[8]|$_[9]_$[10]|$_[11]|$_[12]|$_[13]|$_[14]";
	 if ($full_line =~ /\t/){
	       if ($errCount{'tabsinfile'}++ < 10) {
                $Errors{"Vtabsinfile_$_[1]"} = "$_[5]";
		   }
		}
             }
          }
	      
        #check if sgqual is blank or not for SOURCE_ATOM_ID sgtype
       if ($_[11] eq "SRC_ATOM_ID"){
          if ($_[12] ne ''){
            if ($errCount{'Sgqualnotnull'}++ < 10) {
                $Errors{"Sgqualnotnull_$_[2]"} = "$_[11]|$_[12]";
                   }
                }
             }
  

        ## Remember the attribute name and subset_member hidden attributes
         if ($_[4] ne ''){
           $$VlAttatn{"$_[4]"}++;
            }
         
         if (($_[4] eq "SUBSET_MEMBER") 
              && ($_[5] =~ /\~/)){
          my  @tempfield = split(/~/, $_[5]);
          my  $subfield = @tempfield[1];
              
             $$VlSubatn{"$subfield"}++;  
             
              if (!defined($$VlAtnRef{"$subfield"})){
                if ($errCount{'InvSubAtn'}++ < 10){
                    $Errors{"No_ATN_IN_MRDOC_$_[1]"} = "$_[4]|$subfield";
                }
             }
       }

  }

  sub reportInfo {
	my $self = shift;
	my ($key, $ln, @vals);

	print $_OUT "Attributes: Information\n";

	foreach $key (sort {$a <=> $b} (keys (%mons))) {
	  $mons{"$key"}->reportInfo();
	}

	foreach $key (sort {$a <=> $b} (keys (%lmons))) {
	  $lmons{"$key"}->reportInfo();
	}

	my $ln = keys %infoCount;
	if ($ln > 0) {
	  print $_EOUT "  Info Counts: $ln\n";
	  # present other class specific ifnormation here
	  foreach $key (sort keys(%infoCount)) {
		print $_EOUT "\t$key = $infoCount{$key}\n";
	  }
	  print $_EOUT "\n\n  Info data:\n";
	  foreach $key (sort keys(%Information)) {
		print $_EOUT "\tINFO: $key => $Information{$key}\n";
	  }
	  print "\n\n";
	}
  }

  sub reportWarnings {
	my $self = shift;
	my ($key, $ln, @vals);
	print $_OUT "Attributes: Warnings\n";

	foreach $key (sort {$a <=> $b} (keys (%mons))) {
	  $mons{"$key"}->reportWarnings();
	}

	foreach $key (sort {$a <=> $b} (keys (%lmons))) {
	  $lmons{"$key"}->reportWarnings();
	}

	# present other class specific warnings here
	my $ln = keys %wrngCount;
	if ($ln > 0) {
	  print $_EOUT "  Warning Counts: $ln\n";
	  foreach $key (sort keys(%wrngCount)) {
		print $_EOUT "\t$key = $wrngCount{$key}\n";
	  }
	  print $_EOUT "\n\n  Warning data:\n";
	  foreach $key (sort keys(%Warnings)) {
		print $_EOUT "\tWARN: $key => $Warnings{$key}\n";
	  }
	  print "\n\n";
	}
  }

  sub reportErrors {
	my $self = shift;
	my ($key, $ln, @vals);
	print $_OUT "Attributes: Errors\n";

	foreach $key (sort {$a <=> $b} (keys (%mons))) {
	  $mons{"$key"}->reportErrors();
	}

	foreach $key (sort {$a <=> $b} (keys (%lmons))) {
	  $lmons{"$key"}->reportErrors();
	}

	# present other error numbers.
	# present other class specific errors here
	my $ln = keys %errCount;
	if ($ln > 0) {
	  print $_EOUT "  Error Counts: $ln\n";
	  foreach $key (sort keys(%errCount)) {
		print $_EOUT "\t$key = $errCount{$key}\n";
	  }
	  print $_EOUT "\n\n  Error Data:\n";
	  foreach $key (sort keys(%Errors)) {
		print $_EOUT "\t****ERR: $key => $Errors{$key}\n";
	  }
	  print $_EOUT "\n\n";
	}
  }

  sub report {
	my ($self) = @_;
	my $key;

	## find other errors

	# IFM_6: All VPT atoms have STY of Intl Prod.
	&$subref_checkVPTAtomWithNoSty();


	# IFM_5: check XMAP/TO/FROM attributes
	&$subref_checkXMAPAttrs();

	print $_OUT "Attributes:\n";
	print $_EOUT "Attributes:\n";
	$self->reportErrors();
	$self->reportWarnings();
	$self->reportInfo();
	print $_OUT "End of Attributes check\n";
	print $_EOUT "End of Attributes check\n";
	print $_OUT "#=================\n\n";
	print $_EOUT "#=================\n\n";
  }


  # release memory.
  sub release {
	%mons = ();
	%lmons = ();
	%errCount = ();
	%Errors = ();
	%wrngCount=();
	%Warnings=();
	%infoCount=();
	%Information=();

	%attrAtui = ();
	%xmap3Attr=();
	%xmap6Attr=();
	%xmapToAttr=();
	%xmapFromAttr=();
  }

  sub getAllRef {
	my $self = shift;
	my $which = shift;
	return $mons{$which}->getAllHsh();
  }

  sub setOtherValids {}


}
1

