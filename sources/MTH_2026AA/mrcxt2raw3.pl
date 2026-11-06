#!/usr/bin/perl

use File::Temp qw(tempfile);

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
# Publish only complete, valid context output. A failed mapping or sort must
# leave any earlier raw context artifact intact.
my ($temporary_handle, $temporary) = tempfile('.newsources.XXXXXX', DIR => 'raw3', UNLINK => 0);
close($temporary_handle) or die "Could not close temporary context file: $!\n";
open(RAW3, '|-', 'sort', '-T', '.', '-o', $temporary)
    or die "Could not start context sort: $!\n";
my $pipe_open = 1;
my $completed = eval {
    local $SIG{PIPE} = 'IGNORE';
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
        die "Unmapped MRCXT endpoint at line $.: SAB=$SAB CODE=$CODE CXL=$CXL AUI=$AUI AUI2=$AUI2\n"
            unless defined($said1) && $said1 =~ /^\d+$/ && $said1 > 0
                && defined($said2) && $said2 =~ /^\d+$/ && $said2 > 0;
        $ctype = $ctype{$SAB};
        $RELA = '' if $CXL eq 'SIB' && $SAB !~ /^UWDA/;
        print RAW3 "$said1|$number|$level|   0|$CXS|$said2|$CODE|$HCD\:\:~$said1~SRC_ATOM_ID~~$said2~SRC_ATOM_ID~|$RELA|$haschild|$SAB1|$SAB|$ctype|$ctype\n" or die "Could not write raw context: $!\n";
        }
    }


    my $sorted = close(RAW3);
    $pipe_open = 0;
    die "Context sort failed (status $?)\n" unless $sorted;
    rename($temporary, 'raw3/newsources.raw3')
        or die "Could not publish raw contexts: $!\n";
    1;
};
if (!$completed) {
    my $error = $@ || "Context generation failed\n";
    close(RAW3) if $pipe_open;
    unlink($temporary) if -e $temporary;
    die $error;
}
