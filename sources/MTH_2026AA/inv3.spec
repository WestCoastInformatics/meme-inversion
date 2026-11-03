SourceDir|/local/content/MEME/MEME5/inv/sources/MTHrelease
SourceExt|.RRF
SourceFieldSep|BAR
SourceSchemaDefType|InThisSpec
Schema|MRCUI*|CUI1|VER|REL|RELA|MAPREASON|CUI2|MAPIN

DefineConst|MTHSAB|MTHrelease


# bequeathal relationships
Dest|bequeathal.relationships.src

Scan|MRCUI*|where (<VER> eq 'prevrel1') && <REL> eq 'RB'
	line_number|C|<CUI2>|BBT|<RELA>|<CUI1>|<const:MTHSAB>|<const:MTHSAB>|R|n|N|N|CUI_CURRENT||CUI_PREVIOUS||||

Scan|MRCUI*|where (<VER> eq 'prevrel1') && <REL> eq 'RN'
	line_number|C|<CUI2>|BNT|<RELA>|<CUI1>|<const:MTHSAB>|<const:MTHSAB>|R|n|N|N|CUI_CURRENT||CUI_PREVIOUS||||

Scan|MRCUI*|where (<VER> eq 'prevrel1') && <REL> eq 'RO'
	line_number|C|<CUI2>|BRT|<RELA>|<CUI1>|<const:MTHSAB>|<const:MTHSAB>|R|n|N|N|CUI_CURRENT||CUI_PREVIOUS||||

