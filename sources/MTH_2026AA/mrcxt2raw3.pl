#!/usr/bin/perl

open (SOURCES, "sabs_updated_umls") || die "can't open sabs_updated_umls\n";
while (<SOURCES>) {
    chomp;
    $updated{$_}=1;
}

open (MRSAB, "Meta/MRSAB.RRF") || die "can't open Meta/MRSAB.RRF\n";
while (<MRSAB>) {
    ($vcui,$rcui,$vsab,$rsab,$son,$sf,$sver,$vstart,$vend,$imeta,$rmeta,$slc,$scc,$srl,$tfr,$cfr,$cxty,$ttyl,$atnl,$lat,$cenc,$curver,$sabin,$ssn,$scit) = split(/[|\n]/);
    if ($updated{$vsab} && $cxty ne '') {
	$keep{$vsab} = 1;
	$ctype{$vsab} = ($cxty =~ /NOSIB/) ? 0 : 1;
    }
}

open (TREETOPS, "src-root.cuis.updated") || die "can't open src-root.cuis.updated\n";
while (<TREETOPS>) {
    chomp;
    $istreetop{$_}=1;
}

open(AUIS, "aui_said_map") || die "can't open aui_said_map\n";
while (<AUIS>) {
    ($AUI, $CUI, $said) = split(/[|\n]/);
    $said{$AUI} = $said;
}

# level codes
$lev{'CCP'}=50;
$lev{'SIB'}=60;
$lev{'CHD'}=99;

open (MRCXT, "Meta/MRCXT.RRF") || die "can't open Meta/MRCXT.RRF\n"; 
open (RAW3, "|sort -T . -o raw3/newsources.raw3") || die "can't create raw3/newsources.raw3\n";

while (<MRCXT>) {
    ($CUI,$SUI,$AUI,$SAB,$CODE,$CXN,$CXL,$RNK,$CXS,$CUI2,$AUI2,$HCD,$RELA,$XC,$CVF)=split(/[|\n]/);
    if ($keep{$SAB}) {
	next if ($SAB =~ /^MSH/ && $CODE =~ /^C/);
	$SAB1 = ($istreetop{$CUI}) ? "SRC" : $SAB;
	$level = ($CXL eq "ANC") ? sprintf("%2d",$RNK) : $lev{$CXL};
	$number=sprintf("% 4d",$CXN);
	$haschild = ($XC eq '+' || $CXL eq 'ANC') ? 1 : 0;
	$said1 = $said{$AUI};
	$said2 = $said{$AUI2};
	$ctype = $ctype{$SAB};
	$RELA = '' if $CXL eq 'SIB' && $SAB !~ /^UWDA/;
	print RAW3 "$said1|$number|$level|   0|$CXS|$said2|$CODE|$HCD\:\:~$said1~SRC_ATOM_ID~~$said2~SRC_ATOM_ID~|$RELA|$haschild|$SAB1|$SAB|$ctype|$ctype\n";
    }
}

# wait for sort to complete before exiting!
close(RAW3);
