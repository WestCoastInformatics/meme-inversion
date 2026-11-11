#!/usr/bin/perl
#
# File: invert_rf2.pl
# Author: Nels Olson
# Summary: Inversion script for SNOMEDCT_US in RF2 format
# Usage: invert_rf2.pl [-h] [-c]
#
#################################################################

#---------------------
# Configure libraries
#---------------------
use FindBin qw($Bin);
use lib "$ENV{INV_HOME}/lib";
use lib "$Bin/../lib";
use lib "$Bin";
use open ":utf8";
use strict 'vars';
use strict 'subs';

use Carp;
use Getopt::Long;
#use XML::Parser::PerlSAX;
use NLMInv;
use SrcBldr;
use Atom;
use Attribute;
use Relation;
use Merge;
use Context;

#---------------------
# Declare Global Variables
#---------------------
# Framework References
our ($Inv, $CfgRef, $LogRef, $HierRef);

# Template variables
my ($Atom);
my ($AttrCON, $AttrSAUI, $AttrSAID, $AttrREL, $AttrATTR, $AttrCXT);
my ($MergeSY, $MergeSAME);
my ($RelationR, $RelationA, $RelationM);
my ($ContextPAR);
my ($moduleName);

my %active = ();
my %conActive = ();
my %hasActiveRels = ();
my %parent = ();
my %type = ();
my %limited = ();
my %mandRefin = ();
my %dialect = ();
my %prefDid = ();
my %defnId = ();
my %subsetCid = ();
my %subsetMem = ();
my %cid2said = ();
my %cid2name = ();
my %cid2snomedid = ();
my %cids2rinfo = ();
my %isValid = ();
my %moduleName = ();
my %said2name = ();
my %said2sgid = ();
my %relName2info = ();
my %relCid2info = ();
my $typeId2TTY = "";
my $refSet2ATN = "";
my $refSet2pattern = "";
my $defLang = "";
my $defMod = "";

#---------------------
# Process Options
#---------------------
use Getopt::Long;
GetOptions(q{-help|?|h} => sub { printHelp();},
           q{-c} => sub { checkPrerequisites(); exit 0; } );

our %charType  = ();
our %valChars = ();
for (my $ch = 'a' ; $ch le 'z' ; $ch++) {
  $charType{$ch} = 'lc';
  $valChars{$ch}++;
}
for (my $ch = 'A' ; $ch le 'Z' ; $ch++) {
  $charType{$ch} = 'uc';
  $valChars{$ch}++;
}
for (my $ch = '0' ; $ch le '9' ; $ch++) {
  $charType{$ch} = 'nc';
  $valChars{$ch}++;
}
$charType{''} = 'nl';

# pat1 has 3 parts:
# 1st - (.?) - match 0 or 1 of any char
#
# 2nd - (>[^<]*[^ <]<|\^[^^]*[^ ^]\^) - broken into (A or B)
# A is   >[^<]*[^ <]<
# and B is            \^[^^]*[^ ^]\^
# A is match ">(all chars except < and space)<"
# B is match "^(all chars except ^ and spcae)^"
#
# 3rd - (.?) - match 0 or 1 of any char
our $pat1 = qr#(.?)(>[^<]*[^ <]<|\^[^^]*[^ ^]\^)(.?)#;

# pat2 is the middle part of pat1.
our $pat2a = qr#(>)([^<]*[^ <])(<)#;
our $pat2b = qr#(\^)([^^]*[^ ^])(\^)#;

#---------------------
# Run the program
#---------------------
main();
exit 0;

#---------------------
# Main
#---------------------
# Main program.

sub main {

  # Initialize the framework
  $Inv = new NLMInv("$Bin/../etc/sct.cfg");
  $LogRef = $Inv->getLog();
  $CfgRef = $Inv->getCfg();
  $HierRef = $Inv->getHier();

  # Check Prerequisites
  checkPrerequisites();

  # Start
  $Inv->prTime("Begin");
  $Inv->invBegin();
  &init();


  # find valid description and concept ids
  #&get_valid_descs;
  &get_valid_concepts;
  &get_active_rela_values;
  &get_active_rela_assn_values;

	print "GOT valid codes\n";
  # Process input files
  &process_metadata;
print "done processing metadata\n";

  # get moduleName
  &get_moduleName;

  # must process concepts, attrs and subsets before descriptions
  &process_concepts;
  
  # must get description status so we know what is obsolete and don't dump attributes
  &get_description_status;

  # must find which relas have active rels so that we know which ones should be made into atoms

  # must process attrs (Simple Maps - SNOMEDIDs in particular) before descr's
  &process_attrs;
  &process_defns;

  # must process subsets (languages in particular) after defn's & before descr's
  &process_subsets;

  # must process descriptions before relationships
  &process_descrs;

  my($relationsFile) = $$CfgRef->getReqEle('File.INP.RELATIONS');
  &process_rels($relationsFile);

  &process_assocs;
  &process_mappings;   # no mappings in Jan 2014 Beta release
  &make_sb_atoms;   # must be done after process_{descrs,assocs,mappings}

  &dumpCxts;

  # Finish
  $Inv->prTime("End");
  $Inv->invEnd();
} # end main


#---------------------
# Initialize
#---------------------
# Run first, before parsing begins. Set up templates.

sub init {
  # Dump source meta data.
  my $srcBldr = new SrcBldr();
  $srcBldr->processSrc;

  # Create templates.

  # ATOM templates.
  $Atom = new Atom("");

  # ATTRIBUTE templates.
  $AttrCON = new Attribute("Attribute.CON");
  $AttrSAUI = new Attribute("Attribute.SAUI");
  $AttrSAID = new Attribute("Attribute.SAID");
  $AttrREL = new Attribute("Attribute.REL");
  $AttrATTR = new Attribute("Attribute.SATUI");
  $AttrCXT = new Attribute("Attribute.CXT");

  # RELATION templates
  $RelationR = new Relation("Relation.R");
  $RelationA = new Relation("Relation.R");
  $RelationM = new Relation("Relation.R");

  # CONTEXT templates
  $ContextPAR = new Context("Context.PAR");
#  $ContextSIB = new Context("Context.SIB");
#  $ContextROOT = new Context("Context.ROOT");

  # MERGE templates
  $MergeSY = new Merge("Merge.DID2SCUI");
  $MergeSAME = new Merge("Merge.SAMEAS");

  $typeId2TTY = $$CfgRef->getHashRef("TTY");
  # note: refSet2ATN now maps not only AttributeValue and SimpleMap refSetIds
  # but also "concrete relationship" typeIds to ATNs
  $refSet2ATN = $$CfgRef->getHashRef("ATN");
  $refSet2pattern = $$CfgRef->getHashRef("PATTERN");
  $defLang = $$CfgRef->getReqEle('DEFAULTLANGUAGE');
  $defMod = $$CfgRef->getReqEle('DEFAULTMODULE');

  foreach my $relmap ($$CfgRef->getList('SCT.RELMAP')) {
    my($rname, $rela, $irela, $rel) = split(/\|/, $relmap);
    $relName2info{"$rname"} = "$rela|$irela|$rel";
  }
} # end init


# -------------------------------------------
sub get_valid_descs {
  my($descrFile) = $$CfgRef->getReqEle('File.INP.DESCRIPTIONS');

  open(INPUT, "$descrFile") or die "Can't open/read $descrFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    $_ = iutl->cleanLine($_);
    my ($id, $effectiveTime, $active, $moduleId, $conceptId, $languageCode,
        $typeId, $term, $caseSignificanceId) = split(/[\t\n]/);
		$active{$id}=$active;
    }
close (INPUT);
}
#
# -------------------------------------------
sub get_valid_concepts {
  my($conceptFile) = $$CfgRef->getReqEle('File.INP.CONCEPTS');
  my($rootScui) = $$CfgRef->getReqEle('ROOTSCUI');

  open(INPUT, "$conceptFile") or die "Can't open/read $conceptFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my($id, $effectiveTime, $active, $moduleId,
       $definitionStatusId) = split(/[\t\n]/);
$active{$id}=$active;
$conActive{$id}=$active;
	#if ($active ==1) {
		#$active{$id}=$active;
	#}
    }
close (INPUT);
}
#
#
# -------------------------------------------

sub get_active_rela_values {
  my($relFile) = $$CfgRef->getReqEle('File.INP.RELATIONS');

  open(INPUT, "$relFile") or die "Can't open/read $relFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my($id, $effectiveTime, $active, $moduleId, $sourceId, $destinationId,
       $relationshipGroup, $typeId, $characteristicTypeId,
       $modifierId) = split(/[\t\n]/);
	if ($active ==1) {
		$hasActiveRels{$typeId}=1;
#print "$typeId\n";
	}	
}
close (INPUT);
}

# -------------------------------------------

sub get_active_rela_assn_values {
  my($assocsFile) = $$CfgRef->getReqEle('File.INP.ASSOCIATIONS');

  open(INPUT, "$assocsFile") or die "Can't open/read $assocsFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my($id, $effectiveTime, $active, $moduleId, $refSetId,
       $referencedComponentId, $targetComponent) = split(/[\t\n]/);
	if ($active ==1) {
		$hasActiveRels{$refSetId}=1;
#print "$refSetId\n";
	}	
}
close (INPUT);
}

#---------------------
# process_metadata
#---------------------
# processes metadata files

sub process_metadata {
  my($refsetsFile) = $$CfgRef->getReqEle('File.INP.REFSETS');
  my($descrFormatFile) = $$CfgRef->getReqEle('File.INP.DESCRFORMAT');
  my($moduleDepFile) = $$CfgRef->getReqEle('File.INP.MODULEDEP');

  open(INPUT, "$refsetsFile") or die "Can't open/read $refsetsFile, $!";
  $_ = <INPUT>;  # skip header line

  my %seen = ();
  while (<INPUT>) {
    s/\r$//;
    my($id, $effectiveTime, $active, $moduleId, $refSetId,
       $referencedComponentId, $attributeDescription, $attributeType,
       $attributeOrder) = split(/[\t\n]/);

    $subsetCid{$refSetId} = 1 unless $subsetCid{$refSetId};

    #my($supp) = ($active==1) ? "N" : "O";
    	my $supp = "N";
    	#my $supp;
    	next if ($active{$referencedComponentId} != 1 || $active !=1);
    	#if ($active ==1)
		#{ 
		#$supp = "N";
		#}
    foreach my $atv ("ATTRIBUTEDESCRIPTION\~$attributeDescription",
                      "ATTRIBUTETYPE\~$attributeType",
                      "ATTRIBUTEORDER\~$attributeOrder") {
      $AttrCON->dumpAttr({sgId => $referencedComponentId,
                          atn => "SUBSET_MEMBER", atv => "$refSetId\~$atv",
                          suppress => $supp, satui => $id});
    }

    if (!$seen{$referencedComponentId}++ && $active{$referencedComponentId} ==1) {
    #if (!$seen{$referencedComponentId}++) {
      $AttrCON->dumpAttr({sgId => $referencedComponentId,
                          atn => "REFSET_PATTERN",
                          atv => $refSet2pattern->{$referencedComponentId},
                          suppress => "N", satui => ""});
    }
  }


  open(INPUT, "$descrFormatFile") or die "Can't open/read $descrFormatFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my($id, $effectiveTime, $active, $moduleId, $refSetId,
       $referencedComponentId, $descriptionFormat,
       $descriptionLength) = split(/[\t\n]/);

    $subsetCid{$refSetId} = 1 unless $subsetCid{$refSetId};

    #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
    foreach my $atv ("DESCRIPTIONFORMAT\~$descriptionFormat",
                      "DESCRIPTIONLENGTH\~$descriptionLength") {
      $AttrCON->dumpAttr({sgId => $referencedComponentId,
                          atn => "SUBSET_MEMBER", atv => "$refSetId\~$atv",
                          suppress => $supp, satui => $id});
    }

$AttrCON->dumpAttr({sgId => $referencedComponentId,
                        atn => "DESCRIPTION_FORMAT", atv => $descriptionFormat,
                        suppress => $supp, satui => ""});

    $AttrCON->dumpAttr({sgId => $referencedComponentId,
                        atn => "DESCRIPTION_LENGTH", atv => $descriptionLength,
                        suppress => $supp, satui => ""});
  }


  open(INPUT, "$moduleDepFile") or die "Can't open/read $moduleDepFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my($id, $effectiveTime, $active, $moduleId, $refSetId,
       $referencedComponentId, $sourceEffectiveTime,
       $targetEffectiveTime) = split(/[\t\n]/);

    $subsetCid{$refSetId} = 1 unless $subsetCid{$refSetId};

    #my($supp) = ($active==1) ? "N" : "O";
    my $supp;
    next if ($active != 1);
    if ($active ==1)
	{ 
	$supp = "N";
	}
    foreach my $atv ("SOURCEEFFECTIVETIME\~$sourceEffectiveTime",
                      "TARGETEFFECTIVETIME\~$targetEffectiveTime") {
      $AttrCON->dumpAttr({sgId => $referencedComponentId,
                          atn => "SUBSET_MEMBER", atv => "$refSetId\~$atv",
                          suppress => $supp, satui => $id});
    }

    $RelationR->dumpRel({sgId1 => $moduleId, sgId2 => $referencedComponentId,
                         rel => "RT", rela => "has_dependent", srui => $id,
                         relGroup => "", suppress => $supp});
    $AttrREL->dumpAttr({sgId => $id, atn => "SOURCE_EFFECTIVE_TIME",
                        atv => $sourceEffectiveTime, suppress => $supp,
                        satui => ""});
    $AttrREL->dumpAttr({sgId => $id, atn => "TARGET_EFFECTIVE_TIME",
                        atv => $targetEffectiveTime, suppress => $supp,
                        satui => ""});
  }
} # end process_metadata


#---------------------
# process_concepts
#---------------------
# processes concepts

sub process_concepts {
  my($conceptFile) = $$CfgRef->getReqEle('File.INP.CONCEPTS');
  my($rootScui) = $$CfgRef->getReqEle('ROOTSCUI');

  open(INPUT, "$conceptFile") or die "Can't open/read $conceptFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my($id, $effectiveTime, $active, $moduleId,
       $definitionStatusId) = split(/[\t\n]/);

    #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
    $AttrCON->dumpAttr({sgId => $id, atn => "EFFECTIVE_TIME",
                        atv => $effectiveTime, suppress => $supp,
                        satui => ""});
    $AttrCON->dumpAttr({sgId => $id, atn => "ACTIVE", atv => $active,
                        suppress => $supp, satui => ""});
    if ($id eq $rootScui) {
      $AttrCON->dumpAttr({sgId => $id, atn => "DEFAULT_LANGUAGECODE",
                          atv => $defLang, suppress => "N", satui => ""});
      $AttrCON->dumpAttr({sgId => $id, atn => "DEFAULT_MODULE_ID",
                          atv => $defMod, suppress => "N", satui => ""});
    }
    if ($moduleId ne $defMod) {
      $AttrCON->dumpAttr({sgId => $id, atn => "MODULE_ID", atv => $moduleId,
                          suppress => $supp, satui => ""});
      $AttrCON->dumpAttr({sgId => $id, atn => "MODULE_NAME", atv => $moduleName{$moduleId},
                           suppress => $supp, satui => ""});
    }
    $AttrCON->dumpAttr({sgId => $id, atn => "DEFINITION_STATUS_ID",
                        atv => $definitionStatusId, suppress => $supp,
                        satui => ""});

    # save "active" values for use in setting TTYs of descriptions
    $active{$id} = $active;
  }
} # end process_concepts


#---------------------
# process_attrs
#---------------------
# processes attributes

sub process_attrs {
  my($attributesFile) = $$CfgRef->getReqEle('File.INP.ATTRIBUTES');
  my($cStatusRefSet) = $$CfgRef->getReqEle('CSTATUSREFSET');
  my($dStatusRefSet) = $$CfgRef->getReqEle('DSTATUSREFSET');
  my($limitedStatus) = $$CfgRef->getReqEle('LIMITEDSTATUS');

  open(INPUT, "$attributesFile") or die "Can't open/read $attributesFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my ($id, $effectiveTime, $active, $moduleId, $refSetId,
        $referencedComponentId, $valueId) = split(/[\t\n]/);


    $subsetCid{$refSetId} = 1 unless $subsetCid{$refSetId};

    my $attr = ($refSetId eq $cStatusRefSet) ? $AttrCON :
               ($refSetId eq $dStatusRefSet) ? $AttrSAUI : $AttrREL;
    #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1 || $active{$referencedComponentId} !=1);
    	#next if ($active != 1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}

    foreach my $atv ("VALUEID\~$valueId") {
      $attr->dumpAttr({sgId => $referencedComponentId,
                          atn => "SUBSET_MEMBER", atv => "$refSetId\~$atv",
                          suppress => $supp, satui => $id});
    }

    $attr->dumpAttr({sgId => $referencedComponentId,
                     atn => $refSet2ATN->{$refSetId}, atv => $valueId,
                     suppress => $supp, satui => $id});

    # save "limited" status values for use in setting TTYs of descriptions
    if ($refSetId eq $cStatusRefSet && $active==1 &&
        $valueId eq $limitedStatus) {
      $limited{$referencedComponentId} = 1;
    }
  }


  my($concreteRelsFile) = $$CfgRef->getReqEle('File.INP.CONCRETERELS');

  open(INPUT, "$concreteRelsFile") or die "Can't open/read $concreteRelsFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my ($id, $effectiveTime, $active, $moduleId, $sourceId, $value,
        $relationshipGroup, $typeId, $characteristicTypeId,
        $modifierId) = split(/[\t\n]/);

    #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
    my $atv = "$value\~$relationshipGroup";
    # note: %refSet2ATN now maps not only refSetIds but also typeIds to ATNs
    $AttrCON->dumpAttr({sgId => $sourceId, atn => $refSet2ATN->{$typeId},
                        atv => $atv, suppress => $supp, satui => $id});

  }


  my($simpleMapsFile) = $$CfgRef->getReqEle('File.INP.SIMPLEMAPS');

  open(INPUT, "$simpleMapsFile") or die "Can't open/read $simpleMapsFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my ($id, $effectiveTime, $active, $moduleId, $refSetId,
        $referencedComponentId, $mapTarget) = split(/[\t\n]/);

    $subsetCid{$refSetId} = 1 unless $subsetCid{$refSetId};

    #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1 || $active{$referencedComponentId} != 1);
	if ($active == 1)
		{ 
		$supp = "N";
		}
    foreach my $atv ("MAPTARGET\~$mapTarget") {
      $AttrCON->dumpAttr({sgId => $referencedComponentId,
                          atn => "SUBSET_MEMBER", atv => "$refSetId\~$atv",
                          suppress => $supp, satui => $id});
    }

    if ($refSet2ATN->{$refSetId} eq 'SNOMEDID') {
      $cid2snomedid{$referencedComponentId} = $mapTarget;
    }
    $AttrCON->dumpAttr({sgId => $referencedComponentId,
                        atn => $refSet2ATN->{$refSetId}, atv => $mapTarget,
                        suppress => $supp, satui => ""});
  }


  return;   # skip refinability stuff in RF1-compatability files

  my($refinFile) = $$CfgRef->getReqEle('File.INP.REFINABILITY');
  my($refinRefSet) = $$CfgRef->getReqEle('REFINREFSET');
  my($refinMandatory) = $$CfgRef->getReqEle('REFINMANDATORY');

  open(INPUT, "$refinFile") or die "Can't open/read $refinFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my ($id, $effectiveTime, $active, $moduleId, $refSetId,
        $referencedComponentId, $valueId) = split(/[\t\n]/);

    $subsetCid{$refSetId} = 1 unless $subsetCid{$refSetId};

    if ($refSetId eq $refinRefSet && $active==1 &&
        $valueId eq $refinMandatory) {
      # don't dump this here as a rel attr: it will become an AQ attr attr
      $mandRefin{$referencedComponentId} = 1;
    } else {
      #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
      $AttrREL->dumpAttr({sgId => $referencedComponentId,
                          atn => $refSet2ATN->{$refSetId}, atv => $valueId,
                          suppress => $supp, satui => ""});
    }
  }
} # end process_attrs


#---------------------
# process_defns
#---------------------
# processes definitions

sub process_defns {
  my($defnFile) = $$CfgRef->getReqEle('File.INP.DEFINITIONS');

  open(INPUT, "$defnFile") or die "Can't open/read $defnFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    $_ = iutl->cleanLine($_);
    my ($id, $effectiveTime, $active, $moduleId, $conceptId, $languageCode,
        $typeId, $term, $caseSignificanceId) = split(/[\t\n]/);
    $term =~ s/\|//g;  # strip '|' characters we can't release
    $term =~ s/^ +//;
    $term =~ s/ +$//;

    $defnId{$id} = 1;

    my $supp = "N";
    if ($active == 0 || $active{$conceptId}==0 || $limited{$conceptId}) {
      #$supp = "O";
      next;
       
    }


    # dump definitions as DEFINITION attrs
    $AttrCON->dumpAttr({sgId => $conceptId, atn => "DEFINITION", atv => $term,
                        suppress => $supp, satui => $id});
  }
} # end process_defns

#---------------------
# get_moduleName - need to loop to get all values before writing attributes
#--------------------------------
#
#
sub get_moduleName {
  my($descrFile) = $$CfgRef->getReqEle('File.INP.DESCRIPTIONS');

  open(INPUT, "$descrFile") or die "Can't open/read $descrFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    $_ = iutl->cleanLine($_);
    my ($id, $effectiveTime, $active, $moduleId, $conceptId, $languageCode,
        $typeId, $term, $caseSignificanceId) = split(/[\t\n]/);
    $term =~ s/\|/&#x7C;/g;  # convert '|' characters we can't otherwise release
    $term =~ s/ +$//;
	if ($term =~/ module \(core metadata concept\)/)
                {
                $moduleName = $term;
		$moduleName =~ s/ \(core metadata concept\)//;
                $moduleName{$conceptId}=$moduleName;
                $moduleName{$id}=$moduleName;
		#print "$conceptId|$moduleName{$conceptId}\n";
                }
}
    close(INPUT);
}		# end getModuleName

#---------------------
# process_subsets
#---------------------
# processes subsets

sub process_subsets {
  my($languagesFile) = $$CfgRef->getReqEle('File.INP.LANGUAGESETS');
  my($subsetsFile) = $$CfgRef->getReqEle('File.INP.SUBSETS');
  my($usRefSet) = $$CfgRef->getReqEle('USREFSET');
  my($gbRefSet) = $$CfgRef->getReqEle('GBREFSET');
  my($ptCid) = $$CfgRef->getReqEle('PTCID');

  open(INPUT, "$languagesFile") or die "Can't open/read $languagesFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my ($id, $effectiveTime, $active, $moduleId, $refSetId,
        $referencedComponentId, $acceptabilityId) = split(/[\t\n]/);

    $subsetCid{$refSetId} = 1 unless $subsetCid{$refSetId};

    # save dialect & preferred-term info for use in setting TTYs of descriptions
    my($dialect) = $dialect{$referencedComponentId};
    if ($refSetId eq $usRefSet) {
      # in case already marked as preferred in GB, mark as non-pref in US:
      $prefDid{$referencedComponentId} = 0 if $active==1;
      if ("${active}US" gt $dialect) {
        $dialect = $dialect{$referencedComponentId} = "${active}US";
      }
    }
    if ($refSetId eq $gbRefSet) {
      if ("${active}GB" gt $dialect) {
        $prefDid{$referencedComponentId} = 0 if $active==1;
        $dialect = $dialect{$referencedComponentId} = "${active}GB";
      }
    }
    if ($acceptabilityId eq $ptCid) {
      if ($dialect =~ /US$/ && $refSetId eq $usRefSet) {
        $prefDid{$referencedComponentId} = 1;
      } elsif ($dialect =~ /GB$/ && $refSetId eq $gbRefSet) {
        $prefDid{$referencedComponentId} = 1;
      } elsif ($dialect =~ /^0US/ && $refSetId eq $gbRefSet) {
        $prefDid{$referencedComponentId} = 1;
      }
    }

    # dump SUBSET_MEMBER attr
    #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1 || $active{$referencedComponentId} !=1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
    # don't release subset-mem attrs for defn's since we don't make them atoms
    unless ($defnId{$referencedComponentId}) {
      foreach my $atv ("ACCEPTABILITYID\~$acceptabilityId") {
        $AttrSAUI->dumpAttr({sgId => $referencedComponentId,
                             atn => "SUBSET_MEMBER", atv => "$refSetId\~$atv",
                             suppress => $supp, satui => $id});
      }
    }

#   my $satui = $AttrSAUI->getLastId();
#   $AttrATTR->dumpAttr({sgId => $satui, atn => "REFSET_MEMBER_ID",
#                        atv => $id});
#   $AttrATTR->dumpAttr({sgId => $satui, atn => "EFFECTIVE_TIME",
#                        atv => $effectiveTime});
#   $AttrATTR->dumpAttr({sgId => $satui, atn => "ACTIVE", atv => $active});
#   $AttrATTR->dumpAttr({sgId => $satui, atn => "MODULE_ID", atv => $moduleId});
  }


  open(INPUT, "$subsetsFile") or die "Can't open/read $subsetsFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my ($id, $effectiveTime, $active, $moduleId, $refSetId,
        $referencedComponentId) = split(/[\t\n]/);

    $subsetCid{$refSetId} = 1 unless $subsetCid{$refSetId};

    # dump SUBSET_MEMBER attr
    my $attr = (defined($active{$referencedComponentId})) ? $AttrCON :
                                                            $AttrSAUI;
    #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1 || $active{$referencedComponentId} !=1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
    $attr->dumpAttr({sgId => $referencedComponentId, atn => "SUBSET_MEMBER",
                     atv => $refSetId, suppress => $supp, satui => $id});

#   my $satui = $AttrSAUI->getLastId();
#   $AttrATTR->dumpAttr({sgId => $satui, atn => "REFSET_MEMBER_ID",
#                        atv => $id});
#   $AttrATTR->dumpAttr({sgId => $satui, atn => "EFFECTIVE_TIME",
#                        atv => $effectiveTime});
#   $AttrATTR->dumpAttr({sgId => $satui, atn => "ACTIVE", atv => $active});
#   $AttrATTR->dumpAttr({sgId => $satui, atn => "MODULE_ID", atv => $moduleId});
  }
} # end process_subsets


#---------------------
# process_descrs
#---------------------
# processes descriptions

sub process_descrs {
  my($descrFile) = $$CfgRef->getReqEle('File.INP.DESCRIPTIONS');

  open(INPUT, "$descrFile") or die "Can't open/read $descrFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    $_ = iutl->cleanLine($_);
    my ($id, $effectiveTime, $active, $moduleId, $conceptId, $languageCode,
        $typeId, $term, $caseSignificanceId) = split(/[\t\n]/);
    $term =~ s/\|/&#x7C;/g;  # convert '|' characters we can't otherwise release
    $term =~ s/ +$//;
    if ($term =~ /^Retired procedure/) {
      $term .= " [$conceptId]";
    }

    my $tty = $typeId2TTY->{$typeId};
    $tty = 'PT' if $tty eq 'SY' && $prefDid{$id};

    # must do the following test before the tty refinements below because some
    # OFs (as well as FNs) need their info stored in %relCid2info
    #if ($tty eq 'FN' && $relName2info{$term} ne "" && $active ==1) {
    if ($tty eq 'FN' && $relName2info{$term} ne "" && $hasActiveRels{$conceptId} ==1) {
      my $info = $relName2info{$term};
      $relCid2info{$conceptId} = $info;
      my ($rela, $irela, $rel) = split(/\|/, $info);
      $rel = ($rel eq 'RT') ? 'RO' : ($rel eq 'NT') ? 'RN' :
             ($rel eq 'BT') ? 'RB' : $rel;
      $AttrCON->dumpAttr({sgId => $conceptId, atn => "UMLSREL", atv => $rel,
                          suppress => "N", satui => ""});
      $AttrCON->dumpAttr({sgId => $conceptId, atn => "UMLSRELA", atv => $rela,
                          suppress => "N", satui => ""});
    }

    my $supp = "N";
    if ($active == 0 || $active{$conceptId}==0 || $limited{$conceptId}) {
	next;
      #$supp = "O";
      #$tty = ($tty eq 'PT') ? 'OP' : ($tty eq 'SY') ? 'IS' : 'OF';
      #if ($active == 1) {
        #$tty = ($tty eq 'OP') ? 'OAP' : ($tty eq 'IS') ? 'OAS' : 'OAF';
      #}
    }
    if ($supp eq "N" && $dialect{$id} =~ /GB$/) {
      $tty = ($tty eq 'PT') ? 'PTGB' : 'SYGB';
    }

    $Atom->dumpAtom({str => $term, tty => $tty, code => $conceptId, saui => $id,
                     scui => $conceptId, suppress => $supp});
	$active{$id}=1;
    my $said = $Atom->getLastId();
    if ($tty eq 'PT') {
      $cid2name{$conceptId} = $term;
      $cid2said{$conceptId} = $said;
      $said2name{$said} = $term;
      $said2sgid{$said} = $conceptId;
    }
    $MergeSY->dumpMerge({sgId1 => $id, sgId2 => $conceptId,
                         sgType1 => "ROOT_SOURCE_AUI",
                         sgQual1 => "SNOMEDCT_US"});

#   $AttrSAUI->dumpAttr({sgId => $id, atn => "EFFECTIVE_TIME",
#                        atv => $effectiveTime});
#   $AttrSAUI->dumpAttr({sgId => $id, atn => "ACTIVE", atv => $active});
    if ($languageCode ne $defLang) {
      $AttrSAUI->dumpAttr({sgId => $id, atn => "LANGUAGECODE",
                           atv => $languageCode, suppress => $supp,
                           satui => ""});
    }
    if ($moduleId ne $defMod) {
		#print "IDS|$conceptId|$id|$moduleId|$moduleName{$moduleId}\n";
      $AttrSAUI->dumpAttr({sgId => $id, atn => "MODULE_ID", atv => $moduleId,
                           suppress => $supp, satui => ""});
      $AttrSAUI->dumpAttr({sgId => $id, atn => "MODULE_NAME", atv => $moduleName{$moduleId}, 
			   suppress => $supp, satui => ""});
    }
    $AttrSAUI->dumpAttr({sgId => $id, atn => "TYPE_ID", atv => $typeId,
                         suppress => $supp, satui => ""});
    $AttrSAUI->dumpAttr({sgId => $id, atn => "CASE_SIGNIFICANCE_ID",
                         atv => $caseSignificanceId, suppress => $supp,
                         satui => ""});
	}
} # end process_descrs


#---------------------
# make_sb_atoms
#---------------------
# makes SB atoms

sub make_sb_atoms {
  my($descrFile) = $$CfgRef->getReqEle('File.INP.DESCRIPTIONS');

  open(INPUT, "$descrFile") or die "Can't open/read $descrFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    $_ = iutl->cleanLine($_);
    my ($id, $effectiveTime, $active, $moduleId, $conceptId, $languageCode,
        $typeId, $term, $caseSignificanceId) = split(/[\t\n]/);
    next unless $subsetCid{$conceptId};

    $term =~ s/\|/&#x7C;/g;  # convert '|' characters we can't otherwise release
    $term =~ s/ +$//;

    my $tty = $typeId2TTY->{$typeId};
    $tty = 'PT' if $tty eq 'SY' && $prefDid{$id};
    next if $tty ne 'PT';
    next if $active == 0;
    my $supp = ($active{$conceptId}==0 || $limited{$conceptId}) ? "O" : "N";
    next if $dialect{$id} =~ /GB$/;

    # make duplicate SB atom for subset-concept PTs
    $Atom->dumpAtom({str => $term, tty => 'SB', code => $conceptId,
                     saui => "", scui => $conceptId, suppress => $supp});
    my $said = $Atom->getLastId();
    $MergeSY->dumpMerge({sgId1 => $said, sgId2 => $conceptId,
                         sgType1 => "SRC_ATOM_ID", sgQual1 => ""});
  }
} # end make_sb_atoms


#---------------------
# process_rels
#---------------------
# processes rels

sub process_rels {
  my($file) = shift;
  my($charTypeQualifier) = $$CfgRef->getReqEle('CHARTYPEQUALIFIER');

  open(INPUT, "$file") or die "Can't open/read $file, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my($id, $effectiveTime, $active, $moduleId, $sourceId, $destinationId,
       $relationshipGroup, $typeId, $characteristicTypeId,
       $modifierId) = split(/[\t\n]/);

    if ($typeId eq "116680003" && $active==1) {
      # invert as context
      $$HierRef->addParChild($cid2said{$destinationId}, $cid2said{$sourceId});
      $cids2rinfo{"$sourceId|$destinationId"} = "$id|$relationshipGroup";
    } else {
      if ($mandRefin{$id} && $characteristicTypeId eq $charTypeQualifier) {
        # invert as AQ attr, either active or obsolete
        #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
        my($refinMandatory) = $$CfgRef->getReqEle('REFINMANDATORY');
        my($atv) =  $cid2name{$typeId};
        $AttrCON->dumpAttr({sgId => $sourceId, atn => "AQ", atv => $atv,
                            suppress => $supp, satui => ""});
      } else {
        my $info = $relCid2info{$typeId};
        my($rela, $irela, $rel) = split(/\|/, $info);
        if ($info eq '') {
          $rel = 'XX-' . $typeId;
        }
        #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
        $RelationR->dumpRel({sgId1 => $destinationId, sgId2 => $sourceId,
                             rel => $rel, rela => $rela, srui => $id,
                             relGroup => $relationshipGroup,
                             suppress => $supp});
#       $AttrREL->dumpAttr({sgId => $id, atn => "EFFECTIVE_TIME",
#                           atv => $effectiveTime});
#       $AttrREL->dumpAttr({sgId => $id, atn => "ACTIVE", atv => $active});
        if ($moduleId ne $defMod) {
          $AttrREL->dumpAttr({sgId => $id, atn => "MODULE_ID", atv => $moduleId,
                              suppress => $supp, satui => ""});
      $AttrREL->dumpAttr({sgId => $id, atn => "MODULE_NAME", atv => $moduleName{$moduleId},
                           suppress => $supp, satui => ""});
        }
        #Do not dump CHARACTERISTIC_TYPE_ID or MODIFIER_ID for NCI
        #$AttrREL->dumpAttr({sgId => $id, atn => "CHARACTERISTIC_TYPE_ID",
                            #atv => $characteristicTypeId, suppress => $supp,
                            #satui => ""});
        #$AttrREL->dumpAttr({sgId => $id, atn => "MODIFIER_ID",
                            #atv => $modifierId, suppress => $supp,
                            #satui => ""});

        # generate mergefacts for SAME AS historical association rels
        if ($rela eq "same_as") {
          $MergeSAME->dumpMerge({sgId1 => $sourceId, sgId2 => $destinationId});
        }
      }
    }
  }
} # end process_rels


#---------------------
# process_assocs
#---------------------
# processes assocs

sub process_assocs {
  my($assocsFile) = $$CfgRef->getReqEle('File.INP.ASSOCIATIONS');

  open(INPUT, "$assocsFile") or die "Can't open/read $assocsFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    my($id, $effectiveTime, $active, $moduleId, $refSetId,
       $referencedComponentId, $targetComponent) = split(/[\t\n]/);

    $subsetCid{$refSetId} = 1 unless $subsetCid{$refSetId};

    my $info = $relCid2info{$refSetId};
    my($rela, $irela, $rel) = split(/\|/, $info);
    #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1 || $active{$referencedComponentId} !=1 || $active{$targetComponent} != 1);
    	#next if ($active != 1 || $active{$referencedComponentId} !=1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
    my $attr = (defined($conActive{$referencedComponentId})) ? $AttrCON :
                                                            $AttrSAUI;
    foreach my $atv ("TARGETCOMPONENT\~$targetComponent") {
      $attr->dumpAttr({sgId => $referencedComponentId,
                       atn => "SUBSET_MEMBER", atv => "$refSetId\~$atv",
                       suppress => $supp, satui => $id});
    }

    my $sgType2 = (defined($active{$referencedComponentId})) ? 'SOURCE_CUI'
                                                             : 'SOURCE_AUI';
    if ($rel ne "")
	{
    $RelationA->dumpRel({sgId1 => $targetComponent,
                         sgId2 => $referencedComponentId, rel => $rel,
                         rela => $rela, srui => $id, sgType2 => $sgType2,
                         relGroup => "", suppress => $supp});
	}
#   $AttrREL->dumpAttr({sgId => $id, atn => "EFFECTIVE_TIME",
#                       atv => $effectiveTime});
#   $AttrREL->dumpAttr({sgId => $id, atn => "ACTIVE", atv => $active});
    if ($moduleId ne $defMod) {
      $AttrREL->dumpAttr({sgId => $id, atn => "MODULE_ID", atv => $moduleId,
                          suppress => $supp, satui => ""});
    }

    # generate mergefacts for SAME AS historical association rels
    if ($rela eq "same_as" && $active == 1) {
      $MergeSAME->dumpMerge({sgId1 => $referencedComponentId,
                             sgId2 => $targetComponent});
    }
  }
} # end process_assocs


#---------------------
# process_mappings
#---------------------
# processes mappings

sub process_mappings {
  # process Complex mappings (ICD-9-CM)
  my($mappingsFile) = $$CfgRef->getReqEle('File.INP.COMPLEXMAPS');
  my($mapInfo) = $$CfgRef->getHashRef("MAPINFO");
  my($nocomplex) = '';

  my($VSAB) = $$CfgRef->getReqEle('VSAB');
  my($version) = $$CfgRef->getReqEle('EngNum');
#  my($XRid) = $$CfgRef->getReqEle('MAPSETXRTARGETID');
  my($XMsaid) = "";
  my(%mapCount) = ();
  my(%seen) = ();
  open(INPUT, "$mappingsFile") or $nocomplex=1;
  unless ($nocomplex) {
    $_ = <INPUT>;  # skip header line
    while (<INPUT>) {
      s/\r$//;
      my ($id, $effectiveTime, $active, $moduleId, $refSetId,
          $referencedComponentId, $mapGroup, $mapPriority, $mapRule, $mapAdvice,
          $mapTarget, $correlationId) = split(/[\t\n]/);

      next unless defined($active{$referencedComponentId});
      ++$mapCount{$referencedComponentId} if $active == 1;
      $subsetCid{$refSetId} = 1 unless $subsetCid{$refSetId};

      if ($VSAB ne "") {
        # make XM atom using $refSetId as code/scui

  ### The "2013" below is from der1_CrossMapSets_ICD9_US1000124_20140901.txt in
  ### orig/fromprovider/SnomedCT_Release_US1000124_20140901/RF1Release/Maps/ICD9
        my($ICDversion) = $$CfgRef->getReqEle('MappingTarget.ICD9CM.Version');

        $Atom->dumpAtom({str => "$VSAB to ICD9CM_$ICDversion Mappings",
                         tty => 'XM', code => $refSetId, saui => "",
                         scui => $refSetId, suppress => "N"});
        $XMsaid = $Atom->getLastId();
        $MergeSY->dumpMerge({sgId1 => $XMsaid, sgId2 => $refSetId,
                             sgType1 => "SRC_ATOM_ID", sgQual1 => ""});

        my $sos = "This set maps SNOMEDCT_US concept identifiers to ICD-9-CM"
                  . " codes; a single SNOMEDCT_US concept id may be mapped to one"
                  . " or more ICD-9-CM codes";

        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETSID",
                             atv => $refSetId, suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETNAME",
                             atv => $cid2name{$refSetId}, suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETVERSION",
                             atv => $version, suppress => "N"});
#        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETXRTARGETID",
#                             atv => $XRid, suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETRSAB",
                             atv => "SNOMEDCT_US", suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETVSAB",
                             atv => $VSAB, suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "FROMRSAB",
                             atv => "SNOMEDCT_US", suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "FROMVSAB",
                             atv => $VSAB, suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "TORSAB",
                             atv => "ICD9CM", suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "TOVSAB",
                             atv => "ICD9CM_$ICDversion", suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "SOS", atv => $sos,
                             suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MTH_MAPSETCOMPLEXITY",
                             atv => "N_TO_N", suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MTH_MAPFROMCOMPLEXITY",
                             atv => "SINGLE SCUI", suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MTH_MAPTOCOMPLEXITY",
                             atv => "SINGLE SDUI, MULTIPLE SDUI",
                             suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MTH_MAPFROMEXHAUSTIVE",
                             atv => "N", suppress => "N"});
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MTH_MAPTOEXHAUSTIVE",
                             atv => "N", suppress => "N"});

        $VSAB = "";
      }

      my $info = $mapInfo->{$correlationId};
      my($rel, $rela) = split(/\|/, $info);
      #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	#next if ($active != 1 || $active{$referencedComponentId} !=1);
    	next if ($active != 1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
      $mapRule = iutl->cleanLine($mapRule);
      $mapAdvice = iutl->cleanLine($mapAdvice);
      foreach my $atv ("MAPGROUP\~$mapGroup",
                        "MAPPRIORITY\~$mapPriority",
                        "MAPRULE\~$mapRule",
                        "MAPADVICE\~$mapAdvice",
                        "MAPTARGET\~$mapTarget",
                        "CORRELATIONID\~$correlationId") {
        $AttrCON->dumpAttr({sgId => $referencedComponentId,
                            atn => "SUBSET_MEMBER", atv => "$refSetId\~$atv",
                            suppress => $supp, satui => $id});
      }

      next unless $active == 1;       # no MRMAP data for inactive mappings!

      $mapTarget =~ tr/a-z/A-Z/;   # fix lowercase e and v codes
      my($targetId) = $mapTarget;
      if ($targetId eq '') {
        #targetId = $XRid;
        $targetId = '';
        $rel = 'XR';
      }
      my $atv = "${mapGroup}~${mapPriority}~${referencedComponentId}~${rel}~" .
                "${rela}~${targetId}~${mapRule}~${correlationId}~ACTIVE~" .
                "$active~${id}~$mapAdvice";
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "XMAP", atv => $atv,
                           suppress => $supp});
  #   my $satui = $AttrSAID->getLastId();
  #   $AttrATTR->dumpAttr({sgId => $satui, atn => "EFFECTIVE_TIME",
  #                        atv => $effectiveTime});
  #   $AttrATTR->dumpAttr({sgId => $satui, atn => "ACTIVE", atv => $active});
  #   $AttrATTR->dumpAttr({sgId => $satui, atn => "MODULE_ID", atv => $moduleId});

      unless ($seen{$referencedComponentId}++) {
        $atv = "${referencedComponentId}~~${referencedComponentId}~SCUI~~";
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "XMAPFROM", atv => $atv,
                             suppress => $supp});
      }
      unless ($seen{$mapTarget}++) {
        $atv = "${targetId}~~${mapTarget}~SDUI~~";
        $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "XMAPTO", atv => $atv,
                             suppress => $supp});
      }
    }
    close(INPUT);


    # make relationships for 1-to-1 mappings
    open(INPUT, "$mappingsFile") or die "Can't open/read $mappingsFile, $!";
    $_ = <INPUT>;  # skip header line
    while (<INPUT>) {
      s/\r$//;
      my ($id, $effectiveTime, $active, $moduleId, $refSetId,
          $referencedComponentId, $mapGroup, $mapPriority, $mapRule, $mapAdvice,
          $mapTarget, $correlationId) = split(/[\t\n]/);

      if ($mapCount{$referencedComponentId} == 1 && $active == 1 &&
          $mapTarget ne "" && $mapTarget !~ /\|/) {
        my $info = $mapInfo->{$correlationId};
        my($rel, $rela) = split(/\|/, $info);
        #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
        $mapTarget =~ tr/a-z/A-Z/;   # fix lowercase e and v codes

        #$RelationM->dumpRel({sgId1 => $mapTarget, sgId2 => $referencedComponentId,
                             #rel => $rel, rela => $rela,
                             #srui => "", relGroup => "", suppress => $supp,
                             #sgType1 => "CODE_ROOT_SOURCE", sgQual1 => "ICD9CM",
                             #sgType2 => "SOURCE_CUI"});
      }
    }
  }


  # process Extended mappings (ICD-10, ICD-10-CM)
  $mappingsFile = $$CfgRef->getReqEle('File.INP.EXTENDEDMAPS');
  open(INPUT, "$mappingsFile") or die "Can't open/read $mappingsFile, $!";
  $_ = <INPUT>;  # skip header line

  my($i10id) = "447562003";
  my($i10cmid) = "6011000124106";
  my($VSAB) = $$CfgRef->getReqEle('VSAB');
  my($VSAB1) = $VSAB;
  my($VSAB2) = $VSAB;
  my($XMsaid1, $XMsaid2) = "";
  %mapCount = ();
  %seen = ();
  while (<INPUT>) {
    s/\r$//;
    my ($id, $effectiveTime, $active, $moduleId, $refSetId,
        $referencedComponentId, $mapGroup, $mapPriority, $mapRule, $mapAdvice,
        $mapTarget, $correlationId, $mapCategoryId) = split(/[\t\n]/);

    next unless defined($active{$referencedComponentId});
    $subsetCid{$refSetId} = 1 unless $subsetCid{$refSetId};

    $mapRule =~ s/\|/&#x7C;/g;  # convert '|' chars we can't otherwise release
    $mapAdvice =~ s/\|/&#x7C;/g;  # convert '|' chars we can't otherwise release
    $mapRule = iutl->cleanLine($mapRule);
    $mapAdvice = iutl->cleanLine($mapAdvice);
    ++$mapCount{"$refSetId|$referencedComponentId"} if $active == 1;
    if (($VSAB1 ne "" && $refSetId eq $i10id) ||
        ($VSAB2 ne "" && $refSetId eq $i10cmid)) {
      # make XM atom using $refSetId as code/scui

      my($ICDRSAB) = ($refSetId eq $i10id) ? "ICD10" :
                     ($refSetId eq $i10cmid) ? "ICD10CM" :
                     "UNKNOWN";
### The "2016" below is from section 2 of the documentation at
### https://confluence.ihtsdotools.org/display/DOCICD10/2.+ICD-10+Map+Overview
### The "2025" below would be[is] from section 1.2 of the documentation at:
### https://confluence.ihtsdotools.org/display/RMT/SNOMED+CT+Managed+Service+-+US+Edition+SNOMED+CT+to+ICD-10-CM+Release+Notes+-+September+2025
## (that section looks corrupted but I assumed it's the 2025 release)
      my($ICDVSAB) = ($refSetId eq $i10id) ? $$CfgRef->getReqEle('MappingTarget.ICD10') :
                     ($refSetId eq $i10cmid) ? $$CfgRef->getReqEle('MappingTarget.ICD10CM') :
                     "UNKNOWN";

      $Atom->dumpAtom({str => "$VSAB to $ICDVSAB Mappings",
                       tty => 'XM', code => $refSetId, saui => "",
                       scui => $refSetId, suppress => "N"});
      $XMsaid = $Atom->getLastId();
      if ($refSetId eq $i10id) {
        $XMsaid1 = $XMsaid;
      } elsif ($refSetId eq $i10cmid) {
        $XMsaid2 = $XMsaid;
      }
      $MergeSY->dumpMerge({sgId1 => $XMsaid, sgId2 => $refSetId,
                           sgType1 => "SRC_ATOM_ID", sgQual1 => ""});

      my($ICDname) = ($refSetId eq $i10id) ? "ICD-10" :
                     ($refSetId eq $i10cmid) ? "ICD-10-CM" :
                     "UNKNOWN";
      my $sos = "This set maps SNOMEDCT_US concept identifiers to $ICDname"
                . " codes; a single SNOMEDCT_US concept id may be mapped to"
                . " one or more $ICDname codes";

      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETSID",
                           atv => $refSetId, suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETNAME",
                           atv => $cid2name{$refSetId}, suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETVERSION",
                           atv => $version, suppress => "N"});
#      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETXRTARGETID",
#                           atv => $XRid, suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETRSAB",
                           atv => "SNOMEDCT_US", suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MAPSETVSAB",
                           atv => $VSAB, suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "FROMRSAB",
                           atv => "SNOMEDCT_US", suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "FROMVSAB",
                           atv => $VSAB, suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "TORSAB",
                           atv => $ICDRSAB, suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "TOVSAB",
                           atv => $ICDVSAB, suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "SOS", atv => $sos,
                           suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MTH_MAPSETCOMPLEXITY",
                           atv => "N_TO_N", suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MTH_MAPFROMCOMPLEXITY",
                           atv => "SINGLE SCUI", suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MTH_MAPTOCOMPLEXITY",
                           atv => "SINGLE SDUI, MULTIPLE SDUI",
                           suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MTH_MAPFROMEXHAUSTIVE",
                           atv => "N", suppress => "N"});
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "MTH_MAPTOEXHAUSTIVE",
                           atv => "N", suppress => "N"});

      $VSAB1 = "" if $refSetId eq $i10id;
      $VSAB2 = "" if $refSetId eq $i10cmid;
    }

    my $info = $mapInfo->{$correlationId};
    my($rel, $rela) = split(/\|/, $info);
    #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
    foreach my $atv ("MAPGROUP\~$mapGroup",
                      "MAPPRIORITY\~$mapPriority",
                      "MAPRULE\~$mapRule",
                      "MAPADVICE\~$mapAdvice",
                      "MAPTARGET\~$mapTarget",
                      "CORRELATIONID\~$correlationId",
                      "MAPCATEGORYID\~$mapCategoryId") {
	if ($refSetId != 6011000124106 && $refSetId != 447562003)
		{
      $AttrCON->dumpAttr({sgId => $referencedComponentId,
                          atn => "SUBSET_MEMBER", atv => "$refSetId\~$atv",
                          suppress => $supp, satui => $id});
			}
    }

    next unless $active == 1;       # no MRMAP data for inactive mappings!

    if ($refSetId eq $i10id) {
      $XMsaid = $XMsaid1;
    } elsif ($refSetId eq $i10cmid) {
      $XMsaid = $XMsaid2;
    }

    $mapTarget =~ tr/a-z/A-Z/;   # fix lowercase e and v codes
    my($targetId) = $mapTarget;
    if ($targetId eq '') {
      #$targetId = $XRid;
      $targetId = '';
      $rel = 'XR';
    }
    my $atv = "${mapGroup}~${mapPriority}~${referencedComponentId}~${rel}~" .
              "${rela}~${targetId}~${mapRule}~${mapCategoryId}~ACTIVE~" .
              "$active~${id}~${mapAdvice}";
    $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "XMAP", atv => $atv,
                         suppress => $supp});
#   my $satui = $AttrSAID->getLastId();
#   $AttrATTR->dumpAttr({sgId => $satui, atn => "EFFECTIVE_TIME",
#                        atv => $effectiveTime});
#   $AttrATTR->dumpAttr({sgId => $satui, atn => "ACTIVE", atv => $active});
#   $AttrATTR->dumpAttr({sgId => $satui, atn => "MODULE_ID", atv => $moduleId});

    unless ($seen{"$XMsaid|$referencedComponentId"}++) {
      $atv = "${referencedComponentId}~~${referencedComponentId}~SCUI~~";
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "XMAPFROM", atv => $atv,
                           suppress => $supp});
    }
    unless ($seen{"$XMsaid|$mapTarget"}++) {
      $atv = "${targetId}~~${mapTarget}~SDUI~~";
      $AttrSAID->dumpAttr({sgId => $XMsaid, atn => "XMAPTO", atv => $atv,
                           suppress => $supp});
    }
  }
  close(INPUT);


  my($icdFile) = $$CfgRef->getReqEle('File.INP.ICD10META');

  my %icd10meta = ();
  open(INPUT, "$icdFile") or die "Can't open/read $icdFile, $!";
  while (<INPUT>) {
    chomp;
    $icd10meta{$_} = 1;
  }

  my($icdcmFile) = $$CfgRef->getReqEle('File.INP.ICD10CMMETA');

  my %icd10cmmeta = ();
  open(INPUT, "$icdcmFile") or die "Can't open/read $icdcmFile, $!";
  while (<INPUT>) {
    chomp;
    $icd10cmmeta{$_} = 1;
  }

  # make relationships for 1-to-1 mappings
  open(INPUT, "$mappingsFile") or die "Can't open/read $mappingsFile, $!";
  $_ = <INPUT>;  # skip header line
  while (<INPUT>) {
    s/\r$//;
    my ($id, $effectiveTime, $active, $moduleId, $refSetId,
        $referencedComponentId, $mapGroup, $mapPriority, $mapRule, $mapAdvice,
        $mapTarget, $correlationId, $mapCategoryId) = split(/[\t\n]/);

    if ($mapCount{"$refSetId|$referencedComponentId"} == 1 && $active == 1 &&
        $mapTarget ne "" && $mapTarget !~ /\|/ &&
        (($refSetId eq $i10id && $icd10meta{$mapTarget}) ||
         ($refSetId eq $i10cmid && $icd10cmmeta{$mapTarget}))) {
      my $info = $mapInfo->{$correlationId};
      my($rel, $rela) = split(/\|/, $info);
      #my($supp) = ($active==1) ? "N" : "O";
    	my $supp;
    	next if ($active != 1);
    	if ($active ==1)
		{ 
		$supp = "N";
		}
      $mapTarget =~ tr/a-z/A-Z/;   # fix lowercase e and v codes

      my($sgQual1) = ($refSetId eq $i10id) ? "ICD10" :
                     ($refSetId eq $i10cmid) ? "ICD10CM" : "UNKNOWN";
      #$RelationM->dumpRel({sgId1 => $mapTarget, sgId2 => $referencedComponentId,
                           #rel => $rel, rela => $rela,
                           #srui => "", relGroup => "", suppress => $supp,
                           #sgType1 => "CODE_ROOT_SOURCE", sgQual1 => $sgQual1,
                           #sgType2 => "SOURCE_CUI"});
    }
  }
} # end process_mappings


sub dumpCxts {
  my ($cid, $said, $parSaid, $cxt, $cxtnum, $parCid, $term, $srui, $sgrp);
  my ($aval, $hcd);

  # form and dump context info
  $$HierRef->prepareCxts;

  my $parRef  = $$HierRef->getParentsRef;
  my $chldRef = $$HierRef->getChildrenRef;
  my $pathRef = $$HierRef->getParentPathsRef;

  # first dump the root node's context attribute.
#  $$HierRef->setRoot($cid2said{138875005});
  $said = $cid2said{138875005};
  $term = $said2name{$said};
  $AttrCXT->dumpAttr({sgId => $said, atv => "1\t::~~~~~~\t\t$term\t\t"});

  foreach $said (sort keys %{$parRef}) {
    $cxtnum = 0;
    foreach $cxt (@{ $$pathRef{$said} }) {
      $cxtnum++;
      $cxt =~ s/\|/./g;

      $cid = $said2sgid{$said};
      ($parSaid) = reverse(split(/\./, $cxt));
      $parCid = $said2sgid{$parSaid};
      ($srui, $sgrp) = split(/\|/, $cids2rinfo{"$cid|$parCid"});

      $ContextPAR->dumpCxt2({srcAtomId1 => $said, ptr => $cxt,
			 sgId1 => $cid, sgId2 => $parCid, srui => $srui});

      # dump only the first 10 context attrs per node.
      if ($cxtnum < 11) {
	$aval = join('~', (map { $said2name{$_} } (split(/\./, $cxt))));
	$hcd = "$cxtnum\t:$srui:$sgrp~$said~ROOT_SOURCE_CUI~SNOMEDCT_US~"
	         . "$parSaid~ROOT_SOURCE_CUI~SNOMEDCT_US";
	$term = $said2name{"$said"};
	$AttrCXT->dumpAttr({sgId => $said, atv => "$hcd\t$aval\t$term\t\t"});
      } elsif ($cxtnum == 11) {
	$hcd = "$cxtnum\t::~$said~ROOT_SOURCE_CUI~SNOMEDCT_US~"
	         . "$parSaid~ROOT_SOURCE_CUI~SNOMEDCT_US";
	$AttrCXT->dumpAttr({sgId => $said,
	    atv => "$hcd\t\tSNOMED CT Concept\tMore Concepts not shown\t\t"});
      }
    }
  }
} # end dumpCxts


#---------------------
# get_description_status
#---------------------
# need description before writing attributes

sub get_description_status {
  my($descrFile) = $$CfgRef->getReqEle('File.INP.DESCRIPTIONS');

  open(INPUT, "$descrFile") or die "Can't open/read $descrFile, $!";
  $_ = <INPUT>;  # skip header line

  while (<INPUT>) {
    s/\r$//;
    $_ = iutl->cleanLine($_);
    my ($id, $effectiveTime, $active, $moduleId, $conceptId, $languageCode,
        $typeId, $term, $caseSignificanceId) = split(/[\t\n]/);
    if ($active == 0 || $active{$conceptId}==0 || $limited{$conceptId}) {
	$active{$id}=0;
	}
	else {$active{$id}=1;}
}
}	

#sub dumpCxts {
##  $$HierRef->setRoot($cid2said{138875005});
#  $$HierRef->dumpCxtsAttrs(\$ContextPAR,   # obj to dump root cxt
#                           \$ContextPAR,   # obj to dump par cxts
#                           0,              # obj to dump sib cxts
#                           \$AttrCXT,      # obj to dump attrs
#                           \%said2name,    # tag to name hash
#                           0,              # tag to said hash
#                           \%said2sgid,    # tag to sgid hash
#                           0,              # don't dump children in attrs
#                           0);             # don't dump sibs in attrs
#} # end dumpCxts




# remove subscripts and superscripts.
sub removeSubSup {
  my ($prevChar, $str, $nextChar) = @_;
  # we decide whether to insert spaces before and after the string.

  # remove the delimeters [<> or ^^] from the begin and end.
  my $actStr    = substr($str, 1, length($str) - 2);
  my $firstChar = substr($actStr, 0, 1);
  my $lastChar  = substr($actStr, length($actStr) - 1, 1);

  # insert a spapce if prevChar and firstChar are of the same type.
  # insert a space if precChar is UC and firstChar is LC
  my $prevSpace = '';
  if ((defined($charType{$prevChar})
       && $charType{$prevChar} eq $charType{$firstChar})
      || ($charType{$prevChar} eq 'uc' && $charType{$firstChar} eq 'lc')) {
    $prevSpace = ' ';
  }

  # insert a space if both lastChar and nextChar are of the same type.
  # insert a space if lastChar is either UC/LC/NC and nextChar is UC
  # insert a space if lastChar is NC and nextChar is LC
  my $nextSpace = '';
  if ( (defined($charType{$nextChar})
        && $charType{$nextChar} eq $charType{$lastChar})
       || ($charType{$nextChar} eq 'uc' && defined($valChars{$lastChar}))
       || ($charType{$nextChar} eq 'lc' && $charType{$lastChar} eq 'nc')) {
    $nextSpace = ' ';
  }
  return "$prevChar$prevSpace$actStr$nextSpace$nextChar";
} # end removeSubSup

sub getNoSSTerm {
  my $str = shift;
  while ($str =~ s/$pat1/&removeSubSup($1,$2,$3)/e) {
  }
  return $str;
} # end getNoSSTerm

sub getTagsTerm {
  my $str = shift;
  $str =~ s/$pat2a/<sub>$2<\/sub>/g;
  $str =~ s/$pat2b/<sup>$2<\/sup>/g;
  $str =~ s/\\/</g;
  $str =~ s/\`/>/g;
  return $str;
} # end getTagsTerm


#-----------------
# Common Utilities
#-----------------

# Check prerequisites
sub checkPrerequisites {
  # Check required config file properties
  my $IN;
  open ($IN, "<:utf8", "$Bin/../etc/sct.cfg") || 
    croak "ERROR: Missing config file: etc/sct.cfg\n";
  my @lines = <$IN>;
  close ($IN);
  foreach my $prop ( ("SaidStart", "File.INP.CONCEPTS", "File.INP.DESCRIPTIONS",
                      "File.INP.RELATIONS", "File.INP.LANGUAGESETS") ) {
    my ($line) = grep /^$prop/, @lines;
    if (! $line) {
      $$LogRef->logError("ERROR: Config file is missing $prop property\n");
      exit 1;
    }
  }
  $$LogRef->logDebug("PASSED:  All prerequisite properties and files exist.\n");

}

# Print usage.
sub printUsage {
    print "Usage: invert_rf2.pl [-h] [-c]\n";
}

# Print help.
sub printHelp {
    printUsage();
    print qq{
  Inverts SNOMEDCT_US (RF2 format).

  Options:
    -h:      Prints this help message
    -c:      Checks prerequisites

};
    exit 0;
}
