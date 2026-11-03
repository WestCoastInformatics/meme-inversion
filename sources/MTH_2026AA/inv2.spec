SourceDir|/local/content/MEME/MEME5/inv/sources/MTHrelease
SourceExt|.RRF
SourceFieldSep|BAR
SourceSchemaDefType|InThisSpec
Schema|MRCONSO*|CUI|LAT|TS|LUI|STT|SUI|ISPREF|AUI|SAUI|SCUI|SDUI|SAB|TTY|CODE|STR|SRL|SUPPRESS|CVF|
Schema|MRREL*|CUI1|AUI1|STYPE1|REL|CUI2|AUI2|STYPE2|RELA|RUI|SRUI|SAB|SL|RG|DIR|SUPPRESS|CVF|
Schema|MRSTY*|CUI|TUI|STN|STY|ATUI|CVF
Schema|MRDEF*|CUI|AUI|ATUI|SATUI|SAB|DEF|SUPPRESS|CVF
Schema|MRSAT*|CUI|LUI|SUI|METAUI|STYPE|CODE|ATUI|SATUI|ATN|SAB|ATV|SUPPRESS|CVF

DefineConst|MTHSAB|MTHrelease

Schema|aui_said_map|AUI|CUI|SRC_ATOM_ID
Schema|aui_said_map2|AUI|CUI|SRC_ATOM_ID
Schema|cui_said_map|CUI|SRC_ATOM_ID


# attributes
Dest|attributes.src
Copy|attr_src

Scan|MRSAT*|where <STYPE> ne 'CUI' && <METAUI> matches aui_said_map.AUI
	line_number|aui_said_map.SRC_ATOM_ID|S|<ATN>|<ATV>|<SAB>|R|Y|N|<SUPPRESS>|SRC_ATOM_ID||<SATUI>|md5hash|

Scan|MRSAT*|where <STYPE> eq 'CUI' && <ATN> !~ /^(DA|MR|ST)$/ && <CUI> matches cui_said_map.CUI
	line_number|<CUI>|S|<ATN>|<ATV>|<SAB>|R|Y|N|<SUPPRESS>|CUI||<SATUI>|md5hash|

# [UMLSCUI attrs no longer needed as of 2017AA - uses CUIs in classes_atoms now]
# make UMLSCUI attributes for each atom
#Scan|aui_said_map
#	line_number|<SRC_ATOM_ID>|S|UMLSCUI|<CUI>|<const:MTHSAB>|R|n|N|N|SRC_ATOM_ID|||md5hash|
#
#Schema|moved_aui_said_map|AUI|CUI|SRC_ATOM_ID
#
#Scan|moved_aui_said_map
#	line_number|<SRC_ATOM_ID>|S|UMLSCUI|<CUI>|<const:MTHSAB>|R|n|N|N|SRC_ATOM_ID|||md5hash|

Scan|MRSTY*|where <CUI> matches cui_said_map.CUI
	line_number|cui_said_map.SRC_ATOM_ID|C|SEMANTIC_TYPE|<STY>|E-<const:MTHSAB>|R|Y|N|N|SRC_ATOM_ID|||md5hash|

Scan|MRDEF*|where <AUI> matches aui_said_map.AUI
	line_number|aui_said_map.SRC_ATOM_ID|S|DEFINITION|<DEF>|<SAB>|R|Y|N|<SUPPRESS>|SRC_ATOM_ID||<SATUI>|md5hash|


# relationships
Dest|relationships.src
Copy|rel_src

# note: only include one direction for each REL: where UI1 <= UI2
Scan|MRREL*|where <REL> !~ /^(PAR|CHD|SIB)$/ && (<STYPE1> ne 'CUI' || <STYPE2> ne 'CUI') && (<DIR> eq 'Y' || (<DIR> ne 'N' && (<RG> ne '' || <AUI1> le <AUI2>))) && <AUI1> matches aui_said_map.AUI && <AUI2> matches aui_said_map2.AUI
	line_number|S|aui_said_map.SRC_ATOM_ID|<REL>|<RELA>|aui_said_map2.SRC_ATOM_ID|<SAB>|<SL>|R|Y|N|<SUPPRESS>|SRC_ATOM_ID||SRC_ATOM_ID||~DA:<RG>|<RG>|

Schema|rel_cui_said_map|CUI|SRC_ATOM_ID
Schema|rel_cui_said_map2|CUI|SRC_ATOM_ID

Scan|MRREL*|where <REL> !~ /^(PAR|CHD|SIB)$/ && <STYPE1> eq 'CUI' && <STYPE2> eq 'CUI' && (<DIR> eq 'Y' || (<DIR> ne 'N' && <CUI1> le <CUI2>)) && <CUI1> matches rel_cui_said_map.CUI && <CUI2> matches rel_cui_said_map2.CUI
	line_number|S|<CUI1>|<REL>|<RELA>|<CUI2>|<SAB>|<SL>|R|Y|N|<SUPPRESS>|CUI_CURRENT||CUI_CURRENT||~DA:<RG>|<RG>|


# mergefacts
Dest|mergefacts.src
Copy|merge_src

# Merge each AUI into its CUI (don't make this any more, now being done by
# loader based on CUI values in classes_atoms)
#Scan|MRCONSO*|where <AUI> matches aui_said_map.AUI
#	aui_said_map.SRC_ATOM_ID|SY|<CUI>|<const:MTHSAB>||N|N|META-CUI|SRC_ATOM_ID||CUI||

Schema|auis_nonupdatedSAB_moved|AUI|CUI
Schema|moved_aui_said_map|AUI|CUI|SRC_ATOM_ID

# modify this to use a new file of moved-AUI to said mappings
Scan|auis_nonupdatedSAB_moved|where <AUI> matches moved_aui_said_map.AUI
	moved_aui_said_map.SRC_ATOM_ID|SY|<CUI>|<const:MTHSAB>||N|N|META-MOVED|SRC_ATOM_ID||CUI_CURRENT||

Schema|cui_merges|OLDCUI|CUI

Scan|cui_merges
	<OLDCUI>|SY|<CUI>|<const:MTHSAB>||N|N|META-MERGE|CUI||CUI_CURRENT||

