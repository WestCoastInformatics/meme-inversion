SourceDir|/local/content/MEME/MEME5/inv/sources/MTH_2026AA/src
SourceExt|.RRF
SourceFieldSep|BAR
SourceSchemaDefType|InThisSpec
Schema|MRCONSO*|CUI|LAT|TS|LUI|STT|SUI|ISPREF|AUI|SAUI|SCUI|SDUI|SAB|TTY|CODE|STR|SRL|SUPPRESS|CVF|

Schema|vcodes_updated|CODE
Schema|sabs_updated_umls|SAB
Schema|auis_nonupdatedSAB_moved|AUI|CUI

# Allocate IDs before retention filtering so existing assignments stay stable.
Dest|classes_atoms.unfiltered.raw

Schema|class_src|SRC_ATOM_ID|SOURCE|TERMGROUP|CODE|STATUS|TOBERELEASED|RELEASED|ATOM_NAME|SUPPRESSIBLE|SOURCE_AUI|SOURCE_CUI|SOURCE_DUI|LANGUAGE|ORDER_ID|MOVED|CUI|AUI

Scan|class_src
	<WholeLine>||

Scan|MRCONSO*|where <SAB> matches sabs_updated_umls || (<SAB> eq 'SRC' && ((<TTY> !~ /^R/ && <TTY> ne 'SSN') || <CODE> matches vcodes_updated.CODE ))
	src_atom_id|<SAB>|<SAB>/<TTY>|<CODE>|R|Y|A|<STR>|<SUPPRESS>|<SAUI>|<SCUI>|<SDUI>|<LAT>|needs_order_id|N|<CUI>|<AUI>

Scan|MRCONSO*|where <AUI> matches auis_nonupdatedSAB_moved.AUI
	src_atom_id|<SAB>|<SAB>/<TTY>|<CODE>|R|Y|A|<STR>|<SUPPRESS>|<SAUI>|<SCUI>|<SDUI>|<LAT>|needs_order_id|Y|<CUI>|<AUI>


# Keep the retained atom set consistent with every derived identity map.
# MetamorphoSys can retain obsolete CCS_2005 SRC metadata through the CCS_10
# source family. Allocate its historical IDs above, then exclude these atoms
# before generating maps, attributes, relationships and contexts.
Schema|classes_atoms.unfiltered.raw|SRC_ATOM_ID|SOURCE|TERMGROUP|CODE|STATUS|TOBERELEASED|RELEASED|ATOM_NAME|SUPPRESSIBLE|SOURCE_AUI|SOURCE_CUI|SOURCE_DUI|LANGUAGE|ORDER_ID|MOVED|CUI|AUI
Dest|classes_atoms.src

Scan|classes_atoms.unfiltered.raw|where <SOURCE> ne 'SRC' || <CODE> ne 'V-CCS_2005'
	<WholeLine>


# make AUI-to-src_atom_id mappings
Dest|aui_said_map

Schema|classes_atoms.src|SRC_ATOM_ID|SOURCE|TERMGROUP|CODE|STATUS|TOBERELEASED|RELEASED|ATOM_NAME|SUPPRESSIBLE|SOURCE_AUI|SOURCE_CUI|SOURCE_DUI|LANGUAGE|ORDER_ID|MOVED|CUI|AUI

Scan|classes_atoms.src
	<AUI>|<CUI>|<MOVED>|<SRC_ATOM_ID>

