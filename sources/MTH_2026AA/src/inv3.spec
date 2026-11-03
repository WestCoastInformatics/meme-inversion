SourceDir|/local/content/MEME/MEME5/inv/sources/MTH_2026AA/src
SourceExt|.RRF
SourceFieldSep|BAR
SourceSchemaDefType|InThisSpec
Schema|MRCUI*|CUI1|VER|REL|RELA|MAPREASON|CUI2|MAPIN

DefineConst|MTHSAB|MTH_2026AA


# bequeathal relationships
Dest|bequeathal.relationships.src

Scan|MRCUI*|where (<VER> eq '2025AB') && <REL> eq 'RB'
	line_number|C|<CUI2>|BBT|<RELA>|<CUI1>|<const:MTHSAB>|<const:MTHSAB>|R|n|N|N|CUI_CURRENT||CUI_PREVIOUS||||

Scan|MRCUI*|where (<VER> eq '2025AB') && <REL> eq 'RN'
	line_number|C|<CUI2>|BNT|<RELA>|<CUI1>|<const:MTHSAB>|<const:MTHSAB>|R|n|N|N|CUI_CURRENT||CUI_PREVIOUS||||

Scan|MRCUI*|where (<VER> eq '2025AB') && <REL> eq 'RO'
	line_number|C|<CUI2>|BRT|<RELA>|<CUI1>|<const:MTHSAB>|<const:MTHSAB>|R|n|N|N|CUI_CURRENT||CUI_PREVIOUS||||

