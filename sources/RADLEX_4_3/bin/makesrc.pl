#!/usr/bin/perl
#
unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";

use strict 'vars';
use strict 'subs';

use Carp;
use Getopt::Long;
use NLMInv;
use SrcBldr;
use Atom;
use Attribute;
use Relation;
use Merge;
use Context;
use iutl;

#---------------------
# Declare Global Variables
#---------------------
# Framework References
our ($Inv, $CfgRef, $LogRef, $HierRef);

# Template References
our ($isAtom, $isSaid, $opAtom, $ptAtom, $syAtom,$syneAtom, $acrAtom, $ptSaid, $ptCui, $opCui, $sySaid, $acrSaid, $opSaid, $id, $fldVal, $parRID, $lstSaid, $rela);
our ($allAttr, $styAttr, $contextAttr);
our ($btRel, $ntRel, $rtRel);
our ($syMerge, $acrMerge);
our ($parCxt, $rootCxt, $sibCxt, $parRID);
our (@txt);
our %txt = ();
our %said2name = ();
our %said2sgid = ();
our %id2said = ();
our %dupHash = ();


# VSAB Variables
our ($vsab) = ("");
our ($rootSaid) = 0;
our ($rootName) = ("");
our ($rootCode) = ("");
#---------------------
# Process Options
#---------------------
use Getopt::Long;
GetOptions(q{-help|?|h} => sub { printHelp();},);


#---------------------
# Run the program
#---------------------
main();
exit 0;

#---------------------
# constant data
#--------------------
our $vsab = 'NONE';
our $rsab = 'NONE';


#---------------------
# Main
#---------------------
# Main program.
sub main {

  # Initialize the framework and get the cfg, log, hier etc.
  $Inv = new NLMInv("../etc/RADLEX.cfg");
  $CfgRef = $Inv->getCfg();
  $LogRef = $Inv->getLog();
  $HierRef = $Inv->getHier();
  $Inv->prTime("Begin");
  $Inv->invBegin;

  # Initialize application, process .src files.
  init();
  #readStyInfo();
  my $srcBldr = new SrcBldr();
  $srcBldr->processSrc;
  $Inv->prTime("Done SRC building");

  # Process the main atoms file supplied.
  processRADLEX();
  $Inv->prTime("Done processing RADLEX atoms");
  getParChd();
  $Inv->prTime("Done getting Parent Child data");
  $$HierRef->dumpCxtsAttrs(\$rootCxt, \$parCxt, 0, \$contextAttr, \%said2name, 0, \%said2sgid, 0, 1);
  $$HierRef->dumpParChild();
  #
  # Close the framework (release resources)
  $Inv->invEnd();
}

#---------------------
# Initialize Variables
#---------------------
# Initializes framework.
sub init {

  $rsab = $$CfgRef->getEle('RSAB');
  $vsab = $$CfgRef->getEle('VSAB');

  # Create core data templates.
  $isAtom = new Atom('Atom.IS');
  $opAtom = new Atom('Atom.OP');
  $ptAtom = new Atom('Atom.PT');
  $syAtom = new Atom('Atom.SY');
  $syneAtom = new Atom('Atom.SYNE');
  $acrAtom = new Atom('Atom.ACR');

  $allAttr = new Attribute('Attribute.ALL');
  $styAttr = new Attribute('Attribute.STY');

  $acrMerge = new Merge('Merge.ACR');
  $syMerge = new Merge('Merge.SY');

  $btRel = new Relation('Relation.BT');
  $ntRel = new Relation('Relation.NT');
  $rtRel = new Relation('Relation.RT');

  $rootSaid = $$CfgRef->getReqEle("HC.RootNodeSaid");
  $rootName = $$CfgRef->getReqEle("HC.RootNodeName");
  $rootCode= $$CfgRef->getReqEle("HC.RootNodeCode");
  $said2name{"$rootSaid"} =  $rootName;
  $said2sgid{"$rootSaid"}= $rootCode;
  $contextAttr = new Attribute("Attribute.CONTEXT");
  $parCxt = new Context("Context.PAR");
  $rootCxt = new Context("Context.ROOT");  
  $sibCxt = new Context ("Context.SIB");
}


#sub readStyInfo {
#  open (IN, "<:utf8", $$CfgRef->getEle('File.INP.StyTermIds'))
#    or croak("Can't find Source File, $!");
#  my ($styCode,$ign,$sty);
#  while (<IN>) {
#    chomp;
#    ($styCode,$ign,$sty)=split(/\|/);
#    $styCode2Sty{$styCode}=$sty;
#    $styCode2Sty{substr($styCode,0,1)}=$sty;
#  }
#
#}

sub processRADLEX {

  $$LogRef->logDebug("Processing RADLEX File.\n");
  $$LogRef->logDebug("Processing atoms.\n");
  my $srcFile = $$CfgRef->getReqEle("File.Terms");

  open(TERMS, "<:utf8", $srcFile) or croak("Can't find $srcFile, $!");
  open(OUT, ">../tmp/par_chd_id");
  open(OUT2, ">../tmp/par_chd_said");

  while (<TERMS>) {
 	chomp;
	my ($id,$fldVal,$parRID);
   	my $prTemp = $_;

	#Split into fields, preserving empty trailing fields
	my @txt = split(/\|/,$prTemp, -1);

	#Skip header
	next if defined $txt[0] && $txt[0] eq 'Class ID';
	
	#Safely fetch fields (undef -> empty string)
	my $f0 = $txt[0] // '';
	my $f1 = $txt[1] // '';
	my $f3 = $txt[3] // '';
	my $f7 = $txt[7] // '';
	my $f8 = $txt[8] // '';
	my $f11 = $txt[11] // '';
	my $f12 = $txt[12] // '';
	my $f13 = $txt[13] // '';
	my $f14 = $txt[14] // '';
	my $f15 = $txt[15] // '';
	my $f16 = $txt[16] // '';
	my $f17 = $txt[17] // '';
	my $f18 = $txt[18] // '';
	my $f19 = $txt[19] // '';
	my $f20 = $txt[20] // '';
	my $f21 = $txt[21] // '';
	my $f22 = $txt[22] // '';
	my $f23 = $txt[23] // '';
	my $f24 = $txt[24] // '';
	my $f25 = $txt[25] // '';
	my $f27 = $txt[27] // '';
	my $f29 = $txt[29] // '';
	my $f30 = $txt[30] // '';
	my $f32 = $txt[32] // '';
	my $f33 = $txt[33] // '';
	my $f34 = $txt[34] // '';
	my $f35 = $txt[35] // '';
	my $f36 = $txt[36] // '';
	my $f37 = $txt[37] // '';
	my $f38 = $txt[38] // '';
	my $f39 = $txt[39] // '';
	my $f40 = $txt[40] // '';
	my $f41 = $txt[41] // '';
	my $f42 = $txt[42] // '';
	my $f43 = $txt[43] // '';
	my $f44 = $txt[44] // '';
	my $f45 = $txt[45] // '';
	my $f46 = $txt[46] // '';
	my $f47 = $txt[47] // '';
	my $f48 = $txt[48] // '';
	my $f49 = $txt[49] // '';
	my $f50 = $txt[50] // '';
	my $f51 = $txt[51] // '';
	my $f53 = $txt[53] // '';
	my $f54 = $txt[54] // '';
	my $f55 = $txt[55] // '';
	my $f57 = $txt[57] // '';
	my $f58 = $txt[58] // '';
	my $f59 = $txt[59] // '';
	my $f60 = $txt[60] // '';
	my $f61 = $txt[61] // '';
	my $f62 = $txt[62] // '';
	my $f63 = $txt[63] // '';
	my $f64 = $txt[64] // '';
	my $f65 = $txt[65] // '';
	my $f66 = $txt[66] // '';
	my $f67 = $txt[67] // '';
	my $f68 = $txt[68] // '';
	my $f69 = $txt[69] // '';
	my $f70 = $txt[70] // '';
	my $f71 = $txt[71] // '';
	my $f72 = $txt[72] // '';
	my $f73 = $txt[73] // '';
	my $f74 = $txt[74] // '';
	my $f75 = $txt[75] // '';
	my $f76 = $txt[76] // '';
	my $f77 = $txt[77] // '';
	my $f79 = $txt[79] // '';
	my $f80 = $txt[80] // '';

	if($f7 ne ''){	#Parent
		foreach $fldVal (split (/__pipe__/, $f7)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$parRID = $1;
			}
		}
	}

	if($f63 ne ''){  #RID number
		if($f1 =~ /RID/){
			print OUT "$parRID|$f63\n";
		}
		else{
			my $lstSaid = $ptSaid = $ptAtom->dumpAtom({code => $f63, str => $f1, scui => $f63});
			print OUT "$parRID|$f63\n";
			$said2name{$lstSaid}=$f1;    
			$said2sgid{$lstSaid}=$f63;
			$id2said{$f63}=$lstSaid;
		}
		$parRID = '';
	}

	if($f3 ne ''){	#Definition
		foreach $fldVal (split (/__pipe__/, $f3)){
			$allAttr->dumpAttr({sgId => $f63, atn => 'DEFINITION', atv => $fldVal});
		}
		$fldVal = '';
	}


	if($f11 ne ''){	#ACR
		foreach $fldVal (split (/__pipe__/, $f11)){
			$acrSaid = $acrAtom->dumpAtom({code => $f63, str => $fldVal, scui => $f63});
			$acrMerge->dumpMerge({sgId1 => $ptSaid, sgId2 => $acrSaid});
		}
		$fldVal = '';
	}	

	if($f12 ne ''){	#anatomical_site
		foreach $fldVal (split (/__pipe__/, $f12)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'anatomical_site';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63})
			}	
		}
		$fldVal = '';
	}
	if($f13 ne ''){	#anterior_to
		foreach $fldVal (split (/__pipe__/, $f13)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'anterior_to';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f14 ne ''){	#attaches_to
		foreach $fldVal (split (/__pipe__/, $f14)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'attaches_to';
                		$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f15 ne ''){	#blood_supply_of
		foreach $fldVal (split (/__pipe__/, $f15)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'blood_supply_of';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}
		$fldVal = '';
	}	

	if($f16 ne ''){	#bounded_by
		foreach $fldVal (split (/__pipe__/, $f16)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'bounded_by';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f17 ne ''){	#bounds
		foreach $fldVal (split (/__pipe__/, $f17)){	
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'bounded_by';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f18 ne ''){	#branch_of
		foreach $fldVal (split (/__pipe__/, $f18)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'branch_of';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f19 ne ''){	#branch_part_of
		foreach $fldVal (split (/__pipe__/, $f19)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'branch_part_of';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f20 ne ''){	# Comment
		foreach $fldVal (split (/__pipe__/, $f20)){
			$allAttr->dumpAttr({sgId => $f63, atn => 'COMMENT', atv => $fldVal});
		}
		$fldVal = '';
	}

	if($f21 ne ''){	#Constitutional_Part_Of
		foreach $fldVal (split (/__pipe__/, $f21)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'constitutional_part_of';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f22 ne ''){	#Contained_In
		foreach $fldVal (split (/__pipe__/, $f22)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'contained_in';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}
		$fldVal = '';
    }

	if($f23 ne ''){	#Contains
		foreach $fldVal (split (/__pipe__/, $f23)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'contained_in';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}	
		}
		$fldVal = '';
	}

	if($f24 ne ''){	#Continuous_With
		foreach $fldVal (split (/__pipe__/, $f24)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'continuous_with';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f25 ne ''){	#Created
		$allAttr->dumpAttr({sgId => $f63, atn => 'DATE_CREATED', atv => $f25});
	}

	if($f27 ne ''){	#Distal_to
		foreach $fldVal (split (/__pipe__/, $f27)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'distal_to';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f29 ne ''){	#Drains_Into
		foreach $fldVal (split (/__pipe__/, $f29)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'drains_into';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f30 ne ''){	#External_to
		foreach $fldVal (split (/__pipe__/, $f30)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'external_to';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f32 ne ''){	#Has_Blood_Supply
		foreach $fldVal (split (/__pipe__/, $f32)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'blood_supply_of';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f33 ne ''){	#Has_Branch
		foreach $fldVal (split (/__pipe__/, $f33)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'branch_of';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f34 ne ''){	#Has_Branch_Part
		foreach $fldVal (split (/__pipe__/, $f34)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'branch_part_of';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}	
		}	
		$fldVal = '';
	}

	if($f35 ne ''){	#Has_Constitutional_Part
		foreach $fldVal (split (/__pipe__/, $f35)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'constitutional_part_of';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}	
		}
		$fldVal = '';
	}

	if($f36 ne ''){	#Has_Entrapment_Site
		foreach $fldVal (split (/__pipe__/, $f36)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'has_entrapment_site';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f37 ne ''){	#Has_Innervation_Source
		foreach $fldVal (split (/__pipe__/, $f37)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'has_innervation_source';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f38 ne ''){	#Has_Insertion
		foreach $fldVal (split (/__pipe__/, $f38)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'has_insertion';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f39 ne ''){	#Has_Member
		foreach $fldVal (split (/__pipe__/, $f39)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'has_member';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f40 ne ''){	#Has_origin
		foreach $fldVal (split (/__pipe__/, $f40)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'has_origin';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}
	
	if($f41 ne ''){	#Has_Part
		foreach $fldVal (split (/__pipe__/, $f41)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'part_of';
				$ntRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f42 ne ''){	#Has_Regional_Part
		foreach $fldVal (split (/__pipe__/, $f42)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'has_regional_part';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f43 ne ''){	#Inferior_to
		foreach $fldVal (split (/__pipe__/, $f43)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'inferior_to';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f44 ne ''){	#Innervates
		foreach $fldVal (split (/__pipe__/, $f44)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'has_innervation_source';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f45 ne ''){	#Insertion_of
		foreach $fldVal (split (/__pipe__/, $f45)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'has_insertion',;
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f46 ne ''){	#Lymphatic_Drainage
		foreach $fldVal (split (/__pipe__/, $f46)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'lymphatic_drainage_of';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f47 ne ''){	#Lymphatic_Drainage_Of
		foreach $fldVal (split (/__pipe__/, $f47)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'lymphatic_drainage_of';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f48 ne ''){	#May_Be_Caused_By
		foreach $fldVal (split (/__pipe__/, $f48)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'may_be_caused_by';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f49 ne ''){	#May_Cause
		foreach $fldVal (split (/__pipe__/, $f49)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'may_be_caused_by';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f50 ne ''){	#Member_Of
		foreach $fldVal (split (/__pipe__/, $f50)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'has_member';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f51 ne ''){	# Misspelling_of_term
		foreach $fldVal (split (/__pipe__/, $f51)){
			$allAttr->dumpAttr({sgId => $f63, atn => 'MISSPELLING_OF_TERM', atv => $fldVal});
		}
		$fldVal = '';
	}

	if($f53 ne ''){	#Origin_of
		foreach $fldVal (split (/__pipe__/, $f53)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'has_origin';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f54 ne ''){	#Part_Of
		foreach $fldVal (split (/__pipe__/, $f54)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'part_of';
				$ntRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f55 ne ''){	#Posterior_to
		foreach $fldVal (split (/__pipe__/, $f55)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'anterior_to';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f57 ne ''){ #Pref_name_for_Obsolete/ Obsolete SY
		foreach $fldVal (split (/__pipe__/, $f57)){
			$lstSaid = $opSaid = $opAtom->dumpAtom({code => $f63, str => $fldVal, scui => $f63});
            $said2name{$lstSaid}=$fldVal;
            $said2sgid{$lstSaid}=$f63;
	    $id2said{$f63}=$lstSaid;
		}
		$fldVal = '';
	}

	if($f58 ne ''){	#Pref_name_German 
		foreach $fldVal (split (/__pipe__/, $f58)){
			$allAttr->dumpAttr({sgId => $f63, atn => 'PREFERRED_NAME_GERMAN', atv => $fldVal});
		}
		$fldVal = '';
	}

	if($f59 ne ''){	#Projects_From
		foreach $fldVal (split (/__pipe__/, $f59)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'projects_from';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}	
		}
		$fldVal = '';
	}

	if($f60 ne ''){	#Projects_To
		foreach $fldVal (split (/__pipe__/, $f60)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'projects_to';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f61 ne ''){	#Proximal_to
		foreach $fldVal (split (/__pipe__/, $f61)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'distal_to';
				$rtRel ->dumpRel({sgId1 => $f63, rela => 'distal_to', sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f62 ne ''){	#RADLEX_VERSION_OF_CLASS_CHANGE 
		foreach $fldVal (split (/__pipe__/, $f62)){
			$allAttr->dumpAttr({sgId => $f63, atn => 'RADLEX_VERSION_OF_CLASS_CHANGE', atv => $fldVal});
		}
		$fldVal = '';
	}

	if($f64 ne ''){	#Receives_attachment_from
		foreach $fldVal (split (/__pipe__/, $f64)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'attaches_to';
				 $rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f65 ne ''){	#Receives_Drainage_From
		foreach $fldVal (split (/__pipe__/, $f65)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'drains_into';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f66 ne ''){	#Receives_Input_From
		foreach $fldVal (split (/__pipe__/, $f66)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'receives_input_from';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f67 ne ''){	#Receives_Projection_From
		foreach $fldVal (split (/__pipe__/, $f67)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'projects_to';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f68 ne ''){	#Regional_Part_Of
		foreach $fldVal (split (/__pipe__/, $f68)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'has_regional_part';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f69 ne ''){	#Related_modality
		foreach $fldVal (split (/__pipe__/, $f69)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'related_modality';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f70 ne ''){	#Replaced_by
		if($f70 =~ /__pipe__/){
			foreach $fldVal (split (/__pipe__/, $f70)){
				if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
					$id = $1;
					$rela = 'replaced_by';
					$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
					$allAttr->dumpAttr({sgId => $f63, atn => 'REPLACED_BY', atv => $id});
				}	
			}
			$fldVal = '';
		}
		elsif($f70 =~/^RID/){
			$rela = 'replaced_by';
			$rtRel ->dumpRel({sgId1 => $f70, rela => $rela, sgId2 => $f63});
            $allAttr->dumpAttr({sgId => $f63, atn => 'REPLACED_BY', atv => $f70});
		}
		elsif($f70 =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'replaced_by';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
				$allAttr->dumpAttr({sgId => $f63, atn => 'REPLACED_BY', atv => $id});
		}	
	}

	if($f71 ne ''){	#Segment_Of
		foreach $fldVal (split (/__pipe__/, $f71)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'segment_of';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f72 ne ''){	#Sends_Output_To
		foreach $fldVal (split (/__pipe__/, $f72)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'receives_input_from';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f73 ne ''){	#Source 
		foreach $fldVal (split (/__pipe__/, $f73)){
			$allAttr->dumpAttr({sgId => $f63, atn => 'CITE', atv => $fldVal});
		}
		 $fldVal = '';
	}

	if($f74 ne ''){	#Superior_to
		foreach $fldVal (split (/__pipe__/, $f74)){	
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'inferior_to';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f75 ne ''){	#Surrounded_by
		foreach $fldVal (split (/__pipe__/, $f75)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'surrounded_by';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f76 ne ''){	#Surrounds
		foreach $fldVal (split (/__pipe__/, $f76)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'surrounded_by';
				$rtRel ->dumpRel({sgId1 => $f63, rela => $rela, sgId2 => $id});
			}
		}	
		$fldVal = '';
	}

	if($f77 ne ''){	#multiple Synonyms
		foreach $fldVal (split (/__pipe__/, $f77)){
			if($f57 ne ''){
				$isSaid = $isAtom->dumpAtom({code => $f63, str => $fldVal, scui => $f63});	
				$syMerge->dumpMerge({sgId1 => $isSaid, sgId2 => $opSaid});
			}
			else{
				$sySaid = $syAtom->dumpAtom({code => $f63, str => $fldVal, scui => $f63});	
			$syMerge->dumpMerge({sgId1 => $ptSaid, sgId2 => $sySaid});
			}
		}
		$fldVal = '';
	}

	if($f79 ne ''){	#Tributary_Of
		foreach $fldVal (split (/__pipe__/, $f79)){
			if($fldVal =~ m{http://(?:www\.)?radlex\.org/RID/(RID\d+)}){
				$id = $1;
				$rela = 'tributary_of';
				$rtRel ->dumpRel({sgId1 => $id, rela => $rela, sgId2 => $f63});
			}
		}	
		$fldVal = '';
	}

	if($f80 ne ''){	#Unsanctioned_Term 
		foreach $fldVal (split (/__pipe__/, $f80)){
			$allAttr->dumpAttr({sgId => $f63, atn => 'UNSANCTIONED_TERM', atv => $fldVal});
		}
		$fldVal = '';
	}

$ptSaid = '';
$opSaid = '';
$sySaid = '';
$lstSaid = '';
@txt = ();

}#end of while loop TERMS

}#end subprocess RADLEX

sub getParChd{
	open(PARCHD1, "< ../tmp/par_chd_id")
      or croak("Can't find tmp/par_chd_id, $!");

    my ($parent,$child);
	while (<PARCHD1>){
		chomp;
		($parent,$child)=split(/\|/);
		print OUT2 "$parent|$id2said{$parent}|$child|$id2said{$child}\n";
	}
	close(OUT2);
	close(PARCHD1);

	open(PARCHD2, "< ../tmp/par_chd_said")
	  or croak("Can't find tmp/par_chd_said, $!");

	my ($par_code, $par_said, $chd_code, $chd_said);
	while (<PARCHD2>){
      chomp;
      ($par_code, $par_said, $chd_code, $chd_said)=split(/\|/);
	  if($par_code eq ''){
	  	next;
	  }
	  else{
      	$$HierRef->addParChild($par_said,$chd_said);
	  }
	}
	close(PARCHD2);

	my @rootnodes = $$HierRef->getRoots;
	$$LogRef->logIt("Before: root nodes are: <@rootnodes>\n");
	$$HierRef->setRoot($rootSaid);
	@rootnodes = $$HierRef->getRoots;
	$$LogRef->logIt("After: root nodes are: <@rootnodes>\n");

} #end of getParChd subroutine
