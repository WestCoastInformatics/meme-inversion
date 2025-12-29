#!/usr/bin/perl
#
unshift(@INC,"$ENV{INV_HOME}/bin");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";

use strict 'vars';
use strict 'subs';
use open ':utf8';

use NLMConfig;
use Logger;

use Digest::MD5 qw(md5_hex);
use Encode qw(encode_utf8);
use NLMConfig;


use Getopt::Std;

my %options=();
getopts("d:", \%options);

my $topDir = ".";
if (defined $options{'d'}) {
    $topDir = $options{'d'};
} else {
    $topDir = ".";
}
my $iDir = "$topDir/src";
my $oDir = "$topDir/etc";


print "InputDir: $iDir\nOutputDir: $oDir\n\n";

########## UTILS
sub prDate {
    my $str = shift;
    my $dt = `date`;
    print "$str => $dt";
}

sub getSgType {
    my $typ = shift;

    if ($typ eq 'ROOT_SOURCE_CUI') { return 'RSCUI'; }
    elsif ($typ eq 'SOURCE_CUI') { return 'SCUI'; }
    elsif ($typ eq 'SOURCE_DUI') { return 'SDUI'; }
    elsif ($typ eq 'ROOT_SOURCE_DUI') { return 'RSDUI'; }
    elsif ($typ eq 'CODE_SOURCE') { return 'CODE'; }
    elsif ($typ eq 'CODE_ROOT_SOURCE') { return 'RCODE'; }
    elsif ($typ eq 'SOURCE_AUI') { return 'SAUI'; }
    elsif ($typ eq 'ROOT_SOURCE_AUI') { return 'RSAUI'; }
    elsif ($typ eq 'SRC_ATOM_ID' || $typ eq 'AUI' || $typ eq '') { return 'SAID'; }
    elsif ($typ eq 'SRC_REL_ID') { return 'RELID'; }
    elsif ($typ eq 'SOURCE_RUI') { return 'SRUI'; }
    elsif ($typ eq 'ROOT_SOURCE_RUI') { return 'RSRUI'; }

    return $typ;
}

# 1. find external auis/srcIds specified in the mergefacts file that are not defined
#    in the classes_atoms file.
#       => tDir/extIds.todb
my %vsab2sab = ();
my %sab2vsab = ();
my %thisSrcIds = ();
my %extIds = ();

my %vlScui = ();
my %vlSdui = ();
my %vlCode = ();
my %vlSaui = ();

sub checkId {
    my ($str, $id, $ql, $ckHash) = @_;
    if (($ql eq '' || defined($vsab2sab{"$ql"}) || defined($sab2vsab{"$ql"}))
	&& (defined($$ckHash{$id}))) {
	# valid id.
    } else {
	$extIds{"$str|$id|$ql"}++;
    }
}

sub genExtIds {

    my (@F, $srcId, $vsab, $rsab, $sab, $key);
    my ($id1, $id2, $ty1, $ty2, $ql1, $ql2, $sab1, $sab2);

    # first read valid sources.
    open (SRCS, "<:utf8", "$iDir/sources.src") or die "no $iDir/sources.src file. \n";
    while (<SRCS>) {
	chomp;
	next if /^\#/ || /^\s*$/;
	(@F) = split(/\|/, $_, 6);
	$vsab2sab{"$F[0]"} = $F[4];  # current source
	#$vsab2sab{"$F[1]"} = $F[4];  # previous version
	$sab2vsab{"$F[4]"} = $F[0];
    }
    $vsab2sab{'MTH'} = 'MTH';
    $vsab2sab{'SRC'} = 'SRC';
    $sab2vsab{'MTH'} = 'MTH';
    $sab2vsab{'SRC'} = 'SRC';
    close(SRCS);

    #####################################################################
    # collect all srcIds.
    open (IN, "<:utf8", "$iDir/classes_atoms.src")
	or die "no $iDir/classes_atoms.src  file. \n";

    while (<IN>) {
	chomp;
	next if /^\#/ || /^\s*$/;
	@F = split(/\|/, $_, 16);
	$thisSrcIds{"$F[0]"}++;
	$vlCode{$F[3]}++ if ($F[3] ne '');
	$vlSaui{$F[9]}++ if ($F[9] ne '');
	$vlScui{$F[10]}++ if ($F[10] ne '');
	$vlSdui{$F[11]}++ if ($F[11] ne '');
    }
    close(IN);
    prDate("\tDone with atoms: ");

    #################################
    # now read merge facts and note down any missing ids (auis as well as srcIds).

    open (IN, "<:utf8", "$iDir/mergefacts.src")
	or die "no $iDir/mergefacts.src  file. \n";

    while (<IN>) {
	chomp;
	next if /^\#/ || /^\s*$/;

	@F = split(/\|/, $_, 13);
	# check to see if the 1st id is in this srcIds
	$id1 = $F[0];
	$ty1 = $F[8];
	$ql1 = $F[9];
	$id2 = $F[2];
	$ty2 = $F[10];
	$ql2 = $F[11];

	next if ($ql1 eq 'SRC');
	if ($ty1 eq 'AUI') {
	    $extIds{"AUI|$id1"}++;
	} elsif ($ty1 eq 'SRC_ATOM_ID') {
	    if (!defined($thisSrcIds{"$id1"})) {
		$extIds{"SAID|$id1"}++;
	    }
	}
	# these are all external references.
	elsif ($ty1 eq 'SOURCE_AUI') {       checkId('SAV', $id1, $ql1, \%vlSaui ); }
	elsif ($ty1 eq 'ROOT_SOURCE_AUI') {  checkId('SAR', $id1, $ql1, \%vlSaui ); }
	elsif ($ty1 eq 'SOURCE_CUI') {       checkId('SCV', $id1, $ql1, \%vlScui ); }
	elsif ($ty1 eq 'ROOT_SOURCE_CUI') {  checkId('SCR', $id1, $ql1, \%vlScui ); }
	elsif ($ty1 eq 'SOURCE_DUI') {	     checkId('SDV', $id1, $ql1, \%vlSdui ); }
	elsif ($ty1 eq 'ROOT_SOURCE_DUI') {  checkId('SDR', $id1, $ql1, \%vlSdui ); }
	elsif ($ty1 eq 'CODE_SOURCE') {	     checkId('CDV', $id1, $ql1, \%vlCode ); }
	elsif ($ty1 eq 'CODE_ROOT_SOURCE') { checkId('CDR', $id1, $ql1, \%vlCode ); }
	else {
	    # error.
	    print "ERROR: unrcognized ty1: $ty1 in\n\t$_\n";
	}


	# now check to see if the 2nd id is in this srcIds
	next if ($ql2 eq 'SRC');
	if ($ty2 eq 'AUI') {
	    $extIds{"AUI|$id2"}++;
	} elsif ($ty2 eq 'SRC_ATOM_ID') {
	    if (!defined($thisSrcIds{"$id2"})) {
		$extIds{"SAID|$id2"}++;
	    }
	}

	# these are all external references.
	elsif ($ty2 eq 'SOURCE_AUI') {       checkId('SAV', $id2, $ql2, \%vlSaui ); }
	elsif ($ty2 eq 'ROOT_SOURCE_AUI') {  checkId('SAR', $id2, $ql2, \%vlSaui ); }
	elsif ($ty2 eq 'SOURCE_CUI') {		 checkId('SCV', $id2, $ql2, \%vlScui ); }
	elsif ($ty2 eq 'ROOT_SOURCE_CUI') {	 checkId('SCR', $id2, $ql2, \%vlScui ); }
	elsif ($ty2 eq 'SOURCE_DUI') {       checkId('SDV', $id2, $ql2, \%vlSdui ); }
	elsif ($ty2 eq 'ROOT_SOURCE_DUI') {	 checkId('SDR', $id2, $ql2, \%vlSdui ); }
	elsif ($ty2 eq 'CODE_SOURCE') {      checkId('CDV', $id2, $ql2, \%vlCode ); }
	elsif ($ty2 eq 'CODE_ROOT_SOURCE') { checkId('CDR', $id2, $ql2, \%vlCode ); }
	else {
	    # error.
	    print "ERROR: unregnized ty2: $ty2 in\n\t$_\n";
	}
    }
    close(IN);
    prDate("\tDone with merges: ");

    ##########################
    # now find missing info from relationships.src

    open (IN, "<:utf8", "$iDir/relationships.src")
	or die "no $iDir/relationships.src  file. \n";
    while (<IN>) {
	chomp;
	next if /^\#/ || /^\s*$/;
	@F = split(/\|/, $_, 19);
	$id1 = $F[2];
	$id2 = $F[5];
	$ty1 = $F[12];
	$ty2 = $F[14];
	$ql1 = $F[13];
	$ql2 = $F[15];

	# cases: AUI, SRC_ATOM_ID, CODE_SOURCE, SOURCE_AUI, SOURCE_CUI
	next if ($ql1 eq 'SRC');
	if ($ty1 eq 'AUI') {
	    $extIds{"AUI|$id1"}++;
	} elsif ($ty1 eq 'SRC_ATOM_ID') {
	    if (!defined($thisSrcIds{"$id1"})) {
		$extIds{"SAID|$id1"}++;
	    }
	}

	# these are external references.
	elsif ($ty1 eq 'SOURCE_AUI') {       checkId('SAV', $id1, $ql1, \%vlSaui ); }
	elsif ($ty1 eq 'ROOT_SOURCE_AUI') {  checkId('SAR', $id1, $ql1, \%vlSaui ); }
	elsif ($ty1 eq 'SOURCE_CUI') {       checkId('SCV', $id1, $ql1, \%vlScui ); }
	elsif ($ty1 eq 'ROOT_SOURCE_CUI') {  checkId('SCR', $id1, $ql1, \%vlScui ); }
	elsif ($ty1 eq 'SOURCE_DUI') {	     checkId('SDV', $id1, $ql1, \%vlSdui ); }
	elsif ($ty1 eq 'ROOT_SOURCE_DUI') {  checkId('SDR', $id1, $ql1, \%vlSdui ); }
	elsif ($ty1 eq 'CODE_SOURCE') {	     checkId('CDV', $id1, $ql1, \%vlCode ); }
	elsif ($ty1 eq 'CODE_ROOT_SOURCE') { checkId('CDR', $id1, $ql1, \%vlCode ); }
	else {
	    # error.
	    print "ERROR: unregnized ty1: $ty1 in\n\t$_\n";
	}

	next if ($ql2 eq 'SRC');
	if ($ty2 eq 'AUI') {
	    $extIds{"AUI|$id2"}++;
	} elsif ($ty2 eq 'SRC_ATOM_ID') {
	    if (!defined($thisSrcIds{"$id2"})) {
		$extIds{"SAID|$id2"}++;
	    }
	}

	# external references.
	elsif ($ty2 eq 'SOURCE_AUI') {       checkId('SAV', $id2, $ql2, \%vlSaui ); }
	elsif ($ty2 eq 'ROOT_SOURCE_AUI') {  checkId('SAR', $id2, $ql2, \%vlSaui ); }
	elsif ($ty2 eq 'SOURCE_CUI') {		 checkId('SCV', $id2, $ql2, \%vlScui ); }
	elsif ($ty2 eq 'ROOT_SOURCE_CUI') {	 checkId('SCR', $id2, $ql2, \%vlScui ); }
	elsif ($ty2 eq 'SOURCE_DUI') {       checkId('SDV', $id2, $ql2, \%vlSdui ); }
	elsif ($ty2 eq 'ROOT_SOURCE_DUI') {	 checkId('SDR', $id2, $ql2, \%vlSdui ); }
	elsif ($ty2 eq 'CODE_SOURCE') {      checkId('CDV', $id2, $ql2, \%vlCode ); }
	elsif ($ty2 eq 'CODE_ROOT_SOURCE') { checkId('CDR', $id2, $ql2, \%vlCode ); }
	else {
	    # error.
	    print "ERROR: unregnized ty2: $ty2 in\n\t$_\n";
	}
    }
    close(IN);
    prDate("\tDone with rels: ");


    ############################
    # now find missing info from attributes.src
    open (IN, "<:utf8", "$iDir/attributes.src")
	or die "no $iDir/attributes.src  file. \n";
    while (<IN>) {
	chomp;
	next if /^\#/ || /^\s*$/;

	@F = split(/\|/, $_, 15);
	$sab = $vsab2sab{"$F[5]"};
	$id1 = $F[1];
	$ty1 = $F[10];
	$ql1 = $F[11];

	# cases: AUI, SRC_ATOM_ID, CODE_SOURCE, SOURCE_AUI, SOURCE_CUI
	# NOTE: ROOT_?SOURCE_RUI are not needed as we cann't attribute to another
	# RUI belonging to another source or this source's previous version.
	next if ($ql1 eq 'SRC');
	if ($ty1 eq 'AUI') {
	    $extIds{"AUI|$id1"}++;
	} elsif ($ty1 eq 'SRC_ATOM_ID') {
	    if (!defined($thisSrcIds{"$id1"})) {
		$extIds{"SAID|$id1"}++;
	    }
	}

	# external references.
	elsif ($ty1 eq 'SOURCE_AUI') {       checkId('SAV', $id1, $ql1, \%vlSaui ); }
	elsif ($ty1 eq 'ROOT_SOURCE_AUI') {  checkId('SAR', $id1, $ql1, \%vlSaui ); }
	elsif ($ty1 eq 'SOURCE_CUI') {       checkId('SCV', $id1, $ql1, \%vlScui ); }
	elsif ($ty1 eq 'ROOT_SOURCE_CUI') {  checkId('SCR', $id1, $ql1, \%vlScui ); }
	elsif ($ty1 eq 'SOURCE_DUI') {	     checkId('SDV', $id1, $ql1, \%vlSdui ); }
	elsif ($ty1 eq 'ROOT_SOURCE_DUI') {  checkId('SDR', $id1, $ql1, \%vlSdui ); }
	elsif ($ty1 eq 'CODE_SOURCE') {	     checkId('CDV', $id1, $ql1, \%vlCode ); }
	elsif ($ty1 eq 'CODE_ROOT_SOURCE') { checkId('CDR', $id1, $ql1, \%vlCode ); }
	else {
	    # error.
	    print "ERROR: unregnized ty1: $ty1 in\n\t$_\n";
	}
    }
    close(IN);
    prDate("\tDone with attrs: ");

    # now find missing info from contexts.src
    open (IN, "<:utf8", "$iDir/contexts.src")
	or die "no $iDir/contexts.src  file. \n";
    while (<IN>) {
	chomp;
	next if /^\#/ || /^\s*$/;
	@F = split(/\|/, $_, 18);
	if (!defined($thisSrcIds{"$F[0]"})) { $extIds{"SAID|$F[0]"}++; }
	if (!defined($thisSrcIds{"$F[3]"})) { $extIds{"SAID|$F[3]"}++; }
    }
    close(IN);
    prDate("\tDone with cxts: ");

    # now save missing info.
    open (OUT, ">:utf8", "$oDir/ExtInfo") or die "no ExtInfo file. \n";
    foreach $key (keys %extIds) {
	print OUT "$key\n";
    }
    close(OUT);
}

prDate("Begin: ");
&genExtIds();
prDate("End: ");
