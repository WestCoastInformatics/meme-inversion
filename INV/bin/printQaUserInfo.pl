#!/usr/bin/perl

# Doc info
print "\nDoc related\n";
print "\tAttributeName => DOC_ATN|$atn\n";
print "\tRelationName  => DOC_REL|$rel\n";
print "\tRelaName      => DOC_RELA|$rela\n";
print "\tTtyName       => DOC_TTY|$tty\n";

# source info
print "\nSource related\n";
print "\tVsab          => SRC_VSAB|$vsb\n";
print "\tRsab          => SRC_RSAB|$rsb\n";
print "\tVsab2Rsab     => SRC_V2R|$vsb|$rsb\n\n";
print "\tlanguage     => LANGUAGE|$lan\n\n";

# termgroup info
print "\nTermgroup related\n";
print "\tTermgroup     => TG|$tg\n";
print "\tTG2Suppress   => TGSP|$tg|$sup\n";

# atom info
print "\nAtom related\n";
print "\tSaid          => SAID|$said\n";
print "\tCodeVsab      => CDV|$cd|$vsab\n";
print "\tCodeRsab      => CDR|$cd|$rsab\n";
print "\tCodeVsabTG    => CDVTG|$cd|$vtg\n";
print "\tCodeRsabTG    => CDRTG|$cd|$rtg\n";
print "\tSauiVsab      => SAV|$saui|$vsab\n";
print "\tSauiRsab      => SAR|$saui|$rsab\n";
print "\tScuiVsab      => SCV|$scui|$vsab\n";
print "\tScuiRsab      => SCR|$scui|$rsab\n";
print "\tSduiVsab      => SDV|$sdui|$vsab\n";
print "\tSduiRsab      => SDR|$sdui|rsab\n";
print "\tSourceAtomCds => SATOM|(RPT|VPT)|$cd\n";

# Relationship/Context info
print "\nRel/Cxt related\n";
print "\tRelId         => RID|$relId\n";
print "\tSruiVsab      => RUIV|$srui|$vsab\n";
print "\tSruiRsab      => RUIR|$srui|$rsab\n";


