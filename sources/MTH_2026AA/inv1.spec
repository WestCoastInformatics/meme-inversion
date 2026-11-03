SourceDir|/local/content/MEME/MEME5/inv/sources/MTHrelease
SourceExt|.RRF
SourceFieldSep|BAR
SourceSchemaDefType|InThisSpec
Schema|MRCONSO*|CUI|LAT|TS|LUI|STT|SUI|ISPREF|AUI|SAUI|SCUI|SDUI|SAB|TTY|CODE|STR|SRL|SUPPRESS|CVF|

Schema|vcodes_updated|CODE
Schema|sabs_updated_umls|SAB
Schema|auis_nonupdatedSAB_moved|AUI|CUI

# classes_atoms
Dest|classes_atoms.src

Schema|class_src|SRC_ATOM_ID|SOURCE|TERMGROUP|CODE|STATUS|TOBERELEASED|RELEASED|ATOM_NAME|SUPPRESSIBLE|SOURCE_AUI|SOURCE_CUI|SOURCE_DUI|LANGUAGE|ORDER_ID|MOVED|CUI|AUI

Scan|class_src
	<WholeLine>||

Scan|MRCONSO*|where <SAB> matches sabs_updated_umls || (<SAB> eq 'SRC' && ((<TTY> !~ /^R/ && <TTY> ne 'SSN') || <CODE> matches vcodes_updated.CODE ))
	src_atom_id|<SAB>|<SAB>/<TTY>|<CODE>|R|Y|A|<STR>|<SUPPRESS>|<SAUI>|<SCUI>|<SDUI>|<LAT>|needs_order_id|N|<CUI>|<AUI>

Scan|MRCONSO*|where <AUI> matches auis_nonupdatedSAB_moved.AUI
	src_atom_id|<SAB>|<SAB>/<TTY>|<CODE>|R|Y|A|<STR>|<SUPPRESS>|<SAUI>|<SCUI>|<SDUI>|<LAT>|needs_order_id|Y|<CUI>|<AUI>


# make AUI-to-src_atom_id mappings
Dest|aui_said_map

Schema|classes_atoms.src|SRC_ATOM_ID|SOURCE|TERMGROUP|CODE|STATUS|TOBERELEASED|RELEASED|ATOM_NAME|SUPPRESSIBLE|SOURCE_AUI|SOURCE_CUI|SOURCE_DUI|LANGUAGE|ORDER_ID|MOVED|CUI|AUI

Scan|classes_atoms.src
	<AUI>|<CUI>|<MOVED>|<SRC_ATOM_ID>

