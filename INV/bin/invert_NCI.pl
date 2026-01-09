#!/usr/bin/perl
#File: invert_NCI.pl
#Author: Anoop
#Summary: Inversion script for NCI 
#usage: invert_NCI.pl [h] [c] [g]


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

#use OracleIF;
#use Midsvcs;

use Carp;
use NLMInv;
use SrcBldr;
use Atom;
use Attribute;
use Relation;
use Merge;
use Context;
use iutl;
use IdGen;

# Load config reader module for dynamic configuration
eval {
  require "$Bin/invert_NCI_config_reader.pl";
  1;
} or do {
  my $err = $@ || "Unknown error";
  print STDERR "WARNING: Failed to load config reader module: $err\n";
  print STDERR "Continuing without dynamic configuration support...\n";
};

#---------------------
#inversion script options
#---------------------
use Getopt::Std;

my %options=();
getopts("h", \%options);

if (defined $options{h}) {
  print "Usage: inver_NCI.pl -hg\n";
  print " This file inverts NCI and produces the standard files.\n";
  print "\t-h prints this message.\n";
  print "Step A) Update nci.cfg file in the etc folder with appropriate information based on the config file provided in ../orig folder.\n";
  print "\t1) read the incomming config file and see if any new sources are added (check for internal NCI sources also) or existing sources are removed. \n";
  print "\t2) generate sources.src and termgroups.src files.\n";
  print "Step B) run invert_NCI.pl - without any arguments.\n";
  print "\t1) This generates all the standard output files.\n";
  exit;
}


#---------------------
# Declare Global Variables
#---------------------
# Framework References
our $mainGenId;
our $Inv;
our $CfgFile = "../etc/nci.cfg";
our $Log;
our $Cfg;
our $HierRef;
our $config;


# Template variables
# NCI vsab
our ($ncivsab, $ncirsab, $ncistyvsab);

#NCI atoms and its sub-source atom variables
our ($Atom,$ptAtom,$miscAtom);
our ($nciopAtom,$nciptAtom);
#last_id variables for all the atom entries
our ($nciop1Atom,$ncipt1Atom);
our ($Atom1, $pt1Atom);

#merges, attributes, relations and context variables
our ($Attribute);
our ($merge);
our ($rRel, $nRel, $sRel, $tgRel, $mRel);
our ($rootCxt, $parCxt, $cxtAttr);

#rel_grp variables
our ($rrui, $relgrp, $rcui1, $inrela, $rcui2, $PTsaid);
our ($key, $value, $a, $last, $input, $prev_value,$result);
#--------------------------------------------------
# Constant variable data
our ($code,$term,$desc,$intty,$sab,$tty);
our ($sabtty, $string, $origcode, $str, $cui);
our ($null);
our ($rui,$cui1,$type1,$rel,$inrela,$cui2,$type2,$rela,$rsab);
our ($said1, $said2, $atn, $atv, $rel_grp, $srui);

#--------------------------------------------
our ($misc_ID1,$misc_ID2,$misc_ID3);
our ($miscAtom1,$miscAtom2,$miscAtom3);
our ($misc_merge);



#---------------------------------------
#storage variables
our @valuefields = ();
our @ttytmp = ();
our @par2chd = ();

#context hashes
our %said2sgid = ();      #hash containing source_atom_id to code for context building 
our %said2name = ();      # hash containing source_atom_id to string for context generation
our %cd2said = ();        # hash containing code to source_atom_id for context building\
our %id2pid = ();
our %cd2merge =();         #hash containing NCI PT cuis used for merging
our %stringorigcode=();
our %stringcui=();
our %stringVsabCui=();


our %relgrphash = ();   #hash containing relationship grouping
our %cuihash = ();	     #hash containig cui based grouping for relationships
our %seenNuSaidpair = ();     #hash to remove duplicate rels
our %rui2relgrp = ();
our %srel2atom = ();

#config hashes
our %in2Otty = ();        # get hash from Config file to convert input TTY's to specific obsolete TTY's
our %in2tty = ();         # get hash from Config file to convert input TTy's to output TTY's
our %in2vsab = ();        # get hash from Config file to assign vsab info for incoming sources
our %inl2tty = ();        # get hash from config file to convert FB and BR ttys


#------------------------------------------------------

sub init {

  # create a main generator with proper seeds.
  $mainGenId = new IdGen();
  
  #get hashes from cfg file 
     
  %in2vsab = $$Cfg->getHash('vsab');     
  
  #NCI and NCI-GLOSS vsab and rsab 
  $ncivsab = $$Cfg->getEle('VSAB');
  $ncistyvsab = $$Cfg->getEle('VSAB_STY'); 
  $ncirsab = $$Cfg->getEle('RSAB');
  
  # create templates.
  $Atom = new Atom();
  $miscAtom = new Atom();
  
  # NCI specific ATOM templates.
  $nciopAtom = new Atom('Atom.NCIOP');
  $nciptAtom = new Atom('Atom.NCIPT');
  $ptAtom = new Atom('');
  
  # ATTRIBUTE templates.
  $Attribute = new Attribute('');
  #$ltAttribute = new Attribute('Attribute.LT');
  $cxtAttr = new Attribute('Attribute.CONTEXT');

  # MERGE templates
  $merge = new Merge('Merge.SY');
  $misc_merge = new Merge('');

  # RELATION templates
  $rRel = new Relation('Relation.RT');
  $nRel = new Relation('Relation.NT');
  $sRel = new Relation('Relation.SY');
  $tgRel = new Relation('Relation.TG');
  $mRel = new Relation('Relation.MAP');
 
 # CONTEXT templates
  $rootCxt = new Context('Context.ROOT');
  $parCxt = new Context('Context.PAR');

 # MISC Atoms
  #temp variables for the root atoms
  $miscAtom1 = new Atom();
  $miscAtom2 = new Atom();
  $miscAtom3 = new Atom();


}

#------------------------
#sub processes
#------------------------

sub process {

  # dump source meta data.
  my $srcBldr = new SrcBldr();
  $srcBldr->processSrc('NCI');
  $Inv->prTime("Done SRC building");

  if ($config) {
    # Process subsource atoms (creates SRC atoms, merges, and relationships)
    processSubsourceAtomsFromConfig($config, $miscAtom1, $miscAtom2, $miscAtom3, $tgRel, $misc_merge, $Attribute);
  }

  #$Inv->prTime("processSubsourceAtoms");
  $Inv->prTime("Edit and un-comment processSubsourceAtoms if there is a new subsource");

  #&processSubsourceAtoms;
  &processNCIPT;
  &processMRCONSO;
  &processMRSAT;
  &processMRREL;
  &processRELGRP;
  &processContext;

  }
#------------------------
#trim
#-------------------------
sub trim {
  $_ = shift;
  s/ {2,}/ /g;         # more than 1 blanks to 1 blank
  s/^[ ]*//;           # strip leading blanks
  s/[ ]*$//;           # strip trailing blanks
  return $_;
}

sub trim1 {
  $_ = shift;
  s/ {2,}/ /g;         # more than 1 blanks to 1 blank
  s/^[ ]*//;           # strip leading blanks
  s/[ ]*$//;           # strip trailing blanks
  s/\&amp;/&/g;        
  s/\&lt;/</g;
  s/\&gt;/>/g;
  s/\&quot;/"/g;
  s/\&apos;/'/g;
  s/\&amp;/&/g;
  s/\&#8217;/'/g;
  s/\&#176;/ degrees/g;
  s/\&#39;/'/g;
  s/\&amp;/&/g;
   return $_;
 }
#---------------------------
#contstant variables for NCI
#-------------------------- 
sub processNCIPT{
$Inv->prTime("\tBegin NCI/PT atom dump.");

open(MRCON, "<:utf8", $$Cfg->getEle('FILE.MRCONSO')) or die "Could not open FILE.MRCONSO\n";
open (CCC, ">:utf8", "../etc/code2merge.txt") or die "couldn't open ../etc/code2merge\n";
my $line_count = 0;
while (<MRCON>){
        $line_count++;
        if ($line_count % 50000 == 0) {
                print STDERR "  Processed $line_count lines in processNCIPT...\n";
        }
        chomp;
        ($null,$string,$cui,$null,$sabtty,$origcode) = split(/\|/);
		  #$str =  trim1($string);
		  $str = iutl->cleanLine($string);
		  #if ($str ne $string) {print "$str|$string\n"};
        if($sabtty=~/(ACC-AHA)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(Cellosaurus)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(GDC)(...)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(GDC)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(ICDC)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(BRIDG_3_0_3)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(BRIDG_5_3)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(CTCAE_3)(..)/){
                $sab=$1;
                $tty=$2;
            	#print "$sab|$tty\n";
        }
        elsif($sabtty=~/(CTCAE_5)(..)/){
                $sab=$1;
                $tty=$2;
            	#print "$sab|$tty\n";
        }
        elsif($sabtty=~/(CDISC-GLOSS)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(NCI-GLOSS)(...)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(GENC)(...)/){
                $sab=$1;
                $tty=$2;
            	#print "$sab|$tty\n";
        }
        elsif($sabtty=~/(GAIA)(..)/){
                $sab=$1;
                $tty=$2;
            	#print "$sab|$tty\n";
        }
        elsif($sabtty=~/(PI-RADS)(..)/){
                $sab=$1;
                $tty=$2;
            	#print "$sab|$tty\n";
			}
        elsif($sabtty=~/(NICHD)(...)/){
                $sab=$1;
                $tty=$2;
          }
        elsif($sabtty=~/(ORCHESTRA)(..)/){
                $sab=$1;
                $tty=$2;
          }
        elsif($sabtty=~/(OORO)(..)/){
                $sab=$1;
                $tty=$2;
          }
        elsif($sabtty=~/(FDA-NIH-MoRE)(..)/){
                $sab=$1;
                $tty=$2;
          }
        elsif($sabtty=~/(MRCT-Ctr)(..)/){
                $sab=$1;
                $tty=$2;
	  }
        elsif($sabtty=~/(......)(LLT)/){
                $sab=$1;
                $tty=$2;
          }
		#elsif($sabtty=~/(SEER)(..)/){
		         #$sab="NCI";
				 #$tty=$2;
		#}
        elsif($sabtty=~/(............)(..)/){
                $sab=$1;
                $tty=$2;
        }        
        elsif($sabtty=~/(...........)(..)/){
                $sab=$1;
                $tty=$2;
        }        
        elsif($sabtty=~/(..........)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(.........)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(........)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(.......)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(......)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(.....)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(NCI)(...)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(....)(..)/){
                $sab=$1;
                $tty=$2;
        }
        #elsif($sabtty=~/(....)(...)/){
                #$sab=$1;
                #$tty=$2;
        #}
        elsif($sabtty=~/(...)(...)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(...)(..)/){
                $sab=$1;
                $tty=$2;
          }


#---------------------------------------------
#dump only NCI PT atoms first
   if ($origcode ne ""){
    next if($sab ne 'NCI' && $tty ne 'PT');
      if ($sab eq 'NCI'){
		  if ($tty eq 'PT'){
			# origcode or cui?
			$nciptAtom -> dumpAtom ({vsab => $ncivsab, code => $cui, str => $str, scui => $cui, suppress => 'N'});
            $ncipt1Atom = $nciptAtom->getLastId();
			
		    $cd2said{$cui} = $ncipt1Atom;
			$said2name{$ncipt1Atom} = $str;
	        $said2sgid{$ncipt1Atom} = $cui;
	        $stringorigcode{"$origcode|$str"}++;
			$stringVsabCui{"NCI|$cui|$str"}++;
	        #$stringorigcode{"$origcode|$str"}=$origcode."|".$string;
			#print "$stringorigcode{"$origcode|$str"}\n";
			$cd2merge{$cui} = $ncipt1Atom;
			print CCC "$cui|$cd2merge{$cui}\n";
		}
	  }
    }
   if ($origcode eq ""){
     next if($sab ne 'NCI' && $tty ne 'PT');
      if ($sab eq 'NCI'){
		  if ($tty eq 'PT'){
			$nciptAtom -> dumpAtom ({vsab => $ncivsab, code => $cui, str => $str, scui => $cui, suppress => 'N'});
            $ncipt1Atom = $nciptAtom->getLastId();
			
		    $cd2said{$cui} = $ncipt1Atom;
			$said2name{$ncipt1Atom} = $str;
	           $said2sgid{$ncipt1Atom} = $cui;
	           $stringcui{"$cui|$str"}++;		
			   $stringVsabCui{"NCI|$cui|$str"}++;
			$cd2merge{$cui} = $ncipt1Atom;
			print CCC "$cui|$cd2merge{$cui}\n";
		}
	  }
    }
	
 }
	 close (MRCON);
	 print STDERR "  Completed processNCIPT: $line_count total lines\n";
	}
#-----------------------------------------------------
#dump non orig code atoms of NCI and subsources atoms and merges from MRCONSO
#----------------------------------------------
sub processMRCONSO{
$Inv->prTime("\tprocess non NCI/PT entries.");

open(MRCON, "<:utf8", $$Cfg->getEle('FILE.MRCONSO')) or die "Could not open FILE.MRCONSO\n";
my $line_count = 0;
while (<MRCON>){
        $line_count++;
        if ($line_count % 50000 == 0) {
                print STDERR "  Processed $line_count lines in processMRCONSO...\n";
        }
        chomp;
		 %in2Otty = $$Cfg->getHash('in2Otty');   
		 %in2tty = $$Cfg->getHash('in2tty'); 
		 %inl2tty =  $$Cfg->getHash('inl2tty');
		 
        ($null,$string,$cui,$null,$sabtty,$origcode) = split(/\|/);
		  #$str =  trim1($string);
		  $str = iutl->cleanLine($string);
        if($sabtty=~/(ACC-AHA)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(Cellosaurus)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(GDC)(...)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(GDC)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(ICDC)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(BRIDG_3_0_3)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(BRIDG_5_3)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(CTCAE_3)(..)/){
                $sab=$1;
                $tty=$2;
            	#print "$sab|$tty\n";
        }
        elsif($sabtty=~/(CTCAE_5)(..)/){
                $sab=$1;
                $tty=$2;
            	#print "$sab|$tty\n";
        }
        elsif($sabtty=~/(CDISC-GLOSS)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(NCI-GLOSS)(...)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(GENC)(...)/){
                $sab=$1;
                $tty=$2;
            	#print "$sab|$tty\n";
        }
        elsif($sabtty=~/(GAIA)(..)/){
                $sab=$1;
                $tty=$2;
            	#print "$sab|$tty\n";
        }
        elsif($sabtty=~/(PI-RADS)(..)/){
                $sab=$1;
                $tty=$2;
            	#print "$sab|$tty\n";
        }
        elsif($sabtty=~/(NICHD)(...)/){
                $sab=$1;
                $tty=$2;
          }
        elsif($sabtty=~/(ORCHESTRA)(..)/){
                $sab=$1;
                $tty=$2;
          }
        elsif($sabtty=~/(OORO)(..)/){
                $sab=$1;
                $tty=$2;
          }
        elsif($sabtty=~/(MRCT-Ctr)(..)/){
                $sab=$1;
                $tty=$2;
          }
        elsif($sabtty=~/(MedDRA)(...)/){
                $sab=$1;
                $tty=$2;
          }
        elsif($sabtty=~/(FDA-NIH-MoRE)(..)/){
                $sab=$1;
                $tty=$2;
          }
	elsif($sabtty=~/(SEER)(..)/){
	        $sab="NCI";
	$tty="SY";
	}
        elsif($sabtty=~/(............)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(...........)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(..........)(..)/){
                $sab=$1;
                $tty=$2;
        }        
        elsif($sabtty=~/(.........)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(........)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(.......)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(......)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(.....)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(NCI)(...)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(....)(..)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(...)(...)/){
                $sab=$1;
                $tty=$2;
        }
        elsif($sabtty=~/(...)(..)/){
                $sab=$1;
                $tty=$2;
          }
   		
#-----------------------------------------------------------
#dump atoms, merges and some attributes of non orig_code
          if ($origcode eq ""){	  
		       if ($sab eq 'NCI'){
		 if ($tty eq 'SY'){
                  if (!defined($stringVsabCui{"NCI|$cui|$str"})){
                  $Atom -> dumpAtom ({vsab => $ncivsab, code => $cui, str => $str, scui => $cui, tty => "SY", suppress => 'N'});
				  $stringVsabCui{"NCI|$cui|$str"}++;
                   $Atom1 = $Atom->getLastId();             
                   
                    foreach($cui){
                    if ($cd2merge{$cui}){
                                     $merge -> dumpMerge ({sgId1 => $cd2merge{$cui}, sgId2 => $Atom1});
                           }
                        }
                     }
                  } 
                 if(defined($in2Otty{"$tty"})){ 		
		  $nciopAtom -> dumpAtom ({vsab => $ncivsab, code => $cui, str => $str, scui => $cui, tty => $in2Otty{"$tty"}, suppress => 'O'});	  
		  $nciop1Atom = $nciopAtom->getLastId();	
		        my $opcui = $cui;
			       foreach($opcui){
			         if ($cd2merge{$opcui}){
				     $merge -> dumpMerge ({sgId1 => $cd2merge{$opcui}, sgId2 => $nciop1Atom});
			             }
           	            }   
			}
		if(defined ($in2tty{"$tty"})){ 
			if($in2tty{"$tty"} eq 'AB'){
		     $Atom -> dumpAtom ({vsab => $ncivsab, code => $cui, str => $str, scui => $cui, tty => $in2tty{"$tty"}, suppress => 'Y'});		 }
			 else{
		     $Atom -> dumpAtom ({vsab => $ncivsab, code => $cui, str => $str, scui => $cui, tty => $in2tty{"$tty"}, suppress => 'N'});		  
			 }
			 $Atom1 = $Atom->getLastId();
             	my $ttycui = $cui;
           			foreach($ttycui){
			            if ($cd2merge{$ttycui}){
				     $merge -> dumpMerge ({sgId1 => $cd2merge{$ttycui}, sgId2 => $Atom1});
           	        }
				}	 		 
			}
		  
		if (defined ($inl2tty{"$tty"})){
		       $Atom -> dumpAtom ({vsab => $ncivsab, code => $cui, str => $str, scui => $cui, tty => $inl2tty{"$tty"}, suppress => 'N'});
			   $Atom1 = $Atom->getLastId();  
			   
			  #$ltAttribute -> dumpAttr({sgId => $Atom1});
			  $srel2atom{$cui} = $Atom1;
				
			   if (defined ($cd2said{$cui})){
			   $said1 = $cd2said{$cui};
			   $said2 = $srel2atom{$cui};
               $merge -> dumpMerge ({sgId1 => $said1, sgId2 => $said2});
			   }
			}
			 }
	      if (defined($in2vsab{"$sab"})){      
		  	#if (!defined{$stringcui{"$cui|$str"}}) {
	         if ($tty eq 'PT'){
      	      $ptAtom -> dumpAtom ({vsab => $in2vsab{"$sab"}, code => $cui, str => $str, scui => $cui, tty => 'PT', suppress => 'N'});
			  $pt1Atom = $ptAtom->getLastId();
			  my $subptcui = $cui;
			  foreach($subptcui){
			         if ($cd2merge{$subptcui}){
				     $merge -> dumpMerge ({sgId1 => $cd2merge{$subptcui}, sgId2 => $pt1Atom});
				   }
           	    }
			 }
                      if ($tty eq 'SY'){
                  $Atom -> dumpAtom ({vsab => $in2vsab{"$sab"}, code => $cui, str => $str, scui => $cui, tty => "SY", suppress => 'N'});
                   $Atom1 = $Atom->getLastId();

                    foreach($cui){
                    if ($cd2merge{$cui}){
                                     $merge -> dumpMerge ({sgId1 => $cd2merge{$cui}, sgId2 => $Atom1});
                           }
                        }
                     }

			  
		   if (defined($in2Otty{"$tty"})){  		   
           	   $Atom -> dumpAtom ({vsab => $in2vsab{"$sab"}, code => $cui, str => $str, scui => $cui, tty => $in2Otty{"$tty"}, suppress => 'O'});
                   $Atom1 = $Atom->getLastId(); 
			  my $subopcui = $cui;
			  foreach($subopcui){
			        if ($cd2merge{$subopcui}){
				     $merge -> dumpMerge ({sgId1 => $cd2merge{$subopcui}, sgId2 => $Atom1});
				  }
           	    }
			  }

			  if(defined($in2tty{"$tty"})){
			  	if($in2tty{"$tty"} eq 'AB'){
		    		$Atom -> dumpAtom ({vsab => $in2vsab{"$sab"}, code => $cui, str => $str, scui => $cui, tty => $in2tty{"$tty"}, suppress => 'Y'});		  
				}
				else{	
		    		$Atom -> dumpAtom ({vsab => $in2vsab{"$sab"}, code => $cui, str => $str, scui => $cui, tty => $in2tty{"$tty"}, suppress => 'N'});		  
				}
			$Atom1 = $Atom->getLastId(); 
                my $subttycui = $cui;
			       foreach($subttycui){
			        if ($cd2merge{$subttycui}){
				     $merge -> dumpMerge ({sgId1 => $cd2merge{$subttycui}, sgId2 => $Atom1});
				  }
           	    }			
							
		    }	 	
	      }
		  #}
        }
#---------------------------------------------
#dump orig_code atoms attributes and merges
      if ($origcode ne ""){
		 if ($sab eq 'NCI'){ 
		   if ($tty eq 'SY'){
				  # origcode or cui?
                  if (!defined($stringVsabCui{"NCI|$cui|$str"})){
                  $Atom -> dumpAtom ({vsab => $ncivsab, code => $cui, str => $str, scui => $cui, tty => "SY", suppress => 'N'});
                   $Atom1 = $Atom->getLastId();      
                  $stringVsabCui{"NCI|$cui|$str"}++; 
                    foreach($cui){
                    if ($cd2merge{$cui}){
                                     $merge -> dumpMerge ({sgId1 => $cd2merge{$cui}, sgId2 => $Atom1});
                           }
                        }
                     }
                  }
                   

                   if (defined($in2Otty{"$tty"})){             			
		  # origcode or cui? x
		  $nciopAtom -> dumpAtom ({vsab => $ncivsab, str => $str, scui => $cui, code => $cui, tty => $in2Otty{"$tty"}, suppress => 'O'});	  
		  $nciop1Atom = $nciopAtom->getLastId();	

				     if (defined($cd2merge{$cui})){
				     $merge -> dumpMerge({sgId1 => $cd2merge{$cui}, sgId2 => $nciop1Atom});           	      
                 }			
			}
		  # origcode or cui? x
		if (defined ($in2tty{"$tty"})){
			if($in2tty{"$tty"} eq 'AB'){
		     $Atom -> dumpAtom ({vsab => $ncivsab, str => $str, scui => $cui, code => $cui, tty => $in2tty{"$tty"}, suppress => 'Y'});
			}
			else{
		     $Atom -> dumpAtom ({vsab => $ncivsab, str => $str, scui => $cui, code => $cui, tty => $in2tty{"$tty"}, suppress => 'N'});
			}
			 $Atom1 = $Atom->getLastId();
             
					if (defined($cd2merge{$cui})){
				     $merge -> dumpMerge ({sgId1 => $cd2merge{$cui}, sgId2 => $Atom1});
			}
		}
		  
		if (defined ($inl2tty{"$tty"})){
		  # origcode or cui? x
		       $Atom -> dumpAtom ({vsab => $ncivsab,str => $str, scui => $cui, code => $cui, tty => $inl2tty{"$tty"}, suppress => 'N'});
			   $Atom1 = $Atom->getLastId();  
			   
			  #$ltAttribute -> dumpAttr({sgId => $Atom1});
			  
			  $srel2atom{$cui} = $Atom1;
				
			   if (defined ($cd2said{"$cui"})){
			   $said1 = $cd2said{"$cui"};
			   $said2 = $srel2atom{"$cui"};
               $merge -> dumpMerge ({sgId1 => $said1, sgId2 => $said2});
			   }
			}
			}
		if (defined($in2vsab{"$sab"})){
		    if ($tty eq 'PT'){
			 
		  # origcode or cui?
			$ptAtom -> dumpAtom({vsab => $in2vsab{"$sab"},str => $str, scui => $cui, code => $origcode, tty => 'PT', suppress => 'N'});
			$pt1Atom = $ptAtom->getLastId();
			  
			          if (defined($cd2merge{$cui})){
				     $merge -> dumpMerge ({sgId1 => $cd2merge{$cui}, sgId2 => $pt1Atom});
			  }
			}
                      if ($tty eq 'SY'){
					  # origcode or cui?
                    $Atom -> dumpAtom ({vsab => $in2vsab{"$sab"}, code => $origcode, str => $str, scui => $cui, tty => "SY", suppress => 'N'});
                    $Atom1 = $Atom->getLastId();

                    foreach($cui){
                    if ($cd2merge{$cui}){
                                     $merge -> dumpMerge ({sgId1 => $cd2merge{$cui}, sgId2 => $Atom1});
                           }
                        }
                     }

		  if (defined($in2Otty{"$tty"})){ 
		     
			$Atom -> dumpAtom({vsab => $in2vsab{"$sab"} , tty => $in2Otty{"$tty"},str => $str, scui => $cui, code => $origcode, suppress => 'O'});
			$Atom1 = $Atom->getLastId(); 
			 
			  if (defined($cd2merge{$cui})){
				     $merge -> dumpMerge({sgId1 => $cd2merge{$cui}, sgId2 => $Atom1});
		     }
		 }
                  if (defined($in2tty{"$tty"})){
		    			if($in2tty{"$tty"} eq 'AB'){ 
			 				$Atom -> dumpAtom({vsab => $in2vsab{"$sab"} , tty => $in2tty{"$tty"}, str => $str, scui => $cui, code => $origcode, suppress => 'Y'});
						}	
						else{	
			 				$Atom -> dumpAtom({vsab => $in2vsab{"$sab"} , tty => $in2tty{"$tty"}, str => $str, scui => $cui, code => $origcode, suppress => 'N'});
						}
			 $Atom1 = $Atom->getLastId();
			  
			    if (defined($cd2merge{$cui})){
				     $merge -> dumpMerge({sgId1 => $cd2merge{$cui}, sgId2 => $Atom1});
		     }	  
		   }
		  }
         }
      }
close(MRCON);
print STDERR "  Completed processMRCONSO: $line_count total lines\n";
}
#------------------------------------------------------
sub processMRSAT{
$Inv->prTime("\tBegin attributes.");

  open(MRSAT, "<:utf8", $$Cfg->getEle('FILE.MRSAT')) or die "Could not open File.MRSAT\n";

  my($sgid,$attr,$avsab,$qual,$qual1,$qual2,$qual3,$qual4);
  my $line_count = 0;
  while (<MRSAT>){
       $line_count++;
       if ($line_count % 100000 == 0) {
               print STDERR "  Processed $line_count lines in processMRSAT...\n";
       }
       chomp;
	  ($null,$cui,$sgid,$atn,$atv) = split (/\|/);
	    $qual = "";
				 
        if ($atn eq "DEFINITION"){
                if (/<def-definition>.*<\/def-definition>/){
                        $atv=$&;
                        $atv=~s/<def-definition>//;
                        $atv=~s/<\/def-definition>//;
                        $atv=~s/\&amp;/&/g;
                        $atv=~s/\&apos;/'/g;
                        $atv=~s/\&lt;/</g;
                        $atv=~s/\&gt;/>/g;
                        $atv=~s/\&quot;/"/g;
                        $atv=~s/\&amp;/&/g;
                        $atv=~s/\&#8217;/'/g;
                        $atv=~s/\&#176;/ degrees/g;
                        $atv=~s/\&#39;/'/g;
                }
                if (/<def-source>.*<\/def-source>/){
                        $qual=$&;
                        $qual=~s/<def-source>//;
                        $qual=~s/<\/def-source>//;
                        #$qual="Definition_Source\\".$qual;
						$avsab = $qual;
                }
                if (/<attr>.*<\/attr>/){
                        $attr=$&;
                        $attr=~s/<attr>//;
                        $attr=~s/<\/attr>/)/;
                        #$qual=$qual."\\Definition_Attribution\\(".$attr if ($attr ne "");
						if ($attr ne ""){
					    $atv = $atv."(".$attr;  
				    }
				}
				if ($cui ne '' && $atv ne ''){
				   if (defined($cd2said{"$cui"})){
		               if ($avsab eq "NCI"){
			      $Attribute ->dumpAttr ({sgId => $cui, lvl => 'S', atn => "DEFINITION", atv => trim($atv), vsab => $ncivsab, sgType => 'SOURCE_CUI', sgQual => $ncivsab});
			        }
				}
			      if(defined($in2vsab{"$avsab"})){
				     if(defined ($cd2said{"$cui"})){
			      $Attribute ->dumpAttr ({sgId => $cui, lvl => 'S', atn => "DEFINITION", atv => trim($atv), vsab => $in2vsab{"$avsab"}, sgType => 'SOURCE_CUI', sgQual => $ncivsab});
				  }
				}
			}
        }
        if ($atn eq "ALT_DEFINITION"){
                if (/<def-definition>.*<\/def-definition>/){
                        $atv=$&;
                        $atv=~s/<def-definition>//;
                        $atv=~s/<\/def-definition>//;
                        $atv=~s/\&amp;/&/g;
                        $atv=~s/\&lt;/</g;
                        $atv=~s/\&gt;/>/g;
                        $atv=~s/\&apos;/'/g;
                        $atv=~s/\&quot;/"/g;
                        $atv=~s/\&amp;/&/g;
                        $atv=~s/\&#8217;/'/g;
                        $atv=~s/\&#176;/ degrees/g;
                        $atv=~s/\&#39;/'/g;
                }
                if (/<def-source>.*<\/def-source>/){
                        $qual=$&;
                        $qual=~s/<def-source>//;
                        $qual=~s/<\/def-source>//;
                        #$qual="Definition_Source\\".$qual;
						$avsab = $qual;
                }
                if (/<attr>.*<\/attr>/){
                        $attr=$&;
                        $attr=~s/<attr>//;
                        $attr=~s/<\/attr>/)/;
                        #$qual=$qual."\\Definition_Attribution\\(".$attr if ($attr ne "");
						if ($attr ne ""){
					    $atv = $atv."(".$attr;  
				    }              
				}
				 if ($cui ne '' && $atv ne ''){
				 if (defined($cd2said{"$cui"})){
		               if ($avsab eq "NCI"){
			      $Attribute ->dumpAttr ({sgId => $cui, lvl => 'S', atn => "DEFINITION", atv => trim($atv), vsab => $ncivsab, sgType => 'SOURCE_CUI', sgQual => $ncivsab});
			        }
				}
			       if(defined($in2vsab{"$avsab"})){
				      if(defined ($cd2said{"$cui"})){
			      $Attribute ->dumpAttr ({sgId => $cui, lvl => 'S', atn => "DEFINITION", atv => trim($atv), vsab => $in2vsab{"$avsab"}, sgType => 'SOURCE_CUI', sgQual => $ncivsab});
				}
			   }
            }				
        }
        if ($atn eq "GO_Annotation"){
                if (/<go-term>.*<\/go-term>/)
                        {
                        $qual=$&;
                        $qual=~s/<go-term>//;
                        $qual=~s/<\/go-term>//;
                        $qual=~s/\&#39;/'/g;
						
                        }
                if (/<go-id>.*<\/go-id>/)
                        {
                        $qual1=$&;
                        $qual1=~s/<go-id>//;
                        $qual1=~s/<\/go-id>//;
                        $qual=$qual."\\GO_ID\\".$qual1;
                        }
                if (/<go-source>.*<\/go-source>/)
                        {
                        $qual2=$&;
                        $qual2=~s/<go-source>//;
                        $qual2=~s/<\/go-source>//;
                        $qual=$qual."\\GO_Source\\".$qual2;
                        }
                if (/<go-evi>.*<\/go-evi>/)
                        {
                        $qual3=$&;
                        $qual3=~s/<go-evi>//;
                        $qual3=~s/<\/go-evi>//;
                        $qual=$qual."\\GO_Evidence\\".$qual3;
                        }
                if (/<source-date>.*<\/source-date>/)
                        {
                        $qual4=$&;
                        $qual4=~s/<source-date>//;
                        $qual4=~s/<\/source-date>//;
                        $qual=$qual."\\GO_Source_Date\\".$qual4;
                        $atv = $qual;                   
					   }
        if ($cui ne ''){
		   if (defined($cd2said{"$cui"})){    
			 $Attribute -> dumpAttr({sgId => $cui, lvl => 'S', atn => "GO_Annotation", atv => trim($atv), vsab => $ncivsab, sgType => 'SOURCE_CUI', sgQual => $ncivsab});
                }
        }
   }
    if ($cui ne ""){
		if ($atn eq "DesignNote"){
			$Attribute -> dumpAttr ({sgId => $cui, lvl => 'S', atn => "Design_Note", atv => trim($atv), vsab => $ncivsab, sgType => 'SOURCE_CUI', sgQual => $ncivsab});
		}
		if ($atn eq "NSC Number"){
			$Attribute -> dumpAttr ({sgId => $cui, lvl => 'S', atn => "NSC_Number", atv => trim($atv), vsab => $ncivsab, sgType => 'SOURCE_CUI', sgQual => $ncivsab});
		}
	}
	if ($cui ne ""){
		if ($atn eq "Semantic_Type" && $atv ne "Vanderbilt-Ingram Cancer Center"){
		$Attribute -> dumpAttr ({sgId => $cui, lvl => 'C', atn => "SEMANTIC_TYPE", atv => trim($atv), vsab => $ncistyvsab, sgType => 'SOURCE_CUI', sgQual => $ncivsab});
	   }
	}
		   
        if ($cui ne ""){
	       if (defined($cd2said{"$cui"})){
		     next if(($atn eq "DEFINITION") || ($atn eq  "GO_Annotation") || ($atn eq "ALT_DEFINITION") || ($atn eq "RELATIONSHIPGROUP")|| ($atn eq "OID") || ($atn eq "UMLS_CUI") || ($atn eq "NCI_META_CUI") || ($atn eq "Concept_Status") ||($atn eq "Legacy Concept Name") || ($atn eq "In_Clinical_Trial_For") || ($atn eq "DesignNote") || ($atn eq "NSC Number") || ($atn eq "Subsource") || ($atn eq "Display_Name") || ($atn eq "Semantic_Type"));
		     
			 $Attribute -> dumpAttr ({sgId => $cui, lvl => 'S', atn => $atn, atv => trim($atv), vsab => $ncivsab, sgType => 'SOURCE_CUI', sgQual => $ncivsab});
		         }
	         }

      
	  if ($atn eq "RELATIONSHIPGROUP"){
	       $rui2relgrp{"$cui"} = "$cui|$atv"; 
		     }
		  }
		  close (MRSAT);
		  print STDERR "  Completed processMRSAT: $line_count total lines\n";
	}
#------------------------------------------
sub processMRREL{
$Inv->prTime("\tBegin relationships.");

open(MRREL, "<:utf8", $$Cfg->getEle('FILE.MRREL')) or die "Could not open File.MRREL\n";
open (AAA, ">:utf8", "../tmp/self_rels.txt") or die "couldn't open ../etc/self_rels.txt\n";
open (BBB, ">:utf8", "../etc/parchd_nci_scui.out") or die "couldn't open ../etc/parchd_nci_scui.out\n";
open (CCC, ">:utf8", "../etc/nci_relations.out") or die "couldn't open ../etc/nci_relations.out\n";

my $line_count = 0;
while (<MRREL>){
     $line_count++;
     if ($line_count % 100000 == 0) {
             print STDERR "  Processed $line_count lines in processMRREL...\n";
     }
     chomp;
	 ($rui,$cui1,$type1,$rsab,$rel,$rela,$cui2,$type2) = split (/\|/);
		  
		 if ($cui1 eq $cui2){
		  #printing self referential rels 
		  print AAA "ERROR: $cui1|SELF_REL|$cui2\n";
		  }
         
		if ($rela eq "mapped_to"){
		#	if($rsab =~ /ICD10CM/){
		#		$mRel -> dumpRel ({rel => $rel, sgId1 => $cui1, sgQual1 => "ICD10CM", sgId2 => $cui2});
		#	}
		#	elsif($rsab =~ /ICD10/){
        #        $mRel -> dumpRel ({rel => $rel, sgId1 => $cui1, sgQual1 => "ICD10", sgId2 => $cui2});
		#	}
		#	elsif($rsab =~ /ICD9CM/){
        #        $mRel -> dumpRel ({rel => $rel, sgId1 => $cui1, sgQual1 => "ICD9CM", sgId2 => $cui2});
		#	}
        #    elsif($rsab =~ /MedDRA/){
        #        $mRel -> dumpRel ({rel => $rel, sgId1 => $cui1, sgQual1 => "MDR", sgId2 => $cui2});
        #    }
        #    elsif($rsab =~ /ICDO3/){
        #        $mRel -> dumpRel ({rel => $rel, sgId1 => $cui1, sgQual1 => "ICDO", sgId2 => $cui2});
        #    }
        #    elsif($rsab =~ /GDC/){  #do not process
        #    }
		#	else{
		#		print "New mapping source: $_. Update external code validation script in /meme_work/inv/projects/TDE_QA/confirm_mapping_codes.pl\n";
		#	}
			next;
		}
		 if($rela eq "isa"){
                   push(@{$id2pid{"$cui2"}}, "$cui1");
                   print BBB "PAR-CHD(aui)|$cui2|$cui1|$rela\n";
         }

    if ($rela eq "Conceptual_Part_Of"){
	  if (defined ($cd2said{"$cui1"}) && (defined ($cd2said{"$cui2"}))){
	     
   	     $said1 = $cd2said{"$cui1"};
         $said2 = $cd2said{"$cui2"};
	     $nRel -> dumpRel ({sgId1 => $cui1, sgId2 => $cui2});
  }
}
 if (defined ($rui2relgrp{"$rui"})){
				 print CCC "$rui2relgrp{$rui}|$cui1|$rela|$cui2\n";	 
	      
		  } 
     if (!defined($rui2relgrp{"$rui"})){
			   next if(($rela eq "isa") || ($rela eq "Conceptual_Part_Of")||($cui1 eq $cui2));
	            if ($rui ne ''){
		  $said1 = $cd2said{"$cui1"};
		  $said2 = $cd2said{"$cui2"};
		  #seenNuSaidpair is used to remember said pairs so no duplication relationship is created
         if(!defined $seenNuSaidpair{"$said1|$said2|$rela"}){
		$rRel -> dumpRel ({sgId1 => $cui1, rela => $rela, sgId2 => $cui2});
		$seenNuSaidpair{"$said1|$said2|$rela"}++;
                }
		  } 
		   if ($rui eq ''){
		  $said1 = $cd2said{"$cui1"};
		  $said2 = $cd2said{"$cui2"};
		  $rRel -> dumpRel ({sgId1 => $cui1, rela => $rela, sgId2 => $cui2});
     	}
    }

 }
 close(CCC);
 close(MRREL);
 print STDERR "  Completed processMRREL: $line_count total lines\n";
 }
#--------------------------------------------------
#dumping relations with rel_groups
sub processRELGRP{
$Inv->prTime("\tBegin relation grouping.");
open (CCC, "<:utf8", "../etc/nci_relations.out") or die "couldn't open ../etc/nci_relations.1\n"; 
open (CCC1, ">:utf8", "../tmp/nci_relations1.out") or die "couldn't open ../tmp/nci_relations1.out\n"; 
     my $value = 0;
  while(<CCC>){
    chomp;	
	my ($x,$rel_grp, $curvalue);
	($rrui, $relgrp, $rcui1, $inrela, $rcui2) = split (/\|/);
         $said1 = $cd2said{$rcui1};
         $said2 = $cd2said{$rcui2};
		 
		   if(defined($relgrphash{"$relgrp|$rcui2"})){
		        $rel_grp = $relgrphash{"$relgrp|$rcui2"};
		  }else{
		      if (defined($cuihash{$rcui2})){
			     $x = $cuihash{$rcui2};
                 $curvalue = $x+1;
				 $value = $curvalue;
				 delete $cuihash{"rcui2"};
                 $cuihash{$rcui2} = $curvalue;
			  }else{
                 $cuihash{"$rcui2"} = 1;
              	  $value = 1;                				  
			 }
			  $relgrphash{"$relgrp|$rcui2"} = $value;
			  $rel_grp = $value;
			}
          $srui = "~DA:".$relgrphash{"$relgrp|$rcui2"};
		print CCC1 "$rrui|$relgrp|$rcui1|$rela|$rcui2|$srui|$rel_grp\n";
		$rRel-> dumpRel({sgId1 => $rcui1, rela => $inrela, sgId2 => $rcui2, srui => $srui, relGroup => $rel_grp});
}
close (CCC);
}
 #---------------------------------------------------
# processContext
#--------------------------------------------------
my ($par, $chd);
sub processContext{
    $Inv->prTime("\tBegin Context.");
    ###Dump Hierarchy
    ###Build parent chlds
    @par2chd = sort keys(%id2pid);
    foreach $chd(@par2chd){
        foreach $par(@{$id2pid{"$chd"}}){
            $$HierRef->addParChild($cd2said{"$par"}, $cd2said{"$chd"});
        }
    }
  my @rtnds = $$HierRef->getRoots;
  $$Log->logIt("Before: root nodes are: <@rtnds>\n");

    # also set root node from config if any.
  my ($rtNm, $rtCd, $rtSaid);
  $rtNm = $$Cfg->getEle('HC.RootNodeName');
  $rtCd = $$Cfg->getEle('HC.RootNodeCode');
  $rtSaid = $$Cfg->getEle('HC.RootNodeSaid');

  $$HierRef->setRoot($rtSaid);
  $said2name{"$rtSaid"} = $rtNm;
  $said2sgid{"$rtSaid"} = $rtCd;

  @rtnds = $$HierRef->getRoots;
  $$Log->logIt("After: root nodes are: <@rtnds>\n");

    $$HierRef->dumpCxtsAttrs(\$rootCxt,     # obj to dump root cxt
                            \$parCxt,       # obj to dump par cxts
                            0,              # obj to dump sib cxts
                            \$cxtAttr,      # obj to dump attrs
                            \%said2name,    # said to name hash
                            0,              # see note below (1)
                            \%said2sgid,    # said to sgid hash
                            0,              # don't dump chld in attrs
                            0);             # dump sibs in attrs
    ###################################################################
}
#---------------------------------------------------------------
sub processSubsourceAtoms {
 print "in processNewSubSource\n";
  my ($misc_ID);
    #create RPT, RAB, RSSN atoms for all of the sub-sources
    # because NCI is an existing source and we dont want to overwrite the NCI ROOT information we are doing this step manually
    # for next release make sure to take this informations out
   #PRO-CTCAE
   $miscAtom1->dumpAtom({str => 'Patient Reported Outcomes version of Common Terminology Criteria for Adverse Events' , code => 'V-PRO-CTCAE', tty => 'RPT', vsab => 'SRC'});
   $misc_ID1 = $miscAtom1->getLastId();
   $miscAtom2->dumpAtom({str => 'PRO-CTCAE', code => 'V-PRO-CTCAE', tty => 'RAB', vsab => 'SRC'});
   $misc_ID2 = $miscAtom2->getLastId();
   $miscAtom3->dumpAtom({str => 'PRO-CTCAE', code =>'V-PRO-CTCAE', tty => 'SSN', vsab => 'SRC'});
   $misc_ID3 = $miscAtom3->getLastId();
  
   $tgRel->dumpRel({sgId1 => 'V-MTH', sgId2 => 'V-PRO-CTCAE', rel => 'RT', rela => '', sgQual1 => 'SRC', sgQual2 => 'SRC', vsab => 'SRC', sl=> 'SRC'});
   $misc_merge->dumpMerge({sgId1 => $misc_ID1, sgId2 => $misc_ID2,mergeSet => 'NCI-SRC',sgType1 => 'SRC_ATOM_ID',sgType2 => 'SRC_ATOM_ID',vsab =>'SRC'});
   $misc_merge->dumpMerge({sgId1 => $misc_ID1, sgId2 => $misc_ID3,mergeSet => 'NCI-SRC',sgType1 => 'SRC_ATOM_ID',sgType2 => 'SRC_ATOM_ID',vsab =>'SRC'});
   $Attribute -> dumpAttr ({sgId => $misc_ID1, lvl => 'C', atn => "SEMANTIC_TYPE", atv => "Intellectual Product", vsab => "SRC", sgType => 'SRC_ATOM_ID', sgQual => ""});

   #ICD-10   
   #$miscAtom1->dumpAtom({str => 'International Classification of Diseases, 10th Edition' , code => 'V-ICD-10', tty => 'RPT', vsab => 'SRC'});
   #$misc_ID1 = $miscAtom1->getLastId();
   #$miscAtom2->dumpAtom({str => 'ICD-10', code => 'V-ICD-10', tty => 'RAB', vsab => 'SRC'});
   #$misc_ID2 = $miscAtom2->getLastId();
   #$miscAtom3->dumpAtom({str => 'International Classification of Diseases, 10th Edition', code =>'V-ICD-10', tty => 'SSN', vsab => 'SRC'});
   #$misc_ID3 = $miscAtom3->getLastId();
  
   #$tgRel->dumpRel({sgId1 => 'V-MTH', sgId2 => 'V-ICD-10', rel => 'RT', rela => '', sgQual1 => 'SRC', sgQual2 => 'SRC', vsab => 'SRC', sl=> 'SRC'});
   #$misc_merge->dumpMerge({sgId1 => $misc_ID1, sgId2 => $misc_ID2,mergeSet => 'NCI-SRC',sgType1 => 'SRC_ATOM_ID',sgType2 => 'SRC_ATOM_ID',vsab =>'SRC'});
   #$misc_merge->dumpMerge({sgId1 => $misc_ID1, sgId2 => $misc_ID3,mergeSet => 'NCI-SRC',sgType1 => 'SRC_ATOM_ID',sgType2 => 'SRC_ATOM_ID',vsab =>'SRC'});
   #$Attribute -> dumpAttr ({sgId => $misc_ID1, lvl => 'C', atn => "SEMANTIC_TYPE", atv => "Intellectual Product", vsab => "SRC", sgType => 'SRC_ATOM_ID', sgQual => ""});
}
#
#----------------------------------
#main
#----------------------------------
sub main{
  # Load and process inversion configuration BEFORE initializing NLMInv
  # This ensures nci.cfg is updated before it is read
  print "Loading inversion configuration...\n";
  $config = loadInversionConfig("$Bin/../etc/inversion_config.json");
  
  if ($config) {
    # Update nci.cfg with new source mappings (MUST BE FIRST)
    updateNciCfgFromConfig($config);
    
    # Process source metadata (adds entries to sources.src)
    processSourceMetadataFromConfig($config);

    # Process termgroup metadata (adds entries to termgroups.src)
    processTermgroupMetadataFromConfig($config);
  }

  #instantiate NLMInv
  $Inv = new NLMInv($CfgFile);
  
  # get common obj pointers
  $Log = $Inv->getLog;
  $Cfg = $Inv->getCfg;
  $HierRef = $Inv->getHier;
 
  $Inv -> prTime("Begin");

    ## initialize inv object to open files etc..
    $Inv->invBegin;

    
	## initalize;
     &init;
     &process;
     $Inv->prTime("Done process");

  $Inv->prTime("End");
  $Inv->invEnd;
  
}
&main;
