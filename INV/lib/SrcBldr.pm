#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use strict 'vars';
use strict 'subs';


package SrcBldr;

use Digest::MD5 qw(md5_hex);

{
  my ($_theLog, $_theCfg, $_theIdGen);
  my ($_rptSaid, $_rabSaid, $_vptSaid, $_vabSaid);
  my $topSrc='';
  my $cmtLine = qr/^\s*\#/;
  my $blnkLine = qr/^\s*$/;

  sub init {
    my ($self, $log, $cfg, $idg) = @_;
    $_theLog = $log;
    $_theCfg = $cfg;
    $_theIdGen = $idg;
  }

  sub new {
    my $class = shift;

    my $ref = {};
    return bless($ref,$class);
  }

  # sources.src:
  #  1 - source name       $srcName
  #  2 - low source        $lowSrc
  #  3 - restriction level $restLvl
  #  4 - normalized source $normName
  #  5 - stripped source   $strpName
  #  6 - version           $version
  #  7 - source family     $fmlyName
  #  8 - official name     $ofclName
  # others are unused

  # read sources.src to process all the bits
  sub processSrc {
    my ($self, $givenMergeSetName) = @_;
    $givenMergeSetName = '' if (!defined($givenMergeSetName));

    my $_makeRoot = $$_theCfg->getEle('MakeRoot', 0);
    my $_makeTrans = $$_theCfg->getEle('MakeTrans', 0);

    my $_ifhSrc = $$_theCfg->getReqEle('ifhSRC');
    my $_ofhATOM = $$_theCfg->getReqEle('ofhATOM');
    my $_ofhATTR = $$_theCfg->getReqEle('ofhATTR');
    my $_ofhMRG = $$_theCfg->getReqEle('ofhMRG');
    my $_ofhREL = $$_theCfg->getReqEle('ofhREL');
    my $_rptSaid = 0;
    my $_rabSaid = 0;
    my $_vptSaid = 0;
    my $_vabSaid = 0;
    my $mergeSetName = '';
    my $md5IP = md5_hex("Intellectual Product");
    my $_ordId = 1;

    my ($thisId, $val, @vals);
    my($code, $eng_vcode);

    my($ign, $srcName,$normName, $strpName, $version, $fmlyName, $ofclName);

    my %rootSabNames = $$_theCfg->getHash('RootSabNames');
    my $rootSabNum = keys %rootSabNames;
    seek($_ifhSrc,0,0);
    while (<$_ifhSrc>) {
      chomp;
      next if(/$cmtLine/);
      next if(/$blnkLine/);		# skip blank lines

      ($srcName,$ign, $ign, $normName,$strpName,$version,$fmlyName,
       $ofclName) = split(/\|/);

      next unless($srcName eq $normName); # ignore un-normalized sources

      # first source is the top source
      $topSrc = $srcName if ($topSrc eq '');

      if ($givenMergeSetName eq '') {
		$mergeSetName = "$strpName";
      } else {
		$mergeSetName = $givenMergeSetName;
      }

      if ($_makeRoot == 1) {
		if ($rootSabNum == 0 || defined($rootSabNames{"$srcName"})) {

		  ## create an RPT (Root Primary Term) atom
		  $_rptSaid = $$_theIdGen->newAid();
		  print $_ofhATOM "$_rptSaid|SRC|SRC/RPT|V-$strpName|N|Y|N|$ofclName|N";
		  print $_ofhATOM "||||ENG|$_ordId|\n";
		  $_ordId++;

		  # RPT - SEMANTIC_TYPE - Intellectual Product
		  $thisId = $$_theIdGen->newAtid();
		  print $_ofhATTR "$thisId|$_rptSaid|C|SEMANTIC_TYPE|Intellectual Product";
		  print $_ofhATTR "|SRC|R|Y|N|N|SRC_ATOM_ID|||$md5IP|\n";

		  # rel between the Root concept and the UMLS Metathesaurus
		  # via CODE_TERMGROUP.
		  $thisId = $$_theIdGen->newRid();
		  print $_ofhREL "$thisId|S|V-MTH|RT||V-$strpName|SRC|SRC|R|Y|N|N";
		  print $_ofhREL "|CODE_SOURCE|SRC|CODE_SOURCE|SRC|||\n";


		  ## create an RAB (Root Abbreviation) atom.
		  $_rabSaid = $$_theIdGen->newAid();
		  print $_ofhATOM "$_rabSaid|SRC|SRC/RAB|V-$strpName|N|Y|N|$strpName|N";
		  print $_ofhATOM "||||ENG|$_ordId|\n";
		  $_ordId++;

		  # Merge RPT and RAB
		  print $_ofhMRG "$_rptSaid|SY|$_rabSaid|SRC||N|N|$mergeSetName-SRC";
		  print $_ofhMRG "|SRC_ATOM_ID||SRC_ATOM_ID||\n";


		  ## create SSN (Source Short Name for Root) - must be there if new src
		  $val = $$_theCfg->getEle("$srcName.RSSN", '');
		  if ($val eq '') {
			print STDERR "ERROR: RSSN (Root Short Source Name) is required for ";
			print STDERR "ROOT src <$srcName> in config file\n";

			$$_theLog->logError("RSSN (Root Short Source Name) is required for ROOT src <$srcName> in config file\n");
			exit 1;
		  } else {
			# dump SSN atom
			$thisId = $$_theIdGen->newAid();
			print $_ofhATOM "$thisId|SRC|SRC/SSN|V-$strpName|N|Y|N";
			print $_ofhATOM "|$val|N||||ENG|$_ordId|\n";
			$_ordId++;
			# dump merge RTP to SSN with mrgset - "$strpName-SRC"
			print $_ofhMRG "$_rptSaid|SY|$thisId|SRC||N|N|$mergeSetName-SRC";
			print $_ofhMRG "|SRC_ATOM_ID||SRC_ATOM_ID||\n";
		  }


		  ## now create RHT (Root Hierarchical Term for the root) - optional
		  $val = $$_theCfg->getEle("$srcName.RHT", '');
		  if ($val ne '') {
			$thisId = $$_theIdGen->newAid();
			print $_ofhATOM "$thisId|SRC|SRC/RHT|V-$strpName|N|Y|N";
			print $_ofhATOM "|$val|N||||ENG|$_ordId|\n";
			$_ordId++;

			# merge this with the RPT atom
			print $_ofhMRG "$_rptSaid|SY|$thisId|SRC||N|N|$mergeSetName-SRC";
			print $_ofhMRG "|SRC_ATOM_ID||SRC_ATOM_ID||\n";

			# now set these values in the Cfg.
			$$_theCfg->setEle('HC.RootNodeCode', "V-$strpName");
			$$_theCfg->setEle('HC.RootNodeSaid', $thisId);
			$$_theCfg->setEle('HC.RootNodeName', "$val");
			print "Please include the following lines in the cfg file for ";
			print " future versions of this source\n";
			print "\tHC.RootNodeSaid = $thisId\n";
			print "\tHC.RootNodeCode = V-$strpName\n";
			print "\tHC.RootNodeName = $val\n\n";
		  }

		  ## RSY (Root Synonymous) atoms - (zero or more)
		  foreach $val ($$_theCfg->getList("$srcName.RSY")) {
			$thisId = $$_theIdGen->newAid();
			print $_ofhATOM "$thisId|SRC|SRC/RSY|V-$srcName|N|Y|N|$val|N";
			print $_ofhATOM "||||ENG|$_ordId|\n";
			$_ordId++;

			# merge this with RPT atom
			print $_ofhMRG "$_rptSaid|SY|$thisId|SRC||N|N|$mergeSetName-SRC";
			print $_ofhMRG "|SRC_ATOM_ID||SRC_ATOM_ID||\n";
		  }
		}
      }


      ## VERSIONED Atoms
      # create a VPT (Versioned Primary Term) atom
      $_vptSaid = $$_theIdGen->newAid();
      print $_ofhATOM  "$_vptSaid|SRC|SRC/VPT|V-$srcName|N|Y|N";
      print $_ofhATOM "|$ofclName, $version|N||||ENG|$_ordId|\n";
      $_ordId++;

      # VPT - SEMANTIC_TYPE - Intellectual Product
      $thisId = $$_theIdGen->newAtid();
      print $_ofhATTR "$thisId|$_vptSaid|C|SEMANTIC_TYPE|Intellectual Product";
      print $_ofhATTR "|SRC|R|Y|N|N|SRC_ATOM_ID|||$md5IP|\n";

      # ??? RELATIONSHIPS.SRC
      $thisId = $$_theIdGen->newRid();
      print $_ofhREL "$thisId|S|V-$srcName|BT|has_version|V-$strpName|SRC|SRC|R";
      print $_ofhREL "|Y|N|N|CODE_SOURCE|SRC|CODE_SOURCE|SRC|||\n";

      ## create a VAB (Versioned Abbreviation) atom
      $_vabSaid = $$_theIdGen->newAid();
      print $_ofhATOM "$_vabSaid|SRC|SRC/VAB|V-$srcName|N|Y|N";
      print $_ofhATOM "|$srcName|N||||ENG|$_ordId|\n";
      $_ordId++;

      # Merge VPT and VAB
      print $_ofhMRG "$_vptSaid|SY|$_vabSaid|SRC||N|N|$mergeSetName-SRC";
      print $_ofhMRG "|SRC_ATOM_ID||SRC_ATOM_ID||\n";
      ## VSY (Versioned synonymous) atoms (zero or more)
      foreach $val ($$_theCfg->getList("$srcName.VSY")) {
		$thisId = $$_theIdGen->newAid();
		print $_ofhATOM "$thisId|SRC|SRC/VSY|V-$srcName|N|Y|N|$val|N||||ENG|$_ordId|\n";
		$_ordId++;

		# merge VSY with VPT
		print $_ofhMRG "$_vptSaid|SY|$thisId|SRC||N|N|$mergeSetName-SRC";
		print $_ofhMRG "|SRC_ATOM_ID||SRC_ATOM_ID||\n";
      }

      # 'translation_of' rel is between the ROOT atoms ???????
      if ($_makeTrans) {
		$strpName =~ /(\w*)(.{3})/;
		$eng_vcode = "V-".$1;
		$thisId = $$_theIdGen->newRid();
		print $_ofhREL "$thisId|S|$eng_vcode|RT|translation_of|V-$strpName|SRC";
		print $_ofhREL "|SRC|R|Y|N|N|CODE_SOURCE|SRC|CODE_SOURCE";
		print $_ofhREL "|SRC|||\n";
      }
    }

    print  "********* End SrcBldr**********\n\n";
  }

  sub getVptSaid { return $_vptSaid; }
  sub getVabSaid { return $_vabSaid; }
  sub getRptSaid { return $_rptSaid; }
  sub getRabSaid { return $_rabSaid; }

}
1



