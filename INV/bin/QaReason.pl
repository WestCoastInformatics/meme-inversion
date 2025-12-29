#!/usr/bin/perl
#
unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

use Getopt::Std;

my %options=();
getopts("haf:t:", \%options);

my $showAll = 0;
my $file = "";
my $type = "";
if (defined $options{'a'}) { $showAll = 1; }
if (defined $options{'f'}) { $file = $options{'f'}; }
if (defined $options{'t'}) { $type = $options{'t'}; }
if (defined $options{'h'}) {
    print "QaReasons.pl\n".
	"  h - show help\n".
	"  a - show all the messages\n".
	"  f - show messages for the file [termgroups sources\n".
	"          atoms attributes relationships merges contexts]\n".
	"  t - show messages for this type\n\n";
    exit;
}


# 1 = doc
# 2 = sources
# 3 = termgroups
# 4 = atoms
# 5 = attributes
# 6 = rels
# 7 = merges
# 8 = contexts
sub showReason {

    # file: doc
    $file = lc($file);
    if ($file eq 'doc' || $showAll == 1) {
    }

    # file: termgroups
    if ($file eq 'termgroups' || $showAll == 1) {
	print "\n". "\n\nFile: termgroups\n";

	if ($type eq 'VFieldCount' || $type eq ""){
	    print "\n". 
		"  VFieldCount:\n".
		"  0. count number of fields\n\n".
		"    Format: VFieldCount_XX = YY\n".
		"      XX - termgroup_name\n".
		"      YY - number of fields in a record\n\n";

	}
	if ($type eq 'ETgTtyismatch' || $type eq "") {
	    print "\n".
		"  ETgTtyismatch:\n".
		"  1. tty in each line must be present in the termgroup\n\n".
		"    Query: SELECT Termgroup, TTY FROM termgroups\n".
		"             WHERE SUBSTR(Termgroup,INSTR(Termgroup,'/')+1)\n".
		"                    =~ TTY;\n\n".
		"    Format: ETgTtyismatch_XX = P|Q\n".
		"      XX - record number\n".
		"       P - termgroup_name\n".
		"       Q - termtype\n\n";

	}
	if ($type eq 'EUndefinedSrc' || $type eq "") {
	    print "\n".
		"  EUndefinedSrc:\n".
		"  2. source in tg must be a valid one specified in sources file\n\n".
		"    Format: EUndefinedSrc_XX = YY\n".
		"      XX - record number\n".
		"      YY - source\n";

	} 
    }

    # file: sources
    if ($file eq 'sources' || $showAll == 1) {
	print "\n". "\n\nFile: sources\n";

	if ($type eq 'EFieldCount' || $type eq "") {
	    print "\n".
		"  EFieldCount:\n".
		"  0. count number of fields\n\n".
		"    Format: EFieldCount_XX = YY\n".
		"      XX - source_name\n".
		"      YY - number of fields in a record\n\n";

	}
	if ($type eq 'EForeignRsabSFMatch' || $type eq "") {
	    print "\n".
		"  EForeignRsabSFMatch:\n".
		"  1. RSAB matches SF for non-English source\n\n".
		"    Query: SELECT VSAB,RSAB,SF FROM sources \n".
		"             WHERE RSAB = SF AND LAT != 'ENG';\n\n".
		"    Format: EForeignRsabSFMatch_XX = P|Q|R\n".
		"      XX - source_name\n".
		"       P - source_name\n".
		"       Q - stripped_source\n".
		"       R - source_family\n\n";

	}
	if ($type eq 'ERsabNormRsabMismatch' || $type eq "") {
	    print "\n".
		"  ERsabNormRsabMismatch:\n".
		"  2. RSAB mismatch with NOrmalizedRSAB for non MSH atoms\n\n".
		"    Query: SELECT VSAB, NormalizedRSAB FROM sources \n".
		"              WHERE RSAB != NormalizedRSAB AND SF != MSH;\n\n".
		"    Format: ERsabNormRsabMismatch_XX = YY\n".
		"      XX - source_name\n".
		"      YY - normalized_source\n\n";

	} 
    } 

    # fiel: atoms
    if ($file eq 'atoms' || $showAll == 1) {
	print "\n". "\n\nFile: atoms\n";

	if ($type eq 'VFieldCount' || $type eq "") {
	    print "\n".
		"  VFieldCount:\n".
		"  0. Number of fields in the input record\n\n".
		"    Format: VFiedlCount_XX = YY\n".
		"      XX - src_atom_id\n".
		"      YY - number of fields in the offending line\n\n";

	}
	if ($type eq 'WDplCSSStrings' || $type eq "") {
	    print "\n".
		"  WDplCSSStrings:\n".
		"  L1. Number of Case Sensitive Strings\n\n".
		"    Query: SELECT count(*) \n".
		"             FROM (SELECT STR \n".
		"                     FROM classes_atoms \n".
		"                          GROUP BY STR HAVING count(*)>1);\n\n".
		"    Format: WDplCSSStrings_XX = YY\n".
		"      XX - src_atom_id\n".
		"      YY - string (atom)\n\n";

	}
	if ($type eq 'WDplCISStrings' || $type eq "") {
	    print "\n".
		"  WDplCISStrings:\n".
		"  L2, Number of Case Insensitive Strings\n\n".
		"    Query: SELECT count(*) \n".
		"             FROM (SELECT lower(STR) STR \n".
		"                     FROM classes_atoms \n".
		"                     GROUP BY lower(STR) \n".
		"                     HAVING count(*)>1);\n\n".
		"    Format: WDplCISStrings_XX = YY\n".
		"      XX - src_atom_id\n".
		"      YY - string(atom)\n\n";

	}
	if ($type eq 'ETgVsabMismatch' || $type eq "") {
	    print "\n".
		"  ETgVsabMismatch:\n".
		"  L3. Vsab and Termgroup mismatch\n\n".
		"    Query: SELECT * FROM classes_atoms \n".
		"             WHERE VSAB != SUBSTR(Termgroup,1,INSTR(Termgroup,'/'));\n\n".
		"    Format: ETgVsabMismatch_XX = YY|ZZ\n".
		"      XX - src_atom_id\n".
		"      YY - vsab\n".
		"      ZZ - termgroup\n\n";

	}
	if ($type eq 'ECdACDuiMismatch' || $type eq "") {
	    print "\n".
		"  ECdACDuiMismatch:\n".
		"  L4. Code not mathcing with any of the non-null saui/sdui/scui fields\n\n".
		"    Query: SELECT * FROM classes_atoms \n".
		"             WHERE NOT (SCUI IS NULL AND SAUI IS NULL AND SDUI IS NULL) \n".
		"                   AND CODE != SAUI AND CODE != SCUI AND CODE != SDUI;\n\n".
		"    Format ECdACDuiMismatch_XX = P|Q|R|S\n".
		"      XX - src_atom_id\n".
		"      P  - code\n".
		"      Q  - SAUI\n".
		"      R  - SCUI\n".
		"      S  - SDUI\n\n";

	}
	if ($type eq 'ENonUniqueAuis' || $type eq "") {
	    print "\n".
		"  ENonUniqueAuis:\n".
		"  L5. non unique AUI fields\n\n".
		"    Query: SELECT count(*),Termgroup,STR,CODE,SAUI,SCUI,SDUI \n".
		"             FROM classes_atoms \n".
		"             GROUP BY Termgroup,STR,CODE,SAUI,SCUI,SDUI \n".
		"             HAVING count(*) >1;\n\n".
		"    Format: ENonUniqueAuis_XX = P|Q|R|S|T|U\n".
		"      XX - src_atom_id\n".
		"      P  - termgroup\n".
		"      Q  - string\n".
		"      R  - code\n".
		"      S  - SAUI\n".
		"      T  - SCUI\n".
		"      U  - SDUI\n\n";

	}
	if ($type eq 'WStrsWithBracketNums' || $type eq "") {
	    print "\n".
		"  WStrsWithBracketNums:\n".
		"  L6. Angle brackets in str\n\n".
		"    Query: SELECT VSAB, CODE, STR FROM CLASSES \n".
		"             WHERE regexp_like(STR, ' <[[:digit:]]+>$');\n\n".
		"    Format: WStrsWithBracketNums_XX = YY\n".
		"      XX - src_atom_id\n".
		"      YY - string\n\n";

	}
	if ($type eq 'WStrsWithXMLChars' || $type eq "") {
	    print "\n".
		"  WStrsWithXMLChars:\n".
		"  L7. XML chars in str\n\n".
		"    Query: SELECT VSAB, CODE, STR FROM CLASSES \n".
		"             WHERE regexp_like(STR, '&[[:alnum:]]+;');\n\n".
		"    Format: WStrsWithXMLChars_XX = YY\n".
		"      XX - src_atom_id\n".
		"      YY - string\n\n";

	}
	if ($type eq 'EForeignSrc' || $type eq "") {
	    print "\n".
		"  EForeignSrc:\n".
		"  L8. foreign SRC atom\n\n".
		"    Query: SELECT VSAB, CODE, LAT, STR FROM classes_atoms \n".
		"             WHERE VSAB = 'SRC' AND LAT != 'ENG';\n\n".
		"    Format: EForeignSrc_XX = P|Q|R|S\n".
		"      XX - src_atom_id\n".
		"      P  - source\n".
		"      Q  - code\n".
		"      R  - language\n".
		"      S  - string\n\n";

	}
	if ($type eq 'EUndefinedSource' || $type eq "") {
	    print "\n".
		"  EUndefinedSource:\n".
		"  F2. source not defined in sources.src file\n\n".
		"    Query: SELECT VSAB,LAT FROM classes_atoms \n".
		"             WHERE (VSAB,LAT) NOT IN (SELECT VSAB,LAT FROM sources) \n".
		"                    AND VSAB != 'SRC';\n\n".
		"    Format: EUndefinedSource_XX = YY\n".
		"      XX - src_atom_id\n".
		"      YY - source\n\n";

	}
	if ($type eq 'EUndefinedTG' || $type eq "") {
	    print "\n".
		"  EUndefinedTG:\n".
		"  F3. termgroup not defined in termgroups.src file\n\n".
		"    Query: SELECT Termgroup FROM classes_atoms \n".
		"             WHERE Termgroup NOT IN (SELECT Termgroup FROM termgroups) \n".
		"             AND VSAB != 'SRC';\n\n".
		"    Format: EUndefinedTG_XX = YY\n".
		"      XX - src_atom_id\n".
		"      YY - termgroup\n\n";

	}
	if ($type eq 'EUndefinedTTY' || $type eq "") {
	    print "\n".
		"  EUndefinedTTY:\n".
		"  F4. TTY not in Termgroups.src file\n\n".
		"    Query: SELECT Termgroup FROM classes_atoms \n".
		"             WHERE VSAB != 'SRC' \n".
		"               AND SUBSTR(Termgroup,INSTR(Termgroup,'/')+1) NOT IN \n".
		"                    (SELECT VALUE FROM mrdoc \n".
		"                       WHERE DOCKEY='TTY' AND TYPE = 'expanded_form');\n\n".
		"    Format: EUndefinedTTY_XX = YY\n".
		"      XX - src_atom_id\n".
		"      YY - tty\n\n";

	}
	if ($type eq 'EInvRABCode' || $type eq "") {
	    print "\n".
		"  EInvRABCode:\n".
		"  F6,7. Invalid RAB/VAB code\n\n".
		"    Query: SELECT STR, CODE FROM classes_atoms \n".
		"             WHERE Termgroup = 'SRC/RAB' AND 'V-' || STR != CODE;\n\n".
		"    Format: EInvRABCode_XX = YY\n".
		"      XX - src_atom_id\n".
		"      YY - code\n\n";

	}
	if ($type eq 'EDuplicateSrcVabRab' || $type eq "") {
	    print "\n".
		"  EDuplicateSrcVabRab:\n".
		"  F8,9. More than 1 VAB RAB records\n\n".
		"    Query: SELECT VSAB, CODE, STR FROM classes_atoms \n".
		"             WHERE CODE IN (SELECT CODE FROM classes_atoms \n".
		"                              WHERE Termgroup = 'SRC/VAB' \n".
		"                              GROUP BY CODE\n".
		"                              HAVING COUNT(*)>1);\n\n".
		"    Format: EDuplicateSrcVabRab_XX = YY\n".
		"      XX - src_atom_id\n".
		"      YY - number of such records.\n\n";

	}
    }

    # file: attributes
    if ($file eq 'attributes' || $showAll == 1) {
	print "\n". "\n\nFile: attributes\n";

	if ($type eq 'VFieldCount' || $type eq "") {
	    print "\n".
		"  VFieldCount:\n".
		"  0. Number of fields in the input record\n\n".
		"    Query: SELECT count(*), ATN FROM attributes \n".
		"             GROUP BY ATN HAVING COUNT(DISTINCT ATV)>1;\n\n".
		"    Format: VFiedlCount_XX = YY\n".
		"      XX - src_attribute_id\n".
		"      YY - number of fields in the offending line\n\n"

	}
	if ($type eq 'ENonCLvlStys' || $type eq "") {
	    print "\n".
		"  ENonCLvlStys:\n".
		"  2. attribute level must be C\n\n".
		"    Query: SELECT SrcAttrId, Lvl FROM attributes \n".
		"             WHERE atn = 'SEMANTIC_TYPE'\n".
		"               AND Lvl != 'C';\n\n".
		"    Format: ENonCLvlStys_XX = P|Q\n".
		"      XX - record_id\n".
		"      P  - src_attribute_id\n".
		"      Q  - attribute_level\n\n";
	}
	if ($type eq '???FileMON22' || $type eq "") {

	}
	if ($type eq 'ENonSrcStysNonESrc' || $type eq "") {
	    print "\n".
		"  ENonSrcStysNonESrc:\n".
		"  8. Source should be like E-* for non SRC stys.\n\n".
		"    Query: SELECT * from Attributes \n".
		"             WHERE ATN = 'SEMANTIC_TYPE = 'N' AND VSAB != 'E-%';\n".
		"    Foramt: ENonSrcStysNonESrc_XX = P|Q\n".
		"      XX - record_id\n".
		"      P  - status\n".
		"      Q  - source\n\n";

	}
	if ($type eq '???FileMon 16' || $type eq "") {

	}
	if ($type eq 'ECLvlNonStys' || $type eq "") {
	    print "\n".
		"  ECLvlNonStys:\n".
		"  3. attribute level must be S\n\n".
		"    Query: SELECT SrcAttrId, VSAB, ATN, Lvl FROM attributes \n".
		"             WHERE atn != 'SEMANTIC_TYPE' AND Lvl != 'S'\n\n".
		"    Format: ECLvlNonStys_XX = P|Q|R|S\n".
		"      XX - record_id\n".
		"      P  - src_attribte_id\n".
		"      Q  - source\n".
		"      R  - attribute_name\n".
		"      S  - attribute_level\n\n";

	}
	if ($type eq 'ETbrYCxts' || $type eq "") {
	    print "\n".
		"  ETbrYCxts:\n".
		"  4. CONTEXT attributes are can not be releasable\n\n".
		"    Query: SELECT SrcAttrId, VSAB FROM attributes \n".
		"             WHERE Tbr in ('y','Y') AND ATN = 'CONTEXT';\n\n".
		"    Format: ETbrYCxts_XX = P|Q\n".
		"      XX - record_id\n".
		"      P  - src_attribute_id\n".
		"      Q  - source\n\n";

	}
	if ($type eq 'ENonUniqueAtui' || $type eq "") {
	    print "\n".
		"  ENonUniqueAtui:\n".
		"  7. non unique ATUIs\n\n".
		"    Query: SELECT count(*),VSAB,ATN,HashCode,SgId,SgType,SgQual \n".
		"             FROM attributes \n".
		"             GROUP BY VSAB, ATN, HashCode, SgId, SgType, SgQual \n".
		"             HAVING count(*)>1;\n\n".
		"    Format: ENonUniqueAtui_XX = YY: {PQRSTU}\n".
		"      XX - record_id\n".
		"      YY - duplicate record_id\n".
		"      P  - source\n".
		"      Q  - attribute_name\n".
		"      R  - id\n".
		"      S  - id_type\n".
		"      T  - id_qualifier\n\n";

	}
	if ($type eq 'EInvTbrLexTrd' || $type eq "") {
	    print "\n".
		"  EInvTbrLexTrd:\n".
		"  5. invalid tbr/lexical_tag/TRD\n\n".
		"    Query: SELECT SrcAttrId, VSAB FROM attributes \n".
		"             WHERE ATN = 'LEXICAL_TAG' \n".
		"               AND ((ATV NOT in ('LAB', 'TRD'))) \n".
		"                     OR (Tbr in ('n','N') AND ATV = 'TRD') \n".
		"                     OR (Tbr NOT in ('n', 'N') AND ATV != 'TRD'));\n\n".
		"    Format: EInvTbrLexTrd = P|Q|R\n".
		"      P - to_be_released\n".
		"      Q - attribute_name\n".
		"      R - attribute_value\n\n";

	}
	if ($type eq 'EStsNLvlS' || $type eq "") {
	    print "\n".
		"  EStsNLvlS:\n".
		"  6. S level attributes can not have N status\n\n".
		"    Query: SELECT SrcAttrId, VSAB FROM attributes \n".
		"             WHERE Status = 'N' AND Lvl = 'S';\n\n".
		"    Format: EStsNLvlS_XX = P|Q\n".
		"      P - src_attribute_id\n".
		"      Q - source\n\n";

	}
	if ($type eq 'WXMLChars' || $type eq "") {
	    print "\n".
		"  WXMLChars:\n".
		"  9. check for XML chars - \$pat9 = qr(&[[:alnum:]]+);\n\n".
		"    Query: SELECT VSAB, ATV FROM attributes \n".
		"             WHERE regexp_like(ATV, '&[[:alnum:]]+');\n\n".
		"    Format: WXMLChars_P = Q|R\n".
		"      P - src_attribute_id\n".
		"      Q - source\n".
		"      R - attribute_value\n\n";

	}
	if ($type eq 'EInvSgTypeQual' || $type eq "") {
	    print "\n".
		"  EInvSgTypeQual:\n".
		"  10. invalid sgtype/sgqual\n\n".
		"    Query: SELECT VSAB, SgId, SgType FROM attributes \n".
		"             WHERE SgQual IS NULL \n".
		"               AND SgType NOT IN \n".
		"                   ('SRC_ATOM_ID','SRC_REL_ID','CUI','AUI','RUI');\n\n".
		"    Format: EInvSgTypeQual_XX = P|Q|R\n".
		"      XX - record_id\n".
		"       P - id\n".
		"       Q - id_type\n".
		"       R - id_qualifier\n\n";

	}
	if ($type eq 'WNonNullSAtui' || $type eq "") {
	    print "\n".
		"  WNonNullSAtui:\n".
		"  11. non null satui - warning.\n\n".
		"    Query: SELECT VSAB, SrcAttrId, SATUI \n".
		"             FROM attributes WHERE SATUI IS NOT NULL;\n\n".
		"    Format: WNonNullSAtui_XX = P|Q|R\n".
		"      XX - src_attribute_id\n".
		"       P - source\n".
		"       Q - src_attribute_id\n".
		"       R - src_atui\n\n";

	}
	if ($type eq 'ENullRelaForXmapRN' || $type eq "") {
	    print "\n".
		"  ENullRelaForXmapRN:\n".
		"  12. null rela for XMAP RN rels\n\n".
		"    Query: SELECT VSAB, SrcAttrId FROM attributes \n".
		"             WHERE attribute_name='XMAP' \n".
		"               AND SUBSTR(ATV, \n".
		"                          instr(ATV, '~', 1, 3) + 1, \n".
		"                          (INSTR(ATV, '~', 1, 4) \n".
		"                             - INSTR(ATV, '~', 1, 3)) -1 ) \n".
		"                   IS NULL;\n\n".
		"    Format: ENullRelaForXmapRN_XX = P|Q|R\n".
		"      XX - src_attribute_id\n".
		"       P - source\n".
		"       Q - src_attribute_id\n".
		"       R - attribute_value\n\n";

	}
	if ($type eq 'EInvSgType' || $type eq "") {
	    print "\n".
		"  EInvSgType:\n".
		"  Validate sgId1, sgType1, sgQual1 for attr.1 - 13\n\n".
		"    Format: EInvSgType_XX = P|Q|R\n".
		"      XX - src_attribute_id\n".
		"       P - id\n".
		"       Q - id_type\n".
		"       R - id_qualifier\n\n";

	}
	if ($type eq 'EInvAttrName' || $type eq "") {
	    print "\n".
		"  EInvAttrName:\n".
		"  F15 check if the ATN is valid\n\n".
		"    Format: EInvAttrName_XX = YY\n".
		"      XX - src_attribute_id\n".
		"      YY - attribute_name\n\n";

	}
	if ($type eq 'EInvVSab' || $type eq "") {
	    print "\n".
		"  EInvVSab:\n".
		"  Invalid VSab\n\n".
		"    Format: EInvVSab_XX = YY\n".
		"      XX - src_attribute_id\n".
		"      YY - source\n\n";
	}
    }

    # file: relationships
    if ($file eq 'relationships' || $showAll == 1) {
	print "\n". "\n\nFile: relationships\n";
	if ($type eq 'VFieldCount' || $type eq ""){
	    print "\n".
		"  VFieldCount:\n".
		"  0. count number of fields\n\n".
		"    Format: VFieldCount_XX = YY\n".
		"      XX - src_relationship_id\n".
		"      YY - number of fields in a record\n\n";

	}
	if ($type eq 'EVsabNeSL' || $type eq "") {
	    print "\n".
		"  EVsabNeSL:\n".
		"  1. VSAB not equal to Source of Label\n\n".
		"    Query: SELECT SrcRelId, VSAB, SL \n".
		"             FROM relationships WHERE VSAB != SL;\n\n".
		"    Format: EVsabNeSL_XX = P|Q|R\n".
		"      XX - src_relationship_id\n".
		"       P - src_relationship_id\n".
		"       Q - source\n".
		"       R - source_of_label\n";

	}
	if ($type eq 'ESelfRefRels' || $type eq "") {
	    print "\n".
		"  ESelfRefRels:\n".
		"  2. self referential relationships\n\n".
		"    Query: SELECT SrcRelId, VSAB FROM relationships \n".
		"             WHERE SgId1 = SgId2 \n".
		"               AND SgType1 = SgType2 \n".
		"               AND NVL(SgQual1,'null') = NVL(SgQual2,'null');\n\n".
		"    Format: ESelfRefRels_XX = P|Q\n".
		"      XX - src_relationship_id\n".
		"       P - src_relationship_id\n".
		"       Q - source\n\n";

	}
	if ($type eq 'EInvRelRela' || $type eq "") {
	    print "\n".
		"  EInvRelRela:\n".
		"  3. conflicting rel/rela\n\n".
		"    Query: SELECT SrcRelId, VSAB, REL, RELA \n".
		"             FROM relationships \n".
		"             WHERE (RELA in ('associated_with','consists_of',\n".
		"                             'constitutes', 'contains','contained_in',\n".
		"                             'ingredient_of','has_ingredient') \n".
		"                    AND REL != 'RT') \n".
		"               OR (RELA in ('conceptual_part_of','form_of','isa',\n".
		"                            'part_of', 'tradname_of') \n".
		"                   AND REL != 'NT') \n".
		"               OR (RELA in ('has_conceptual_part','has_form',\n".
		"                            'inverse_isa', 'has_part','has_tradname') \n".
		"                   AND REL != 'BT');\n\n".
		"    Format: EInvRelRela_XX = P|Q|R|S\n".
		"      XX - src_relationship_id\n".
		"       P - src_relationship_id\n".
		"       Q - source\n".
		"       R - relationship_name\n".
		"       S - relationship_attribute\n\n";

	}
	if ($type eq 'ENonUniqueRuis' || $type eq "") {
	    print "\n".
		"  ENonUniqueRuis:\n".
		"  4. Non Unique RUIS\n\n".
		"    Query: SELECT count(*),VSAB,REL,RELA,SgId1,SgType1,\n".
		"                  SgQual1,SgId2,SgType2,SgQual2 \n".
		"             FROM relationships \n".
		"             GROUP BY VSAB,REL,RELA,SgId1,SgType1,\n".
		"                      SgQual1,SgId2,SgType2,SgQual2 \n".
		"             HAVING count(*)>1;\n\n".
		"    Format: ENonUniqueRuis_XX = <P> : Q\n".
		"      XX - src_relationship_id\n".
		"       P - relRuis (Relationship Unique Identifier)\n".
		"       Q - source|relationship_name|relationship_attribute\n".
		"           |id_1|id_type_1|id_qualifier_1|id_2|id_type_2\n".
		"           |id_qualifier_2\n\n";

	}
	if ($type eq 'EOrphanSFOLFO' || $type eq "") {
	    print "\n".
		"  EOrphanSFOLFO:\n".
		"  5. SFO/LFO not connected to any atom\n\n".
		"    Query: SELECT VSAB,SgType1,SgType2 \n".
		"             FROM relationships \n".
		"             WHERE REL = 'SFO/LFO' \n".
		"               AND (SgType1 NOT IN \n".
		"                       ('ROOT_SOURCE_AUI','SOURCE_AUI','SRC_ATOM_ID') \n".
		"                    OR \n".
		"                    SgType2 NOT IN \n".
		"                       ('ROOT_SOURCE_AUI','SOURCE_AUI','SRC_ATOM_ID'));\n\n".
		"    Format: EOrphanSFOLFO_XX = P|Q|R\n ".
		"      XX - src_relationship_id\n".
		"       P - source\n".
		"       Q - id_type_1\n".
		"       R - id_type_2\n\n";

	}
	if ($type eq 'EInvSgTypeQual1' || $type eq "") {
	    print "\n".
		"  EInvSgTypeQual1:\n".
		"  6. sgType1 without Requied SgQual1\n\n".
		"    Query: SELECT VSAB, SgId1, SgType1 \n".
		"             FROM relationships \n".
		"             WHERE SgQual1 IS NULL \n".
		"               AND SgType1 NOT IN \n".
		"                   ('SRC_ATOM_ID','SRC_REL_ID','CUI','AUI','RUI');\n\n".
		"    Format: EInvSgTypeQual1_XX = P|Q|R\n ".
		"      XX - src_relationship_id\n".
		"       P - source\n".
		"       Q - id_1\n".
		"       R - id_type_1\n\n";

	}
	if ($type eq 'EInvSgTypeQual2' || $type eq "") {
	    print "\n".
		"  EInvSgTypeQual2:\n".
		"  7. sgType2 without Requied SgQual2\n\n".
		"    Query: SELECT VSAB, SgId2, SgType2 \n".
		"             FROM relationships \n".
		"             WHERE SgQual2 IS NULL \n".
		"               AND SgType2 NOT IN \n".
		"                   ('SRC_ATOM_ID','SRC_REL_ID','CUI','AUI','RUI');\n\n".
		"    Format: EInvSgTypeQual2_XX = P|Q|R\n".
		"      XX - src_relationship_id\n".
		"       P - source\n".
		"       Q - id_2\n".
		"       R - id_type_2\n\n";

	}
	if ($type eq 'EInvSgsTransVer' || $type eq "") {
	    print "\n".
		"  EInvSgsTransVer:\n".
		"  8. inv sgs for translation_of and version rel\n\n".
		"    Query: SELECT SrcRelId, rela  \n".
		"             FROM relationships \n".
		"             WHERE RELA = 'translation_of' AND VSAB = 'SRC' \n".
		"               AND (SgType1 != 'CODE_TERMGROUP' \n".
		"                    OR SgType2 != 'CODE_TERMGROUP' \n".
		"                    OR SgQual1 != 'SRC/RPT' \n".
		"                    OR SgQual2 != 'SRC/RPT');\n\n".
		"    Format: EInvSgsTransVer_XX = P|Q\n".
		"      XX - src_relationship_id\n".
		"       P - src_relationship_id\n".
		"       Q - relationship_attribute\n\n";

	}
	if ($type eq 'EInvSgType1_Rels' || $type eq "") {
	    print "\n".
		"  EInvSgType1_rels:\n".
		"  validate sgId1, sgType1, sgQual1 in Relationships\n\n".
		"    Format: EinvSgType1_rels_XX = P|Q|R\n".
		"      XX - src_relationship_id\n".
		"       P - id_1\n".
		"       Q - id_type_1\n".
		"       R - id_qualifier_1\n\n";

	}
	if ($type eq 'EInvSgType2_Rels' || $type eq "") {
	    print "\n".
		"  EInvSgType2_Rels:\n".
		"  validate sgId2, sgType2, sgQual2 in Relationships\n\n".
		"    Format: EInvSgType2_Rels_XX = P|Q|R\n".
		"      XX - src_relationship_id\n".
		"       P - id_2\n".
		"       Q - id_type_2\n".
		"       R - id_qualifier_2\n\n";

	}
	if ($type eq 'EInvRela' || $type eq "") {
	    print "\n".
		"  EInvRela:\n".
		"  check for valid rela\n\n".
		"    Format: EInvRela_XX = YY\n".
		"      XX - src_relationship_id\n".
		"      YY - relationship_attribute\n\n";

	}
	if ($type eq 'EInvVSab' || $type eq "") {
	    print "\n".
		"  EInvVSab:\n".
		"  check for valid vsab\n".
		"    format: EInvVSab_XX = YY\n".
		"      XX - src_relationship_id\n".
		"      YY - source\n\n";

	}
	if ($type eq '???FileMon27_28' || $type eq "") {

	}
    }

    # file: merges
    if ($file eq 'merges' || $showAll == 1) {
	print "\n". "\n\nFile: merges\n";
	if ($type eq 'VFieldCount' || $type eq ""){
	    print "\n".
		"  VFieldCount:\n".
		"  0. count number of fields\n\n".
		"    Format: VFieldCount_XX = YY\n".
		"      XX - id_1\n".
		"      YY - number of fields in a record\n\n";

	}
	if ($type eq 'EInvSgTypeQual1' || $type eq "") {
	    print "\n".
		"  EInvSgTypeQual1:\n".
		"  1. sgType1 without Required SgQual1\n\n".
		"    Query: SELECT VSAB, SgId1, SgType1 FROM mergefacts \n".
		"             WHERE SgQual1 IS NULL \n".
		"               AND SgType1 NOT IN \n".
		"                   ('SRC_ATOM_ID','SRC_REL_ID','CUI','AUI','RUI');\n\n".
		"    Format: EInvSgTypeQual1_XX = P|Q|R\n".
		"      XX - id1_id2_mergeset\n".
		"       P - source\n".
		"       Q - id_1\n".
		"       R - id_type_1\n\n";

	}
	if ($type eq 'EInvSgTypeQual2' || $type eq "") {
	    print "\n".
		"  EInvSgTypeQual2:\n".
		"  2. sgType2 without Requied SgQual2\n\n".
		"    Query: SELECT VSAB, SgId2, SgType2 FROM mergefacts \n".
		"             WHERE SgQual2 IS NULL AND SgType2 NOT IN \n".
		"                ('SRC_ATOM_ID','SRC_REL_ID','CUI','AUI','RUI');\n\n".
		"    Format: EInvSgTypeQual2_XX = P|Q|R\n".
		"      XX - id1_id2_mergeset\n".
		"       P - source\n".
		"       Q - id_2\n".
		"       R - id_type_2\n\n";

	}
	if ($type eq 'ESelfRefRels' || $type eq "") {
	    print "\n".
		"  ESelfRefRels:\n".
		"  3. self referential mergefacts\n\n".
		"    Query: SELECT * FROM mergefacts \n".
		"             WHERE SgId1 = SgId2 AND SgType1 = SgType2 \n".
		"               AND NVL(SgQual1,'null') = NVL(SgQual2,'null');\n\n".
		"    Format: ESelfRefRels_XX\n".
		"      XX - id1_id2_mergeset\n\n";

	}
	if ($type eq 'EInvSgTypeX_merge' || $type eq "") {
	    print "\n".
		"  EInvSgType1_merge:\n".
		"  validate sgIdX, sgTypeX, sgQualX\n\n".
		"    Format: EInvSgType1_merge_XX_YY = P|Q|R\n".
		"       X - either 1 or 2\n".
		"      XX - idX,id_type_X,id_qualifier_X\n".
		"      YY - idX\n".
		"       P - id_X\n".
		"       Q - id_type_X\n".
		"       R - id_qualifier_X\n\n";

	}
	if ($type eq 'VBadType_X' || $type eq "") {
	    print "\n".
		"  VBadTypeX:\n".
		"  check id with the right id_type\n".
		"    Format: VBadType_XX = P,Q\n".
		"       X - either 1 or 2\n".
		"      XX - idX,id_typeX,mergeset\n".
		"       P - idX\n".
		"       Q - id_type_X\n\n";

	}
	if ($type eq 'VBadQual1s' || $type eq "") {
	    print "\n".
		"  VBadQual1s:\n".
		"  if type is CODE, qualifier must be present\n\n".
		"    Format: VBadQual1s_XX = P, Q\n".
		"      XX - idX, id_typeX, mergeset\n".
		"       P - id_type_X\n".
		"       Q - id_qualifier_X\n\n";
	}
    }

    # file: contexts
    if ($file eq 'contexts' || $showAll == 1) {
	print "\n". "\n\nFile: contexts\n";
	if ($type eq 'VFieldCount' || $type eq ""){
	    print "\n".
		"  VFieldCount:\n".
		"  0. count number of fields\n\n".
		"    Format: VFieldCount_XX = YY\n".
		"      XX - src_atom_id_1,relationship_name,\n".
		"           relationship_attribute,src_atom_id_2\n".
		"      YY - number of fields in a record\n\n";

	}
	if ($type eq 'EParWNullPtr' || $type eq "") {
	    print "\n".
		"  EParWNullPtr:\n".
		"  1. PAR with null PTR\n\n".
		"    Query:  SELECT * FROM contexts WHERE REL='PAR' AND PTR IS NULL;\n\n".
		"    Format: EParWNullPtr_XX\n".
		"      XX - src_atom_id_1,relationship_name,\n".
		"           relationship_attribute,src_atom_id_2\n\n";

	}
	if ($type eq 'ENonUniqueRui' || $type eq "") {
	    print "\n".
		"  ENonUniqueRui:\n".
		"  2. non unique RUI fields\n\n".
		"    Query: SELECT count(*),VSAB,REL,RELA,SgId1,SgType1,\n".
		"                  SgQual1,SgId2,SgType2,SgQual2 \n".
		"             FROM contexts \n".
		"             GROUP BY VSAB,REL,RELA,SgId1,SgType1,SgQual1,SgId2,\n".
		"                      SgType2,SgQual2 HAVING count(*)>1;\n\n".
		"    Format: ENonUniqueRui_XX = P|Q|R|S|T|U|V|W|X|Y\n".
		"      XX - src_atom_id_1,relationship_name,\n".
		"           relationship_attribute,src_atom_id_2\n".
		"       P - source\n".
		"       Q - relationship_name\n".
		"       R - relationship_attribute\n".
		"       S - sg_id_1\n".
		"       T - sg_type_1\n".
		"       U - sg_qualifier_1\n".
		"       V - sg_id_2\n".
		"       W - sg_type_2\n".
		"       X - sg_qualifier_2\n".
		"       Y - parent_treenum\n\n";

	}
	if ($type eq 'EInvSgTypeQual1' || $type eq "") {
	    print "\n".
		"  EInvSgTypeQual1:\n".
		"  3. sgType1 without Requied SgQual1\n\n".
		"    Query: SELECT VSAB, SgId1, SgType1 FROM contexts \n".
		"             WHERE SgQual1 IS NULL \n".
		"               AND SgType1 NOT IN \n".
		"                   ('SRC_ATOM_ID','SRC_REL_ID','CUI','AUI','RUI');\n\n".
		"    Format: EInvSgTypeQual1_XX = P|Q|R\n".
		"      XX - src_atom_id_1,relationship_name,\n".
		"           relationship_attribute,src_atom_id_2\n".
		"       P - source\n".
		"       Q - sg_id_1\n".
		"       R - sg_type_1\n\n";

	}
	if ($type eq 'EInvSgTypeQual2' || $type eq "") {
	    print "\n".
		"  EInvSgTypeQual2:\n".
		"  4. sgType2 without Requied SgQual2\n\n".
		"    Query: SELECT VSAB, SgId2, SgType2 FROM contexts \n".
		"             WHERE SgQual2 IS NULL \n".
		"               AND SgType2 NOT IN \n".
		"                   ('SRC_ATOM_ID','SRC_REL_ID','CUI','AUI','RUI');\n\n".
		"    Format: EInvSgTypeQual2_XX = P|Q|R\n".
		"      XX - src_atom_id_1,relationship_name,\n".
		"           relationship_attribute,src_atom_id_2\n".
		"       P - source\n".
		"       Q - sg_id_2\n".
		"       R - sg_type_2\n\n";

	}
	if ($type eq 'ESibWRela' || $type eq "") {
	    print "\n".
		"  ESibWRela:\n".
		"  5. SIB rel with non-null RELA\n\n".
		"    Query: SELECT SrcRelId, RELA FROM contexts \n".
		"             WHERE REL = 'SIB' AND RELA IS NOT NULL AND VSAB != 'UWDA';\n\n".
		"    Format: ESibWRela_XX = P|Q|R\n".
		"       XX - src_atom_id_1,relationship_name,\n".
		"            relationship_attribute,src_atom_id_2\n".
		"        P - src_atomd_id_1\n".
		"        Q - src_atom_id_2\n".
		"        R - relationship_attribute\n\n";

	}
	if ($type eq 'EVsabNeSL' || $type eq "") {
	    print "\n".
		"  EVsabNeSL:\n".
		"  6. VSAB not equal source of label\n\n".
		"    Query: SELECT SrcRelId, VSAB, SL FROM contexts WHERE VSAB != SL;\n\n".
		"    Format: EVsabNeSL_XX = P|Q|R|S\n".
		"       XX - src_atom_id_1,relationship_name,\n".
		"            relationship_attribute,src_atom_id_2\n ".
		"        P - src_atom_id_1\n".
		"        Q - src_atomd_id_2\n".
		"        R - source\n".
		"        S - source_of_label\n\n";

	}
	if ($type eq 'EParentMismatch' || $type eq "") {
	    print "\n".
		"  EParentMismatch:\n".
		"  7. parent mismatch\n\n".
		"    Query: SELECT * FROM contexts \n".
		"             WHERE SrcAtomId2 != SUBSTR(PTR,INSTR(PTR,'.',-1)+1) \n".
		"               AND PTR like '%.%' AND REL = 'PAR' ;\n\n".
		"    Format: EParentMismatch_XX = P\n".
		"      XX - src_atom_id_1,relationship_name,\n".
		"           relationship_attribute,src_atom_id_2\n".
		"       P - parent_treenum\n\n";

	}
	if ($type eq 'EInvRela' || $type eq "") {
	    print "\n".
		"  EInvRela:\n".
		"  FileMon.23 - check for valid rela\n\n".
		"    Format: EInvRela_XX = YY\n".
		"      XX - src_atom_id_1\n".
		"      YY - relationship_attribute\n\n";

	}
	if ($type eq 'EInvVSab' || $type eq "") {
	    print "\n".
		"  EInvVSab:\n".
		"  FileMon.25 - check for valid vsab\n\n".
		"    Format: EInvVSab_XX = YY\n".
		"      XX - src_atom_id_1\n".
		"      YY - source\n\n";

	}
	if ($type eq 'EInvSgType_X' || $type eq "") {
	    print "\n".
		"  EInvSgType_X: ".
		"  Invalid Sg Group.\n\n".
		"    Format: EInvSgType_XX = P|Q|R\n".
		"       X - either 1 or 2\n".
		"      XX - sg_id_X, id_type_X, id_qualifier_X\n".
		"       P - sg_id_X, id_type_X, id_qualifier_X\n\n";

	}
	if ($type eq 'VBadSaid_X' || $type eq "") {
	    print "\n".
		"  VBadSaidX:\n".
		"  id 1 or 2 must be a valid said\n\n".
		"    Format: VBadSaid_X_YY = ''\n".
		"       X - either id 1 or 2\n".
		"      YY - src_atom_id_1,relationship_name,\n".
		"           relationship_attribute,src_atom_id_2\n\n";

	}
	if ($type eq 'VBadTreePos' || $type eq "") {
	    print "\n".
		"  VBadTreePos: \n".
		"    Format: VBadTreePos_XX_YY = ''\n".
		"      XX -  src_atom_id_1,relationship_name,\n".
		"            relationship_attribute,src_atom_id_2\n".
		"      YY -  parent_treenum???\n\n";
	}
    }
}
&showReason();



