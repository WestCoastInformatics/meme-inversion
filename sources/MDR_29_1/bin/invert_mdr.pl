#!/usr/bin/perl
#

#----------------------------------------
# Configure libraries
#----------------------------------------

use FindBin qw($Bin);
use lib "$ENV{INV_HOME}/lib";
use lib "$Bin/../lib";
use strict 'vars';
use strict 'subs';

use NLMInv;
use SrcBldr;
use Atom;
use Attribute;
use Relation;
use Merge;
use Context;
use iutl;
use Brit2Amer;
use Carp;

our $cfgFile;
our $Inv;
our $Log;
our $Cfg;
our $Hier;
our $LvgProg;

#---------------------
# constant data
#--------------------
our $vsab = 'NONE';
our $rsab = 'NONE';

# abritish to american translation class.
our $br2am;

our %icdCodes=();
our %cstCodes=();
our %cstUCd2TG = ();
our %whoUCd2TG = ();

our ($xmAtom, $osAtom, $abAtom, $hgAtom, $htAtom, $ptAtom, $ltAtom, $olAtom, $smqAtom);
our ($mthAtom, $genAtom);
our ($Attr, $ctgAttr, $smqtlAttr, $smqrAttr, $smqctAttr, $xmAttr, $mtstyAttr, $cxtAttr);
our ($ptltMerge, $exMerge, $aeMerge, $osabMerge);
our ($icd9cmRel, $cstRel, $whoRel, $ptlltRel, $smqRel, $smqrevRel, $aeRel, $exRel, $osabRel);
our ($parCxt, $sibCxt, $rootCxt);
our ($icdXmCd, $cstXmCd);
our ($genAtom, $smqDefAttr, $smqSosAttr, $engMrg, $engRel, $ascMrg, $ascRel);
our ($langMode, $dataEncode);

our %nmSdui2Said=();
our %mth_nmSdui2Said=();
our %atomNames=();
our %amNames = ();
our %exNames = ();
our %cdTty2said=();
our %cd2eng=();

our $invIcd=0;
our $invWho=0;
our $invCst=0;
our %said2name = ();
our %said2sgid=();
our %ptCd2Nm = ();

#----------------------------------------
# Process Options
#----------------------------------------
use Getopt::Std;

my %options=();
getopts("c:hsl:", \%options);

if (defined $options{h}) {
  print "\n\tThis script inverts MedDRA English and translations (except MedDRA Japan) and produces the standard files.\n\n";
  print "\tTo check the prerequisitie properties\n";
  print "\t\tinvert_mdr.pl -c mdr11.cfg \n";
  print "\t\tinvert_mdr.pl -c mdr_spa.cfg \n\n";
  print "\tHow to run MedDRA English \n";
  print "\t\tinvert_mdr.pl\n";
  print "\t\tThis generates all the standard output files.[~ 6 min]\n\n";
  print "\tHow to run MedDRA transalations ( Example - MedDRA Spanish) \n";
  print "\t\tinvert_mdr.pl -l spa\n";
  print "\t\tThis generates all the standard output files.[~ 6 min]\n";

  print "\tOptions:\n";
  print " \t -h:   Prints this help message\n";
  print " \t -c:   To check the Prerequisites\n";
  print " \t -l:   To run MedDra translations\n\n";
  print " \t -s:   To create default STYs\n\n";

  exit 0;
}

if (defined $options{c}) {
   &checkPrerequisites;
}
# This is to find valid codes in these sources so we can check if the
# code exists before making a relation between mdr and these.
# This is done once and the valid codes are saved on disk.
#sub readMapInfo {
#  my ($ign, $cd, $ucd, $said, $src, $tg, $nm);
#  # first read valid icd9cm and costart codes.
#  open(ICDCLS, "$dataEncode", $$Cfg->getEle("File.INP.ICDCls"))
#    or die "Could not open File.INP.ICDCls.\n";
#  while(<ICDCLS>) {
#    chomp;
#    ($said, $src, $tg, $cd) = split(/\|/, $_);
#    $icdCodes{"$cd"}++ if ($tg =~/^ICD9CM/);
#  }
#  close(ICDCLS);

#  open (CSTCLS, "$dataEncode", $$Cfg->getEle("File.INP.COSTARCls"))
#    or die "Could not open File.INP.COSTARCls.\n";
#  while (<CSTCLS>) {
#    chomp;
#    ($said, $src, $tg, $cd, $ign, $nm) = split(/\|/, $_);
#    $cstCodes{"\U$cd"}++;
#    $cstUCd2TG{"\U${cd}"} = "$tg" if ($tg =~ /PT/);
#
#  }
#  close(CSTCLS);

#  open (WHOCLS, "$dataEncode", $$Cfg->getEle("File.INP.WHOARTCls"))
#    or die "Could not open File.INP.WHOARTCls.\n";
#  while(<WHOCLS>) {
#    chomp;
#    ($said, $ign, $tg, $cd, $ign, $nm) = split(/\|/, $_);
#    $cd = substr($cd, 0, 4);
#    push(@{$whoUCd2TG{"$cd"}}, "$tg") if ($tg =~ /[HP]T$/);
#}
#  close(WHOCLS);
#} #end of readMapInfo subroutine 


# If a string has any expansion, we create a corresponding MTH atom.
# This method creates subroutine with the list of abbreviations which 
# needs to be
# expanded. The list of abbreviations and their expand form are read from 
# external file, ../etc/MG_Abbreviations

sub make_expandAbbr {
  my ($abbr, $expnd, $expand, $strSub);

 if ($langMode eq 'ENG') {  
  open (IN, "$dataEncode", $$Cfg->getEle('File.INP.ABBRS'))
        or die "Couldn't open ABBREVS file for \n";
      
    $expand = '';
    $strSub = ' my($str) = @_;'."\n";
      while (<IN>) {
      chomp;
      next if (/^#/ );
      next if(/^ *$/);
      next if(/^$/);
      ($abbr, $expnd) = split(/\&\&/);
      $strSub.= "   \$str =~ s#$abbr#$expnd#g;\n";
    }
    close(IN);
    $strSub.= "    return \$str;\n";
    eval "sub expandAbbr {\n$strSub\n}";
 }
}
  

  sub init {
  # create a main generator with proper seeds.
  $rsab = $$Cfg->getEle('RSAB');
  $vsab = $$Cfg->getEle('VSAB');
  $br2am = new Brit2Amer();

  # make print templates
  # ATOM templates
  $xmAtom = new Atom('Atom.XM');
  $osAtom = new Atom('Atom.OS');
  $hgAtom = new Atom('Atom.HG');
  $htAtom = new Atom('Atom.HT');
  $ptAtom = new Atom('Atom.PT');
  $ltAtom = new Atom('Atom.LT');
  $olAtom = new Atom('Atom.OL');
  $abAtom = new Atom('Atom.AB');
  $smqAtom = new Atom('Atom.SMQ');
  $mthAtom = new Atom();
  
  #Foreign translations Merges/Rels
  $genAtom = new Atom();
  $engMrg = new Merge('Merge.ENG');
  $ascMrg = new Merge('Merge.ASC');
  $engRel = new Relation('Relation.ENG');
  $ascRel = new Relation('Relation.ASC');
  $osabRel = new Relation('Relation.OSAB');

  # Attribute templates
  $Attr = new Attribute('Attribute.Atom');
  $ctgAttr = new Attribute('Attribute.CTG');
  $smqtlAttr =  new Attribute('Attribute.SMQTL');
  $smqrAttr = new Attribute('Attribute.SMQR');
  $smqctAttr = new Attribute('Attribute.SMQCT');

  $xmAttr = new Attribute('Attribute.XM');
  $mtstyAttr = new Attribute('Attribute.STY');
  #$mtstyAttr = new Attribute('Attribute.MTSTY');
  $cxtAttr = new Attribute('Attribute.CXT');

  # Merge templates
  $ptltMerge = new Merge('Merge.PTLT');
  $exMerge = new Merge('Merge.EX');
  $aeMerge = new Merge('Merge.AE');
  $osabMerge = new Merge('Merge.OSAB');

  # Relation templates
  $icd9cmRel = new Relation('Relation.ICD9CM');
  $cstRel = new Relation('Relation.CST');
  $whoRel = new Relation('Relation.WHO');
  $ptlltRel = new Relation('Relation.PTLLT');
  $smqRel = new Relation('Relation.SMQ');
  $smqrevRel = new Relation('Relation.SMQREV');
  $aeRel = new Relation('Relation.AE');
  $exRel = new Relation('Relation.EX');

  # Context templates.
  $rootCxt = new Context('Context.ROOT'); 
  $parCxt = new Context('Context.PAR');
  $sibCxt = new Context('Context.SIB');
  
  &make_expandAbbr;
}

# uses the global hases: icdCodes and cstCodes.
# takes tty, string, code, whoartCd, hartsCd, costartCd, icd9Cd, icd9cmCd,
#                          icd10Cd, jartCd
our %seenCstRel=();
sub dumpCodes {
  my ($srcAtomId, $tty, $nm, $cd, $wcd, $hcd, $ccd, $icd, $i9cd,
      $i10cd, $jcd) = @_;
  # create mapping attributes

  # -----------
  # whoart code: 'CROSS_REFERENCE' attr, cd -> wcd rel
#  my ($whoCdName, $ucd, $ttg, $tcd);
#  if ($wcd ne '') {
    # create whoart code from its code and name: First 4 chars of code and 
    # upper case name joined by "_". Dump this as ATN=CROSS_REFERENCE 
#    $whoCdName = substr($wcd,0,4);
#    $ctgAttr->dumpAttr({sgId => $srcAtomId, atn => 'CROSS_REFERENCE', atv => "WHOART: $wcd"});
    
   # if it is a valid whoart code, dump rel.
#   if ($langMode eq 'ENG') {
#    if (defined($whoUCd2TG{"$whoCdName"})) {
#      foreach $tcd (@{$whoUCd2TG{"$whoCdName"}}) {
        # we may need to dump this at src_atom_id level instead of code_source
      	#$whoRel->dumpRel({sgId1 => $cd, sgId2 => $whoCdName});  # Pending
#	$whoRel->dumpRel({sgId1 => $srcAtomId, sgId2 => $whoCdName});  # Pending
#      }
#    } else {
#      $$Log->logWarning("Invalid WHO code: <$whoCdName>. Skipping...\n");
#      $invWho++;
#    }
#   }
#  }

  # hart code: 'CROSS_REFERENCE' attr
#  $ctgAttr->dumpAttr({sgId => $srcAtomId, atn => 'CROSS_REFERENCE', atv => "HARTS: $hcd"}) if ($hcd ne '');

  # costar code: 'CROSS_REFERENCE' attr, mapAttr (XMAPFROM, XMAPTO, XMAP), 
  #              cd -> ccd rel (no duplicates)
  #if ($ccd ne '' && $ccd ne 'N') {
  #  $ctgAttr->dumpAttr({sgId => $srcAtomId, atn => 'CROSS_REFERENCE', atv => "COSTART: $ccd"});
#
    # dump its map attribute
    #&dumpMapAttr($cstXmCd, $cd, $ccd) if ($langMode eq 'ENG') ; #Pending
    
#   if ($langMode eq 'ENG') {
#    if (defined($cstCodes{"$ccd"})) {
#      # find unique code ie., code_string
#      $ucd = "\U$ccd";
#      if (defined($cstUCd2TG{"$ucd"})) {
#	$ttg = $cstUCd2TG{"$ucd"};
#	if (!defined($seenCstRel{"$cd|$tty|$ucd|$ttg"})) {
#	  $cstRel->dumpRel({sgId1 => $srcAtomId,  sgId2 => $ccd});
#	  $seenCstRel{"$cd|$tty|$ucd|$ttg"}++;
#	}
#      }
#    } else {
#      $$Log->logWarning("Invalid CST code: <$ccd>. Skipping...\n");
#      $invCst++;
#    }
#   }
#  }

  # ---------
  # icd9 code: 'CROSS_REFERENCE' attr
  #$ctgAttr->dumpAttr({sgId => $srcAtomId, atn => 'CROSS_REFERENCE', atv => "ICD9: $icd"}) if ($icd ne '');

  # -----------
  # icd9cm code: 'CROSS_REFERENCE' attr, mapAttr (XMAPFROM, XMAPTO, XMAP), rel (cd->i9cd)
#  if ($i9cd ne '') {
#    $ctgAttr->dumpAttr({sgId => $srcAtomId, atn => 'CROSS_REFERENCE', atv => "ICD9CM: $i9cd"});
    # dump its map attribute
    #&dumpMapAttr($icdXmCd, $cd, $i9cd) if ($langMode eq 'ENG') ; # Pending

#    if ($langMode eq 'ENG') {  
    # if icd9cm code is valid, create a rel
#    if (defined($icdCodes{"$i9cd"})) {
#      $icd9cmRel->dumpRel({sgId1 => $srcAtomId, sgId2 => $i9cd});
#    } else {
#      $$Log->logWarning("Invalid ICD code: <$i9cd>. Skipping...\n");
#      $invIcd++;
#    }
#    }
#  }

  # ------------
  # icd10cm code: 'CROSS_REFERENCE' attr
#  $ctgAttr->dumpAttr({sgId => $srcAtomId, atn => 'CROSS_REFERENCE', atv => "ICD10: $i10cd"}) if ($i10cd ne '');

  # ---------
  # jart code: 'CROSS_REFERENCE' attr
#  $ctgAttr->dumpAttr({sgId => $srcAtomId, atn => 'CROSS_REFERENCE', atv => "J-ART: $jcd"}) if ($jcd ne '');

}

# dump map nodes (XM) from info supplied in cfg file (via the Map.tag)
#sub dumpMapNode {
#  my $tag = shift;
#  my $mapRef = $$Cfg->getHashRef("Map.$tag");
#  # check for required elements.
#  my ($key, $val, $go);
#  $go = 1;
#  foreach $key ('MAPSETVSAB', 'MAPSETRSAB', 'FROMVSAB', 'FROMRSAB',
#	       'TOVSAB', 'TORSAB', 'MAPSETVERSION', 'CODE', 'MAPSETTYPE') {
#    if (!defined($$mapRef{"$key"})) {
#      $$Log->logError("Required element <Map.$tag.$key> is not present.\n");
#      $go = 0;
#    }
#  }
#  if ($go != 1) {
#    $$Log->logError("Correct the mistakes and rerun.\n");
#    exit;
#  }
#
#  # now create the atom.
#  my $code = $$mapRef{'CODE'};
#  my $lastId = $xmAtom->dumpAtom({code => $code, sdui => '',
#				  str => $$mapRef{'MAPSETNAME'}});
#
#  #now dump all attributes.
#  $mtstyAttr->dumpAttr({sgId => $code, atv => 'Intellectual Product',
#			sgQual => "$vsab"});
#  foreach $key ('MAPSETVSAB', 'MAPSETRSAB', 'FROMVSAB', 'FROMRSAB',
#		'TOVSAB', 'TORSAB', 'MAPSETVERSION', 'MTH_MAPSETCOMPLEXITY',
#		'MTH_MAPFROMCOMPLEXITY', 'MTH_MAPTOCOMPLEXITY',
#		'MTH_MAPFROMEXHAUSTIVE', 'MTH_MAPTOEXHAUSTIVE', 
#		'FROMTYPE', 'TOTYPE', 'SMQ_NOTE', 'MAPSETSID', 'FROMRULE',
#		'TORULE', 'MAPSETTYPE',
#		'MTH_UMLSMAPSETSEPARATOR', 'MAPSETXRTARGETID',
#		'MAPSETSCHEMENAME', 'MAPSETSCHEMEID', 'MAPSETSCHEMEVERSION',
#		'MAPSETREALMID', 'MAPSETRULETYPE', 'TARGETSCHEMEID') {
#    $val = $$mapRef{"$key"};
#    if ($val ne '') {
#      $xmAttr->dumpAttr({sgId => $code, atn => $key, atv => $val});
#    }
#  }
#  return $lastId;
#}

#our %dupAttrs_IFT=();
#our %dupAttrs_IF=();
#our %dupAttrs_IT=();
# remember to avoid duplicates.
#sub dumpMapAttr {
#  my $id = shift;
#  my $from = shift;
#  my $to = shift;
#
#  if (!defined($dupAttrs_IF{"$id|$from"})) {
#    $dupAttrs_IF{"$id|$from"}++;
#    $xmAttr->dumpAttr({sgId => $id, atn => 'XMAPFROM',
#		       atv => "$from~~$from~CODE~~"});
#  }
#  if (!defined($dupAttrs_IT{"$id|$to"})) {
#    $dupAttrs_IT{"$id|$to"}++;
#    $xmAttr->dumpAttr({sgId => $id, atn => 'XMAPTO',
#		       atv => "$to~~$to~CODE~~"});
#  }
#  if (!defined($dupAttrs_IFT{"$id|$from|$to"})) {
#    $dupAttrs_IFT{"$id|$from|$to"}++;
#    $xmAttr->dumpAttr({sgId => $id, atn => 'XMAP',
#		       atv => "~~$from~RQ~mapped_to~$to~~~~~~"});
#  }
#}

# for a given string, we can create its expanded form, american form if they
# are different from the original string.
sub makeOtherAtoms {
  my $name = shift;
  my $code = shift;
  my $tty = shift;
  my $said = shift;
  my $sdui = $code;
  $sdui = shift if (@_ > 0);
  my ($exNm, $amNm);

  # get expanded name if any and remember.
  # $exNm = &expandIt($name);
  $exNm = iutl->cleanLine(&expandAbbr($name)); # Ratnakar

  if ($exNm ne $name) {
    substr($exNm, 0, 1) =~tr/a-z/A-Z/;
    push(@{$exNames{"$tty|$exNm"}}, "$code|$sdui|$said");
  }

  # check if it has american name.
  $amNm = $br2am->b2a("$name");
  push(@{$amNames{"$tty|$amNm"}}, "$code|$sdui|$said")
    if (uc($amNm) ne uc($name));
}

our %ptltlocds=();
sub   processMDR {
  if ($langMode eq 'ENG') { &processMDR_All; }
 # else { &processMDR_FL; }
 else { &processMDR_All; 
            &processMDR_FL;}
}


sub readFLInfo {
  my $outFile = shift;
  
  
  open(OUT, ">:utf8", "$outFile")
    or die "Could not open ${langMode}_atoms\n";

  my ($ign, $tty, $fl, $cd, $nm, $ptcd, @codes, $current, $des, $nt);

  ## now read SOC/HLGT/HLT/PT file and get their atoms.
  my %ttyFl = (OS => 'SOC', HG => 'HLGT', HT => 'HLT', PT => 'PT');
  while (($tty, $fl) = each %ttyFl) {
    open(IN, "$dataEncode", $$Cfg->getEle("File.INP.$fl"))
      or die "Could not open File.INP.$fl\n";
    while (<IN>) {
      chomp;
        s/\$/\|/g; # Replace delimiter to '|'
      ($cd, $nm) = split(/\|/, iutl->cleanLine($_));
      print OUT "name|$tty|$cd|$cd|$nm\n";
    }
    close(IN);
  }

  ## now process LLT/OL terms.
  open(IN, "$dataEncode", $$Cfg->getEle("File.INP.LT"))
    or die "Could not open File.INP.LT.\n";
  while (<IN>) {
    chomp;
    s/\$/\|/g; # Replace delimiter to '|'
    ($cd, $nm, $ptcd, @codes) = split(/\|/, iutl->cleanLine($_));

    # 7th one in codes is currency. Note that and remove it from codes.
    $current = splice(@codes, 6, 1);

    # now create the atom and its attributes, and rel to PT.
    if ($current eq 'Y') { $tty = 'LLT'; } else { $tty = 'OL'; }
    # proces it here.
    print OUT "name|$tty|$cd|$ptcd|$nm\n";
  }
  close(IN);

  ## now process SMQ list
  open(IN, "$dataEncode", $$Cfg->getEle('File.INP.SMQL'))
    or die "Could not open File.INP.SMQL.\n";
  while (<IN>) {
    chomp;
    s/\$/\|/g; # Replace delimiter to '|'
    ($cd, $nm, $ign, $des, $ign, $nt) = split(/\|/, iutl->cleanLine($_));
    $des = iutl->stripBlanks($des, 1);
    $nt = iutl->stripBlanks($nt, 1);
    # process $nm, $nt.
    print OUT "name|SMQ|$cd|$cd|$nm\n";
    print OUT "sos|SMQ|$cd|$cd|$nt\n" if ($nt ne '');
    print OUT "def|SMQ|$cd|$cd|$des\n" if ($des ne '');
  }
  close(IN);
  close(OUT);
  $$Log->logIt("Done reading info - " . `date` . "\n");
}

sub runLVG {
  my ($ifile, $ofile) = @_;
  # now call LVG and write them to $landMode_atoms_LVG
  my $LvgProg = $$Cfg->getEle('LVGProg');
  `$LvgProg -f:q5 -t:5 -F:1:2:3:4:5:6 < $ifile > $ofile`;
  $$Log->logIt("Done with lvg - " . `date` . "\n");
}

sub processMDR_FL {
  my $tempDir = $$Cfg->getEle('TEMPDIR', "../tmp");
  my $lvgInFile = "$tempDir/${langMode}_atoms";
  my $lvgOutFile = "$tempDir/${langMode}_atoms_lvg";
  my %engCdTty2Tg=();
  my %lvgTagCdSduiTty2Str=();
  my ($ign, $tg, $tty, $cd, $tag, $sdui, $nm, $newNm, $etg, $lstId);
  # read information from files
  &readFLInfo($lvgInFile);

  # run lvg
  &runLVG($lvgInFile, $lvgOutFile);


  # first read valid eng code, tty, and termgrup. ignore mth ttys.
  open(IN, "<:utf8", $$Cfg->getEle("File.INP.ENGCLS"))
    or die "Could not open File.INP.ENGCLS to read eng atoms.\n";
  while(<IN>) {
    chomp;
    ($ign, $ign, $tg, $cd) = split(/\|/, $_);
    ($ign, $tty) = split(/\//, $tg);
    $engCdTty2Tg{"$cd|$tty"} = $tg unless ($tty =~ /MTH/);
  }
  close(IN);


  # process all lang atoms.
  open (IN, "<:utf8", $lvgOutFile) or die "Could not open $lvgInFile\n";
  while(<IN>) {
    chomp;
    ($tag, $tty, $cd, $sdui, $nm, $newNm) = split(/\|/,$_);
    if ($tag eq 'name') {
      if ($langMode eq 'SPA') {      
      if ($nm ne $newNm) {
	$lstId = $genAtom->dumpAtom({code => $cd, sdui => $sdui,
			    str => $newNm, suppress => $tty eq 'OL' ? 'O':'N',
			    tty => "MTH_$tty", lat => $langMode});
	
	# create merges and rels from lvg atoms
#	$ascMrg->dumpMerge({sgId1 => $cd, sgQual1 => "$vsab/$tty",
#			    sgId2 => $cd, sgQual2 => "$vsab/MTH_$tty"});
	$ascMrg->dumpMerge({sgId1 => $cdTty2said{"$cd|$tty"}, 
			    sgId2 => $lstId});			    
#	$ascRel->dumpRel({sgId1 => $cd, sgQual1 => "$vsab/$tty",
#			  sgId2 => $cd, sgQual2 => "$vsab/MTH_$tty"});
  	$ascRel->dumpRel({sgId1 => $cdTty2said{"$cd|$tty"},
			  sgId2 => $lstId});
	
      }
      }
   # create merges and rels from Eng atoms
      if (defined($engCdTty2Tg{"$cd|$tty"})) {
	$etg = $engCdTty2Tg{"$cd|$tty"};
#	$engMrg->dumpMerge({sgId1 => $cd, sgQual1 => $etg,
#			    sgId2 => $cd, sgQual2 => "$vsab/$tty"});
#	$engRel->dumpRel({sgId1 => $cd, sgQual1 => $etg,
#			  sgId2 => $cd, sgQual2 => "$vsab/$tty"});
        if (!defined $cd2eng{"$cd"}) {
	$cd2eng{"$cd"}++;
	$engMrg->dumpMerge({sgId1 => $cd, sgId2 => $cd});
	$engRel->dumpRel({sgId1 => $cd, sgId2 => $cd});
	}		  
      }

    } 
    elsif (($tag eq 'sos') && ($langMode eq 'SPA')) {
    #  # create sos attribute
    #  $smqSosAttr->dumpAttr({sgId => $cd, atv => $nm, sgQual => "$vsab/$tty"});
    #   # create mth sos if any.
      if ($nm ne $newNm) {
      # $smqSosAttr->dumpAttr({sgId => $cd, sgQual => "$vsab/$tty",
      #			       atv => $newNm});
       $smqctAttr->dumpAttr({sgId => $cd, atn => 'MTH_SMQ_NOTE', atv => $newNm}) 
      }
   # } elsif ($tag eq 'def') {
   #   # create definition attribute.
   #   $smqDefAttr->dumpAttr({sgId => $cd, atv => $nm, sgQual => "$vsab/$tty"});
   #   # for some reason we do not use the 7bit defs.
    }
 }
}

sub   processMDR_All {
  ## read valid codes.
  my %cstCodes = ();		# icdCodes: valid icd9cm codes
  my %icdCodes = ();		# cstCodes: valid costar codes
  my %ordSOC = ();		# ordSoc: socid 2 socorder

  #if ($langMode eq 'ENG') {
    # this reads the valid codes from files and saves them the 
  # global hases: icdCodes and cstCodes.
  #&readMapInfo();

  ## create XM atoms for icd9cm and costar and its attributes.
  #my $icdXmSaid = &dumpMapNode('ICD9CM');
  #my $cstXmSaid = &dumpMapNode('CST');
  #$icdXmCd = $$Cfg->getReqEle('Map.ICD9CM.CODE');
  #$cstXmCd = $$Cfg->getReqEle('Map.CST.CODE');
  #}
  
  ## read ordered soc and create soc atoms.
  # first read ordered socs.
  my ($socOrd, $socId);
  open(IN, "$dataEncode", $$Cfg->getEle("File.INP.ISOC"))
    or die "Could not open File.INP.ISOC.\n";
  while (<IN>) {
    chomp;
    ($socOrd, $socId) = split(/\$/, $_);
    $ordSOC{"$socId"} = $socOrd;
  }
  close(IN);

  ## now read socs file and create atoms/attrs/rels
  open(IN, "$dataEncode", $$Cfg->getEle("File.INP.SOC"))
    or die "Could not open File.INP.SOC.\n";
  my ($cd, $nm, $abv, @codes, $lstId, $abId, $exNm, $ign, $ptSoc, $Unm);
  while (<IN>) {
    chomp;
    s/\$ /\$/g;
    s/ +/ /g;
    s/ \$/\$/g;

    ($cd, $nm, $abv, @codes) = split(/\$/, $_);
    #$nm = iutl->cleanLine($nm) if ($langMode ne 'ENG');
    $nm = iutl->cleanLine($nm);
    #$nm=~s/ $//; # Add this to cleanLine
    $Unm = uc($nm);

    # create soc atom
    $lstId = $osAtom->dumpAtom({code => $cd, sdui => $cd, str => $nm});
    #$ttyNm2cdSaid{"OS|$nm"} = "$cd|$lstId";
    $nmSdui2Said{"$Unm|$cd"} = $lstId  if (!defined($nmSdui2Said{"$Unm|$cd"}));
    $atomNames{"$Unm"}++;
    $cdTty2said{"$cd|OS"} = $lstId;
    $said2name{"$lstId"} = $nm;
    $said2sgid{"$lstId"} = $lstId;

    ## create soc atom attribute
    # soc order
	 $Attr->dumpAttr({sgId => $cd, atn => 'INTL_SOC_SORT_ORDER', atv => $ordSOC{"$cd"}});

    # abbreviation
    # Changes on 03/12/08
    # Create Arreviation atom rather than attribute.		
    if ( $abv ) {
      $abId = $abAtom->dumpAtom({code => $cd, sdui => $cd, str => iutl->cleanLine($abv)});	
      #dump merge and rel between OS and AB atom
      $cdTty2said{"$cd|AB"} = $lstId;
      $osabMerge->dumpMerge({sgId1 => $abId, sgId2 =>$lstId}); 
      $osabRel->dumpRel({sgId1 => $abId, sgId2 =>$lstId}); 
    }
         

    # dump codes
    &dumpCodes($lstId, 'OS', $nm, $cd, @codes);

    # now create expanded form if any and remember american terms.
    &makeOtherAtoms($nm, $cd, 'OS', $lstId) if ($langMode eq 'ENG');
  }
  $$Log->logIt("Done processing SOC file.\n");
  close(IN);

  ## now process HLGT terms.
  open(IN, "$dataEncode", $$Cfg->getEle('File.INP.HLGT'))
    or die "Could not open File.INP.HLGT.\n";
  while (<IN>) {
    chomp;
    s/\$ /\$/g;
    s/ +/ /g;
    s/ \$/\$/g;
    ($cd, $nm, @codes) = split(/\$/, $_);
    $nm = iutl->cleanLine($nm);
    $Unm = uc($nm);

    # create hlgt atom
    $lstId = $hgAtom->dumpAtom({code => $cd, sdui => $cd, str => $nm});
    $nmSdui2Said{"$Unm|$cd"} = $lstId  if (!defined($nmSdui2Said{"$Unm|$cd"}));
    $atomNames{"$Unm"}++;
    $cdTty2said{"$cd|HG"} = $lstId;
    $said2name{"$lstId"} = $nm;
    $said2sgid{"$lstId"} = $lstId;


    # create hlgt atom attributes: none
    # dump codes
    &dumpCodes($lstId, 'HG', $nm, $cd, @codes);

    # now create expanded form if any and remember american terms.
    &makeOtherAtoms($nm, $cd, 'HG', $lstId) if ($langMode eq 'ENG');
  }
  $$Log->logIt("Done processing HGLT file.\n");
  close(IN);

  ## now process HLT terms.
  open(IN, "$dataEncode", $$Cfg->getEle("File.INP.HLT"))
    or die "Could not open File.INP.HLT.\n";
  while (<IN>) {
    chomp;
    s/\$ /\$/g;
    s/ +/ /g;
    s/ \$/\$/g;
    ($cd, $nm, @codes) = split(/\$/, $_);
    #$nm = iutl->cleanLine($nm) if ($langMode ne 'ENG');
    $nm = iutl->cleanLine($nm);
    #$nm=~s/ $//; # Add this to cleanLine
    $Unm = uc($nm);

    # create hlt atom
    $lstId = $htAtom->dumpAtom({code => $cd, sdui => $cd, str => $nm});
    #$ttyNm2cdSaid{"HT|$nm"} = "$cd|$lstId";
    $nmSdui2Said{"$Unm|$cd"} = $lstId  if (!defined($nmSdui2Said{"$Unm|$cd"}));
    $atomNames{"$Unm"}++;
    $cdTty2said{"$cd|HT"} = $lstId;
    $said2name{"$lstId"} = $nm;
    $said2sgid{"$lstId"} = $lstId;

    ## create hlt atom attributes: noe
    # dump codes
    &dumpCodes($lstId, 'HT', $nm, $cd, @codes);

    # now create expanded form if any and remember american terms.
    &makeOtherAtoms($nm, $cd, 'HT', $lstId) if ($langMode eq 'ENG');
  }
  $$Log->logIt("Done processing HT file.\n");
  close(IN);

  ## now process PT terms.
  my %ptNames = ();
  open(IN, "$dataEncode", $$Cfg->getEle('File.INP.PT'))
    or die "Could not open File.INP.PT.\n";
  while (<IN>) {
    chomp;
    s/\$ /\$/g;
    s/ +/ /g;
    s/ \$/\$/g;
    ($cd, $nm, $ign, $ptSoc, @codes) = split(/\$/, $_);
    $nm = iutl->cleanLine($nm);
    $Unm = uc($nm);

    # create pt atom
    $lstId = $ptAtom->dumpAtom({code => $cd, sdui => $cd, str => $nm});
    #$ttyNm2cdSaid{"PT|$nm"} = "$cd|$lstId";
    $nmSdui2Said{"$Unm|$cd"} = $lstId if (!defined($nmSdui2Said{"$Unm|$cd"}));
    $atomNames{"$Unm"}++;
    $cdTty2said{"$cd|PT"} = $lstId;
    $said2name{"$lstId"} = $nm;
    $said2sgid{"$lstId"} = $lstId;
    $ptNames{"$nm"} = $lstId;	# remember for future use.
    $ptCd2Nm{"$cd"} = $nm; # added for mdrcze

    ## create pt atom attributes: MPS (primary soc)
    $Attr->dumpAttr({sgId => $cd, atn => 'PRIMARY_SOC', atv => $ptSoc});

    # dump codes
    &dumpCodes($lstId, 'PT', $nm, $cd, @codes);

    # now create expanded form if any and remember american terms.
    &makeOtherAtoms($nm, $cd, 'PT', $lstId) if ($langMode eq 'ENG');
  }
  $$Log->logIt("Done processing PT file.\n");
  close(IN);

  ## now process LLT/OL terms.
  open(IN, "$dataEncode", $$Cfg->getEle("File.INP.LT"))
    or die "Could not open File.INP.LT.\n";
  my ($ptcd, $current, $curTTY, $ptsaid, $ltsaid);
  my %ltCd2Tty = ();

  while (<IN>) {
    chomp;
    s/\$ /\$/g;
    s/ +/ /g;
    s/ \$/\$/g;
    ($cd, $nm, $ptcd, @codes) = split(/\$/, $_);
    $nm = iutl->cleanLine($nm);
    $Unm = uc($nm);
    # 7th one in codes is currency. Note that and remove it from codes.
    $current = splice(@codes, 6, 1);

    # now create the atom and its attributes, and rel to PT.
    if ($current eq 'Y') {
      # create an LLT atom.
      $lstId = $ltAtom->dumpAtom({code => $cd, sdui => $ptcd, str => $nm});
      &dumpCodes($lstId, 'LLT', $nm, $cd, @codes) ;
      $ltCd2Tty{"$cd"} = 'LLT';
      $cdTty2said{"$cd|LLT"} = $lstId;
      $curTTY = 'LLT';
    } else {
      # otherwise create an OL atom.
      $lstId = $olAtom->dumpAtom({code => $cd, sdui => $ptcd, str => $nm});
      &dumpCodes($lstId, 'OL', $nm, $cd, @codes);
      $ltCd2Tty{"$cd"} = 'OL';
      $cdTty2said{"$cd|OL"} = $lstId;
      $curTTY = 'OL';
    }

    #$ttyNm2cdSaid{"$curTTY|$nm"} = "$cd|$lstId";
    $nmSdui2Said{"$Unm|$ptcd"} = $lstId if (!defined($nmSdui2Said{"$Unm|$ptcd"}));
    $atomNames{"$Unm"}++;
    $said2name{"$lstId"} = $nm;
    $said2sgid{"$lstId"} = $lstId;

   $ptlltRel->dumpRel({sgId1 => $lstId, sgId2 => $cdTty2said{"$ptcd|PT"}});

   $ptsaid = $cdTty2said{"$ptcd|PT"};
   $ltsaid = $cdTty2said{"$cd|LLT"}; 
   $$Hier->addParChild($ptsaid, $lstId);

    # if this atom is same as a PT atom, merge these two.
    # we need to dump mergefacts for all same code lt/ol and pt for foreign translations too
    #if ($langMode eq 'ENG') {  # why to exclude these ?
    if (defined($ptCd2Nm{"$ptcd"}) && $nm eq $ptCd2Nm{"$ptcd"} ) { # need to dump only if sdui is and string same
    #if (defined($ptNames{"$nm"})) {
      # commented on 06/09/08
      # found duplicate PT names in MDRCZE resulting bad merge 
      #$ptltMerge->dumpMerge({sgId1 => $lstId, sgId2 => $ptNames{"$nm"}});
      $ptltMerge->dumpMerge({sgId1 => $lstId, sgId2 => $cdTty2said{"$ptcd|PT"}});
      $ptltlocds{"$cd"}++;
    #}
    }
    
    # now create expanded form if any and remember american terms.
    &makeOtherAtoms($nm, $cd, $curTTY, $lstId, $ptcd) if ($langMode eq 'ENG');

  }
  $$Log->logIt("Done processing LLT file.\n");
  close(IN);

  ## now process SMQ list
  open(IN, "$dataEncode", $$Cfg->getEle('File.INP.SMQL'))
    or die "Could not open File.INP.SMQL.\n";
  my ($cudId, $lvl, $des, $src, $nt, $vr, $sts, $alg);
  my %smqCd2Nm = ();

  while (<IN>) {
    chomp;
    s/\$ /\$/g;
    s/ +/ /g;
    s/ \$/\$/g;
    ($cd, $nm, $lvl, $des, $src, $nt, $vr, $sts, $alg) = split(/\$/, $_);
    $src = iutl->cleanLine($src);  # Modified for Dutch
    if ($src=~/^"/) { $src=~s/"//g; }
    $des=iutl->cleanLine($des);  
    $nt=iutl->cleanLine($nt);  
    $nm=iutl->cleanLine($nm);
    $alg=iutl->cleanLine($alg);
    
    $Unm = uc($nm);
    
    if ($langMode ne 'ENG') {
    $des=~s/ -//g ;
    $des=~s/- //g;
    $des=~s/^ //g;
    $des=~s/\)\. /\)\./g;
    $nt  =~s/\)\. /\)\./g;
    }
    
    # remember smq cd to name.
    $smqCd2Nm{"$cd"} = $nm;
    # create the SMQ atom.
    $lstId = $smqAtom->dumpAtom({code => $cd, sdui => $cd, str => $nm});
    $cdTty2said{"$cd|SMQ"} = $lstId;
    #$ttyNm2cdSaid{"SMQ|$nm"} = "$cd|$lstId";
    $nmSdui2Said{"$Unm|$cd"} = $lstId if (!defined($nmSdui2Said{"$Unm|$cd"}));
    $atomNames{"$Unm"}++;
    $said2name{"$lstId"} = $nm;
    $said2sgid{"$lstId"} = $lstId;

    # now create expanded form if any and remember american terms.
    &makeOtherAtoms($nm, $cd, 'SMQ', $lstId) if ($langMode eq 'ENG');


    # dump smq attributes.
    $smqctAttr->dumpAttr({sgId => $cd, atn => 'SMQ_LEVEL', atv => $lvl})
      if ($lvl);
    $smqctAttr->dumpAttr({sgId => $cd, atn => 'DEFINITION', atv => $des})
      if ($des);
    $smqctAttr->dumpAttr({sgId => $cd, atn => 'SMQ_SOURCE', atv => $src})
      if ($src);
    $smqctAttr->dumpAttr({sgId => $cd, atn => 'SMQ_NOTE', atv => $nt}) if ($nt);
    $smqctAttr->dumpAttr({sgId => $cd, atn => 'SMQ_STATUS', atv => $sts})
      if ($sts);
    $smqctAttr->dumpAttr({sgId => $cd, atn => 'SMQ_ALGORITHM', atv => $alg})
      if ($alg);
  }
  $$Log->logIt("Done processing SMQL file.\n");
  close(IN);

  ## now process SMQ content.
  open(IN, "$dataEncode", $$Cfg->getEle("File.INP.SMQC"))
    or die "Could not open File.INP.SMQC.\n";
  my ($relId, $rrelId, $tcd, $scp, $cat, $wt, $lmvr);
  my %seenTCD=();
  while (<IN>) {
    chomp;
    s/\$ /\$/g;
    s/ +/ /g;
    s/ \$/\$/g;

    ($cd, $tcd, $lvl, $scp, $cat, $wt, $sts, $vr, $lmvr) = split(/\$/, $_);

    $curTTY = 'SMQ';
    $curTTY = 'PT' if ($lvl == 4);
    $curTTY = $ltCd2Tty{"$tcd"} if ($lvl == 5);

    # dump the rel
    $relId = $smqRel->dumpRel({sgId1 => $tcd, sgId2 => $cd});

    # dump reverse rels for SMQs
    $rrelId = $smqrevRel->dumpRel({sgId1 => $cd, sgId2 => $tcd});
 
    # dump term attributes
    if (!defined($seenTCD{"$tcd"})) {
      $smqtlAttr->dumpAttr({sgId => $tcd, atn => 'SMQ_TERM_LEVEL', atv => $lvl});
      $seenTCD{"$tcd"}++;
    }
    # dump REL attributes
    $smqrAttr->dumpAttr({sgId => $relId,
			 atn => 'SMQ_TERM_SCOPE', atv => $scp});
    $smqrAttr->dumpAttr({sgId => $relId,
			 atn => 'SMQ_TERM_CAT', atv => $cat});
    $smqrAttr->dumpAttr({sgId => $relId,
			 atn => 'SMQ_TERM_WEIGHT', atv => $wt});
    $smqrAttr->dumpAttr({sgId => $relId,
			 atn => 'SMQ_TERM_STATUS', atv => $sts});
    $smqrAttr->dumpAttr({sgId => $relId,
			 atn => 'SMQ_TERM_ADDVERSION', atv => $vr});
    $smqrAttr->dumpAttr({sgId => $relId,
			 atn => 'SMQ_TERM_LMVERSION', atv => $lmvr});
    # dump Reverse REL attributes
  
    $smqrAttr->dumpAttr({sgId => $rrelId,
			 atn => 'SMQ_TERM_SCOPE', atv => $scp});
    $smqrAttr->dumpAttr({sgId => $rrelId,
			 atn => 'SMQ_TERM_CAT', atv => $cat});
    $smqrAttr->dumpAttr({sgId => $rrelId,
			 atn => 'SMQ_TERM_WEIGHT', atv => $wt});
    $smqrAttr->dumpAttr({sgId => $rrelId,
			 atn => 'SMQ_TERM_STATUS', atv => $sts});
    $smqrAttr->dumpAttr({sgId => $rrelId,
			 atn => 'SMQ_TERM_ADDVERSION', atv => $vr});
    $smqrAttr->dumpAttr({sgId => $rrelId,
			 atn => 'SMQ_TERM_LMVERSION', atv => $lmvr});
  }
  %seenTCD = ();		# release memory.
  $$Log->logIt("Done processing SMQS file.\n");
  close(IN);

  #now release memeory for the mapattrs
  #%dupAttrs_IFT=();
  #%dupAttrs_IF=();
  #%dupAttrs_IT=();

# process american terms and expanded terms only for MedDRA English
if ($langMode eq 'ENG') {
  ## now process american terms and expanded terms
  my ($amNm, $ttyNm, $exNm, $info, $tty1, $tty2, $cd1, $cd2, $ign);
  my ($said1, $said2, $sup, $sdui);
  my ($aed, $aen, $exd, $exn, $wtty, $ign, @ign, $eachVal);

  ## now process american terms.
  open (OUT, ">:utf8", "../tmp/amNames") or die "could not open amNames\n";
  my @allKeys = sort keys (%amNames);
  foreach $wtty ('OS', 'HG', 'HT', 'SMQ', 'PT', 'LLT', 'OL') {
    foreach $ttyNm (@allKeys) {
      ($tty1, $amNm) = split(/\|/, $ttyNm);
      next if ($tty1 ne $wtty);
      $Unm = uc($amNm);


      foreach $eachVal (@{$amNames{"$ttyNm"}}) {
	# atom where the ae came from.
	($cd1, $sdui, $said1) = split(/\|/, $eachVal);
	print OUT "$ttyNm|$eachVal\n";
	if ($said2 = $nmSdui2Said{"$Unm|$sdui"}) {
	  # existing atom.
	  $aed++;
	  $aeMerge->dumpMerge({sgId1 => $said1, sgId2 => $said2});
	} elsif ($said2 = $mth_nmSdui2Said{"$Unm|$sdui"}) {
	  # existing atom.
	  $aed++;
	  $aeMerge->dumpMerge({sgId1 => $said1, sgId2 => $said2});
	  $aeRel->dumpRel({sgId1 => $said2, sgId2 => $said1});
	} elsif (!defined($atomNames{"$Unm"}))  {
	  ## new term. so create the atom, rel and merge.
	  $aen++;
	  $sup = $tty1 eq 'OL' ? 'O' : 'N';
	  $said2 = $mthAtom->dumpAtom({str => $amNm, code => $cd1,
				       sdui => $sdui,
				       tty => "MTH_$tty1", suppress => $sup});
	  $aeMerge->dumpMerge({sgId1 => $said2, sgId2 => $said1});
	  $aeRel->dumpRel({sgId1 => $said2, sgId2 => $said1});
	  $mth_nmSdui2Said{"$Unm|$sdui"} = $said2;
	  $atomNames{"$Unm"}++;

	  # it is possible to have both ae and ex in a term.
	  # remember this in expanded terms
	  $exNm = iutl->cleanLine(&expandAbbr($amNm));
	  
	  if ($exNm ne $amNm) {
	    push(@{$exNames{"$tty1|$exNm"}}, "$cd1|$sdui|$said2")
	      if (!defined($exNames{"$tty1|$exNm"}));
	  }
	}
      }
    }
  }
  close(OUT);

  # now process expanded terms.
  open (OUT, ">:utf8", "../tmp/exNames") or die "could not open exNames\n";
  @allKeys = sort keys (%exNames);
  foreach $wtty ('OS', 'HG', 'HT', 'SMQ', 'PT', 'LLT', 'OL') {
    foreach $ttyNm (@allKeys) {
      ($tty1, $exNm) = split(/\|/, $ttyNm);
      next if ($tty1 ne $wtty);
      $Unm = uc($exNm);
      #print OUT "$ttyNm|$exNames{$ttyNm}\n";

      # atom where the ae came from.
      foreach $eachVal (@{$exNames{"$ttyNm"}}) {
	($cd1, $sdui, $said1) = split(/\|/, $eachVal);
	if ($said2 = $nmSdui2Said{"$Unm|$sdui"}) {
	  # existing atom.
	  $exd++;
	  $exMerge->dumpMerge({sgId1 => $said1, sgId2 => $said2});
	} elsif ($said2 = $mth_nmSdui2Said{"$Unm|$sdui"}) {
	  # existing atom.
	  $exd++;
	  $exMerge->dumpMerge({sgId1 => $said1, sgId2 => $said2});
	  $exRel->dumpRel({sgId1 => $said2, sgId2 => $said1});
	} elsif (!defined($atomNames{"$Unm"})) {
	  ## new term. so create the atom, rel and merge.
	  $exn++;
	  $sup = $tty1 eq 'OL' ? 'O' : 'N';
	  $said2 = $mthAtom->dumpAtom({str => $exNm, code => $cd1,
				       sdui => $sdui,
				       tty => "MTH_$tty1", suppress => $sup});
	  $exMerge->dumpMerge({sgId1 => $said2, sgId2 => $said1});
	  $exRel->dumpRel({sgId1 => $said2, sgId2 => $said1});
	  $mth_nmSdui2Said{"$Unm|$sdui"} = $said2;
	  $atomNames{"$Unm"}++;
	}
      }
    }
  }
  close(OUT);

  $$Log->logIt("exi ae: $aed\n");
  $$Log->logIt("new ae: $aen\n");
  $$Log->logIt("new ex: $exd\n");
  $$Log->logIt("new ex: $exn\n\n");

  $$Log->logIt("Invalid ICDCodes : $invIcd\n");
  $$Log->logIt("Invalid WHOCodes : $invWho\n");
  $$Log->logIt("Invalid CSTCodes : $invCst\n");

  }
  # release memory
  %nmSdui2Said=();
  %mth_nmSdui2Said=();
  %atomNames=();
  %exNames=();
  %amNames=();

}

sub readHierInfo{
  $$Log->logIt("Adding par/chlds\n");

  # process hier file.
  open(IN, "<:utf8", $$Cfg->getEle("File.INP.MDHIER"))
    or die "Could not open File.INP.MDHIER\n";
  my ($sid, $hgid, $htid, $ptid, $ssaid, $hgsaid, $htsaid, $ptsaid,$ptname,$htname,$hgname,$socname,$socab,$null,$ptsoc,$fg);

  #open(OUT, "> parchld") or die "no parchld file.\n";
  while (<IN>) {
    chomp;
    ($ptid, $htid, $hgid, $sid,$ptname,$htname,$hgname,$socname,$socab,$null,$ptsoc,$fg) = split(/\$/, $_);

    $ssaid = $cdTty2said{"$sid|OS"};
    $hgsaid = $cdTty2said{"$hgid|HG"};
    $htsaid = $cdTty2said{"$htid|HT"};
    $ptsaid = $cdTty2said{"$ptid|PT"};

    $$Hier->addParChild($ssaid, $hgsaid);
    $$Hier->addParChild($hgsaid, $htsaid);
    $$Hier->addParChild($htsaid, $ptsaid);

    if($fg eq 'Y'){
    	$smqtlAttr->dumpAttr({sgId => $ptid, atn => 'PRIMARY_PATH', atv => "$ptid\$$htid\$$hgid\$$sid\$$ptname\$$htname\$$hgname\$$socname"});
    }
  }
  close(IN);

  #close(OUT);

  my @rtnds = $$Hier->getRoots;
  $$Log->logIt("Before: root nodes are: <@rtnds>\n");

  # also set root node from config if any.
  my ($rtNm, $rtCd, $rtSaid);
  $rtNm = $$Cfg->getEle('HC.RootNodeName');
  $rtCd = $$Cfg->getEle('HC.RootNodeCode');
  $rtSaid = $$Cfg->getEle('HC.RootNodeSaid');

  # Preserve a stable root-child order for sibling lists in CONTEXT values.
  foreach my $root (sort $$Hier->getRoots()) {
    $$Hier->addParChild($rtSaid, $root);
  }
  $said2name{"$rtSaid"} = $rtNm;
  $said2sgid{"$rtSaid"} = $rtCd;
  
  @rtnds = $$Hier->getRoots;
  $$Log->logIt("After: root nodes are: <@rtnds>\n");
 
}

sub prepareCxts {
  &readHierInfo;
  if ($langMode eq 'ENG') { 
  $$Hier->dumpCxtsAttrs(\$rootCxt,      # obj to dump root cxt
			    \$parCxt,       # obj to dump par cxts
			    \$sibCxt,       # obj to dump sib cxts
			    \$cxtAttr,      # obj to dump attrs
			    \%said2name,    # said to name hash
			    0,              # see note below (1)
			    \%said2sgid,    # said to said hash
			    0,              # don't dump chld in attrs
			    1);             # dump sibs in attrs
  } else { 
  $$Hier->dumpCxtsAttrs(\$rootCxt,      # obj to dump root cxt
			    \$parCxt,       # obj to dump par cxts
			    \$sibCxt,       # obj to dump sib cxts
			    0,      # obj to dump attrs
			    \%said2name,    # said to name hash
			    0,              # see note below (1)
			    \%said2sgid,    # said to said hash
			    0,              # don't dump chld in attrs
			    0);             # dump sibs in attrs
  }
}

sub processSTYs {

  ## first prepare said2stys from the generated file sty_term_ids.
  # this file is generted during test insertion.
  my ($ign, $said, $sty, $sab, $tg, $key, $ptree, $psaid, @inpLn);
  my ($ln, $tty, $sdui, $rel);
  my %said2stys = ();
  my %saidsNeedStys = ();
  my %smqSaids=();
  my %ttySdui2Said=();
  open (IN, "<:utf8", $$Cfg->getEle('File.INP.StyTermIds'))
    or die "Could not open File.INP.StyTermIds file.\n";
  while(<IN>) {
    chomp;
    ($said, $sty) = split(/\|/, $_);
    push(@{$said2stys{"$said"}}, $sty);
  }
  close(IN);

  ## now read atoms file
  # remember saids whose stys are not yet populated

  open(IN, "<:utf8", $$Cfg->getEle('File.Atom'))
    or die "Could not open File.Atoms file.\n";
  while (<IN>) {
    chomp;
    @inpLn = split(/\|/, $_);
    next if ($inpLn[1] ne $vsab);
    $said = $inpLn[0];
    ($ign, $tty) = split(/\//, $inpLn[2]);
    $sdui = $inpLn[11];
    if (!defined($said2stys{"$said"})) {
      #store its tty and sdui(12th field).
      $saidsNeedStys{"$said"} = "$tty|$sdui";
      if ($inpLn[2] =~ /SMQ/) { $smqSaids{"$said"}++; }
    } else {
      $ttySdui2Said{"$tty|$sdui"} = $said;
    }
  }
  close(IN);


  # for these walk through the context trees and assign stys.
  open (IN, "<:utf8", $$Cfg->getEle('File.Context'))
    or die "Could not open File.Contexts.\n";
  $ln = 0;
  $$Log->logIt("tree walk begin\n");
  while (<IN>) {
    chomp;
    ($said, $rel, $ign, $ign, $ign, $ign, $ign, $ptree)= split(/\|/, $_);
    next if($rel ne 'PAR');
    next if (defined($said2stys{"$said"}));

    # this said doen'st have any assigned stys. so walk the tree and assign
    # one.
    foreach $psaid (reverse (split(/\./, $ptree))) {
      if (defined($said2stys{"$psaid"})) {
	@{$said2stys{"$said"}} = @{$said2stys{"$psaid"}};
	$ign = $saidsNeedStys{"$said"};
	$ttySdui2Said{"$ign"} = $said;
	delete($saidsNeedStys{"$said"});
	$ln++;
	$$Log->logIt("\t$said|$ign added(tree): @{$said2stys{$said}}\n");
	last;
      }
    }
  }
  close(IN);
  $$Log->logIt("$ln saids are resolved via tree walk.\n\n");

  $$Log->logIt("PT to LLT/OL begin\n");
  # now find stys via sdui for the missing ones.
  # do it in two stages: first assign stys for LLT/OL and then fro mth atoms.
  $ln = 0;
  foreach $said (keys (%saidsNeedStys)) {
    ($tty, $sdui) = split(/\|/, $saidsNeedStys{"$said"});
    next if ($tty =~ /MTH/);
    if ($tty eq 'LLT' or $tty eq 'OL') {
      $psaid = $ttySdui2Said{"PT|$sdui"};
      if (defined($said2stys{"$psaid"})) {
	@{$said2stys{"$said"}} = @{$said2stys{"$psaid"}};
	$ign = $saidsNeedStys{"$said"};
	$ttySdui2Said{"$ign"} = $said;
	delete($saidsNeedStys{"$said"});
	$$Log->logIt("\t$said|$ign added(LLT/OL): @{$said2stys{$said}}\n");
	$ln++;
      }
    }
  }
  $$Log->logIt("$ln saids are resolved via PT to LLT/OL.\n\n");

  $$Log->logIt("MTH begin\n");
  # now assign stys for mth atoms via sdui
  $ln = 0;
  foreach $said (keys (%saidsNeedStys)) {
    ($tty, $sdui) = split(/\|/, $saidsNeedStys{"$said"});
    next if ($tty !~ /MTH/);
    $tty =~ s/MTH_//;
    $psaid = $ttySdui2Said{"$tty|$sdui"};
    if (defined($said2stys{"$psaid"})) {
      @{$said2stys{"$said"}} = @{$said2stys{"$psaid"}};
      $ign = $saidsNeedStys{"$said"};
      $ttySdui2Said{"$ign"} = $said;
      delete($saidsNeedStys{"$said"});
      $$Log->logIt("\t$said|$ign added(MTH): @{$said2stys{$said}}\n");
      $ln++;
    }
  }
  $$Log->logIt("$ln saids are resolved via tty to mth_tty.\n\n");


  $$Log->logIt("SMQ begin\n");
  # add "Clasification" as sty for all SMQ atoms
  $ln = 0;
  foreach $said (sort keys (%smqSaids)) {
    push (@{$said2stys{"$said"}}, "Classification")
      unless grep(/Classification/, @{$said2stys{"$said"}});
    if (defined ($saidsNeedStys{"$said"})) {
      $ign = $saidsNeedStys{"$said"};
      $ttySdui2Said{"$ign"} = $said;
      delete($saidsNeedStys{"$said"});
      $$Log->logIt("\t$said|$ign added(SMQ): @{$said2stys{$said}}\n");
      $ln++;
    }
  }
  $$Log->logIt("$ln saids are resolved for bare SMQ.\n");

  # now dump stys as attributes.
  open(OUT, ">:utf8", "occs_defaults_stys")
    or die "Could not open new_sty_defaults file.\n";
  $mtstyAttr->setDefaults({sgType => 'SRC_ATOM_ID'});
  foreach $said (sort keys (%said2stys)) {
    foreach $sty (@{$said2stys{"$said"}}) {
      $mtstyAttr->dumpAttr({sgId => $said, atv => $sty});
      print OUT "$said|$sty\n";
    }
  }
  close(OUT);

  # what ever is remiaining in saidsNeedStys, we need to do some thing.
  my @remKeys = sort keys(%saidsNeedStys);
  $ln = @remKeys;
  $$Log->logIt("After assigning stys, the $ln saids are remaining.\n");
  foreach $ln (@remKeys) {
    $$Log->logIt("\t$ln|$saidsNeedStys{$ln}\n");
  }
  $$Log->logIt("\n\n");
}


# -----------------------------------------------------------------------------
# main main main
#------------------------------------------------------------------------------
sub main {

  # instantiate NLMInv
  $Inv = new NLMInv($cfgFile);

  # get common obj pointers
  $Log = $Inv->getLog;
  $Cfg = $Inv->getCfg;
  $Hier = $Inv->getHier;
  $Inv->prTime("Begin");

  # begin inversion and app specific initialization
  if (defined $options{s}) {
    $Inv->invBegin('Append');
    &init;
    &processSTYs;
  }
  
  else {
    $Inv->invBegin;
    &init;

    # dump source meta data.
    my $srcBldr = new SrcBldr();
    $srcBldr->processSrc();
    $Inv->prTime("Done SRC building");

    # process input files
    &processMDR;
    $Inv->prTime("Done MDR Processing");

    # dump contexts and context attributes.
    prepareCxts();
    $Inv->prTime("Done CXT building");
  }

  # close all files.
  $Inv->invEnd;
  $Inv->prTime("End");
}

sub runMain {
  if (!defined $options{l} || uc($options{l}) eq 'ENG') {
    $langMode = 'ENG';
    $cfgFile = "../etc/MDR.cfg";
    $dataEncode = "<:utf8";
  } 
#    elsif (uc($options{l}) eq 'SPA') {
#    $langMode = 'SPA';
#    $cfgFile = "../etc/mdrspa14_0.cfg";
#    $dataEncode="<:encoding(cp1252)";
#  } elsif (uc($options{l}) eq 'AE') {
#  } elsif (uc($options{l}) eq 'DUT') {
#    $langMode = 'DUT';
#    $cfgFile = "../etc/mdrdut14_0.cfg";
#    $dataEncode="<:encoding(cp1252)";
#  } elsif (uc($options{l}) eq 'EA') {
#  } elsif (uc($options{l}) eq 'EX') {
#  } elsif (uc($options{l}) eq 'FRE') {
#    $langMode = 'FRE';
#    $cfgFile = "../etc/mdrfre14_0.cfg";
#    $dataEncode="<:encoding(cp1252)";
#  } elsif (uc($options{l}) eq 'GER') {
#    $langMode = 'GER';
#    $cfgFile = "../etc/mdrger14_0.cfg";  
#    $dataEncode="<:encoding(cp1252)";
#  } elsif (uc($options{l}) eq 'ITA') {
#    $langMode = 'ITA';
#    $cfgFile = "../etc/mdrita14_0.cfg";  
#    $dataEncode="<:encoding(cp1252)";
#  } elsif (uc($options{l}) eq 'JPN') {
#    $langMode = 'JPN';
#    $dataEncode="<:encoding(cp1252)";
#    #$cfgFile = "../etc/mdrjpn14_0.cfg";  
#  } elsif (uc($options{l}) eq 'POR') {
#    $langMode = 'POR';
#    $cfgFile = "../etc/mdrpor14_0.cfg";  
#    $dataEncode="<:encoding(cp1252)";
#  } elsif (uc($options{l}) eq 'CZE') {
#    $langMode = 'CZE';
#    $cfgFile = "../etc/mdrcze14_0.cfg";  
#    $dataEncode="<:utf8";
#  }
  
  &main;
}
&runMain;

#  Check for prerequisites
sub checkPrerequisites {
  # Check required config file properties
  my $IN;
  my @reqProp;

  # Add the required to be checked for English and foreign transalations
  if ($options{c} eq 'MDR.cfg') {
        @reqProp = ("SaidStart", "VSAB", "HC.RootNodeSaid", "HC.RootNodeName","HC.RootNodeCode" );
  } else {
        @reqProp = ("SaidStart", "VSAB", "HC.RootNodeSaid", "HC.RootNodeName","HC.RootNodeCode","TransBase" );
  }
  open ($IN, "<:utf8", "$Bin/../etc/$options{c}") || croak"ERROR: missing config file: $options{c}\n";
  my @lines = <$IN>;
  close ($IN);

#  foreach my $prop ( ("SaidStart", "VSAB", "HC.RootNodeSaid", "HC.RootNodeName","HC.RootNodeCode" ) ) {
    foreach my $prop (@reqProp) {
    my ($line) = grep /^$prop/, @lines;
      if (! $line) {
        print "ERROR: Config file is missing $prop property\n";
      }
      if ($prop =~ /^File\./) {
	my ($key, $val) = split(/=/, $line);
	$val =~ s/^ *//; chomp($val);
	if (! -e "$Bin/$val") {
	print "ERROR: $key file is missing: $val.\n";
	exit 1;
       }
     }
   }
  print "PASSED: All prerequisite properties exist.\n";
  exit 0;
}

