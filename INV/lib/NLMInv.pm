#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib (".");
our $defInvCfg = "$ENV{INV_HOME}/etc/inv_defaults.cfg";

use strict 'vars';
use strict 'subs';

package NLMInv;

use Logger;
use SrcBldr;
use NLMConfig;
use IdGen;
use Atom;
use Attribute;
use Merge;
use Relation;
use Context;
use Time::Local;
use Hierarchy;
#use SrcQa;
use Brit2Amer;

our $_theNLMInv;
our $_theCfg;
our $_theIdGen;
our $_theLog;
our $_theHier;

# constructor. enforce singleton.
sub new {
  if (defined($_theNLMInv)) {
	return $_theNLMInv;
  }

  my ($class, $configFile) = @_;
  if (!defined($configFile)) {
    die "You must instantiate NLMInv with a config file.\n";
  }

  ## create and init all the necessary things here.

  # create config file
  $_theCfg = new NLMConfig($configFile);


  # get log file, mode, and level and instantiate a log
  my $temp = $_theCfg->getEle('LogFile','');
  $temp = "DefaultLog.log" if ($temp eq '');
  my $logFile = "../etc/qa/$temp";
  my $logMode = $_theCfg->getEle('LogMode', 'Append');
  my $logLevel = $_theCfg->getEle('LogLvl', 'ERROR');
  $_theLog = new Logger($logFile, $logMode, $logLevel);

  # now set the association level
  $temp = $_theCfg->getEle('AssociationLevel', 0);
  NLMInv->setAssocLevel($temp);


  # instantiate an IdGen also.
  $_theIdGen = new IdGen($_theCfg->getReqEle('SaidStart'),
						 $_theCfg->getEle('AtidStart',1),
						 $_theCfg->getEle('RlidStart',1));


  # now create a hier object.
  $_theHier = new Hierarchy();


  # create this object.
  my $ref = {};
  $_theNLMInv =  bless($ref, $class);
  print "Done creating all.\n";
  print "Initializing\n";

  Hierarchy->init(\$_theLog, \$_theCfg);
  Atom->init(\$_theLog, \$_theCfg, \$_theIdGen);
  Attribute->init(\$_theLog, \$_theCfg, \$_theIdGen);
  Merge->init(\$_theLog, \$_theCfg);
  Relation->init(\$_theLog, \$_theCfg, \$_theIdGen);
  Context->init(\$_theLog, \$_theCfg);
  SrcBldr->init(\$_theLog, \$_theCfg, \$_theIdGen);
  Brit2Amer->init(\$_theLog);

  # we may want to have a separate qa log fiel. *****
  #SrcQa->init($_theLog, $_theCfg);

  $temp = `date`;
  $_theLog->logIt("**** Starting Application -- $temp\n");

  return $_theNLMInv;
}


# destructor.
sub DESTROY {
  $_theLog->closeLog();
}

sub getCfg { return \$_theCfg; }
sub getLog { return \$_theLog; }
sub getHier { return \$_theHier; }
sub getIdGen { return \$_theIdGen; }


# if $which = '' => regular mode
#           = 'Append' => append to the files.
#           = 2 => create .src2 files.
sub invBegin {
  my ($self, $which) = @_;

  if (defined($which)) {
	print "Mode is $which\n";
  }

  if (!defined ($which)) {
	$which = 0;
  } elsif ($which eq 'Append') {
	$which = 1;
  } elsif ($which != 2) {
    $_theLog->logIt("invBegin must be called with '' or 'Append' or 2.\n");
    die "invBegin must be called with '' or 'Append' or 2.\n";
  }

  $self->_invBegin($which);
  $_theHier = new Hierarchy();
}

sub _invBegin {
  my ($self, $which) = @_;
  my ($val);
  if ($which == 0) {
    $_theLog->logInfo("Opening all standard files.\n");
  } else {
    # reset the generator starting numbers.
    my ($tFile, $nextSaid, $nextAtid, $nextRlid);
    $tFile = $_theCfg->getReqEle('File.Atom');
    ($nextSaid) = split(/\|/, `tail -1 $tFile`);
    $tFile = $_theCfg->getReqEle('File.Attribute');
    ($nextAtid) = split(/\|/, `tail -1 $tFile`);
    $tFile = $_theCfg->getReqEle('File.Relation');
    ($nextRlid) = split(/\|/, `tail -1 $tFile`);

    $nextSaid++;
    $nextAtid++;
    $nextRlid++;

    # set the generator starting numbers.
    $_theIdGen->reset($nextSaid, $nextAtid, $nextRlid);
    if ($which == 1) {
      $_theLog->logInfo("Opening all standard files to append.\n");
    } else {
      $_theLog->logInfo("Opening all standard files in .src2 mode.\n");
    }
  }

  # open standard input files.
  $val = $_theCfg->getReqEle('File.Atom');
  if ($which == 2) {
	$val = "${val}2";
  }
  $_theLog->logDebug("Atoms file : $val\n");
  open (ATOMS, $which == 1 ? ">>:utf8" : ">:utf8",  $val)
    or die "Could not open atoms:$val file.\n";
  $_theCfg->setEle('ofhATOM', *ATOMS);
  Atom->setFileHandler(*ATOMS);


  $val = $_theCfg->getReqEle('File.Attribute');
  if ($which == 2) {
	$val = "${val}2";
  }
  $_theLog->logDebug("Attrs file : $val\n");
  open (ATTRS, $which == 1 ? ">>:utf8" : ">:utf8",  $val)
    or die "Could not open attrs:$val file.\n";
  $_theCfg->setEle('ofhATTR', *ATTRS);
  Attribute->setFileHandler(*ATTRS);


  $val = $_theCfg->getReqEle('File.Relation');
  if ($which == 2) {
	$val = "${val}2";
  }
  $_theLog->logDebug("Rels file : $val\n");
  open (RELS, $which == 1 ? ">>:utf8" : ">:utf8",  $val)
    or die "Could not open rels:$val file.\n";
  $_theCfg->setEle('ofhREL', *RELS);
  Relation->setFileHandler(*RELS);


  $val = $_theCfg->getReqEle('File.Merge');
  if ($which == 2) {
	$val = "${val}2";
  }
  $_theLog->logDebug("Merges file : $val\n");
  open (MERGES, $which == 1 ? ">>:utf8" : ">:utf8",  $val)
    or die "Could not open mrgs:$val file.\n";
  $_theCfg->setEle('ofhMRG', *MERGES);
  Merge->setFileHandler(*MERGES);


  $val = $_theCfg->getReqEle('File.Context');
  if ($which == 2) {
	$val = "${val}2";
  }
  $_theLog->logDebug("Cxts file : $val\n");
  open (CXTS, $which == 1 ? ">>:utf8" : ">:utf8",  $val)
    or die "Could not open cxts:$val file.\n";
  $_theCfg->setEle('ofhCXT', *CXTS);
  Context->setFileHandler(*CXTS);


  $val = $_theCfg->getReqEle('File.Source');
  $_theLog->logDebug("Sources file : $val\n");
  open (SRCS, "<:utf8",  $val) or die "Could not open srcs:$val file.\n";
  $_theCfg->setEle('ifhSRC', *SRCS);


  $val = $_theCfg->getReqEle('File.Termgroup');
  $_theLog->logDebug("TGs file : $val\n");
  open (TGS, "<:utf8",  $val) or die "Could not open tgs:$val file.\n";
  $_theCfg->setEle('ifhTGS', *TGS);

  # create dummy atoms and supply the cfg
  my $atOrd = $_theCfg->getEle('AtomOrder.Type');
  if ($atOrd eq 'Natural') {
    Atom->setDumpOrd($_theCfg->getEle('DumpAtomOrder', 1));
  }
}

sub invEnd {
  my $self = shift;
  $_theLog->logInfo("Closing all standard files.\n");
  close(ATOMS);  $_theCfg->setEle('ofhATOM', '');
  close(ATTRS);  $_theCfg->setEle('ofhATTR', '');
  close(CXTS);   $_theCfg->setEle('ofhCXT', '');
  close(RELS);   $_theCfg->setEle('ofhREL', '');
  close(MERGES); $_theCfg->setEle('ofhMRG', '');
  close(SRCS);   $_theCfg->setEle('ifhSRC', '');
  close(TGS);    $_theCfg->setEle('ifhTGS', '');
  $_theLog->closeLog();
}

{
  my $assocLevel = 0;
  my %said2code = ();
  my %code2said = ();
  my %said2sdui = ();
  my %sdui2said = ();
  my %said2scui = ();
  my %scui2said = ();

  # always expect 4 variables (in this order) : said, code, sdui, scui
  sub setAssocLevel {
    my ($class, $temp) = @_;
    if (defined ($temp)) {
      $assocLevel = $temp;
    }
  }

  sub associateSIDs {
    my $class = shift;
    my $said = shift;
    my $code = shift;
    my $sdui = shift;
    my $scui = shift;
    if ($assocLevel & 1) {
      $said2code{"$said"} = $code;
      push(@{$code2said{"$code"}}, $said);
    }
    if ($assocLevel & 2) {
      $said2sdui{"$said"} = $sdui;
      push(@{$sdui2said{"$sdui"}}, $said);
    }
    if ($assocLevel & 4) {
      $said2scui{"$said"} = $scui;
      push(@{$scui2said{"$scui"}}, $said);
    }
  }
  sub getSaid2CodeRef { return \%said2code; }
  sub getCode2SaidRef { return \%code2said; }
  sub getSaid2SduiRef { return \%said2sdui; }
  sub getSdui2SaidRef { return \%sdui2said; }
  sub getSaid2ScuiRef { return \%said2scui; }
  sub getScui2SaidRef { return \%scui2said; }
}

{
  my %atomOrd=();
  my ($ordCur, $ordInc);
  sub prepareAtomOrdering {
    # first get the root. (the one that doesn't have any parents.
    # start assigning from 100, in increments of 10.
    # ignore type for now

    my $self = shift;

    $ordCur = $_theCfg->getEle('AtomOrder.Begin', 100);
    $ordInc = $_theCfg->getEle('AtomOrder.Increment', 10);

    my @hcRoots = $_theHier->getRoots();
    my $cd;
    $_theLog->logInfo("CXT roots: @hcRoots\n");
    foreach $cd (@hcRoots) {
      &formAtomOrd ($cd);
    }
  }

  # internal method
  sub formAtomOrd {
    my $nd = shift;
    my $chld;
    if (defined ($atomOrd{"$nd"})) {
      return;
    }
    $atomOrd{"$nd"} = $ordCur;
    $ordCur += $ordInc;
    foreach $chld ($_theHier->getChildren("$nd")) {
      &formAtomOrd($chld);
    }
  }


  sub getAtomOrd {
    my $self = shift;
    my $nd = shift;
    return $atomOrd{"$nd"};
  }
}

sub prTime {
  shift;
  my $str = shift;
  my $mdt = `date`;
  $_theLog->logIt("$str => $mdt\n");
}




{
  ## this is for processing default stys.
  my %said2sgid=();
  my %sgid2saids=();
  my %said2stys = ();
  my %said2nostys=();
  my %said2edstys=();
  my %said2ednostys=();
  my %ch2pars = ();
  my $inhrt_mode = 0;


  #styAttr - attr object todump sty attribute.
  # typ = [default<0,said>, <1,code>, <2,scui>, <3,sdui>]
  # which = inherit [default<0, all parents stys>, <1, only 1 parents stys>]

  sub inheritSTYs {
    my ($self, $styAttr, $typ, $lc_inhrt_mode) = @_;
    $typ = 0 if (!defined $typ);
    $inhrt_mode = defined $lc_inhrt_mode ? $lc_inhrt_mode : 0;

    prTime('', "Entered NLMInv::processSTYs");

    my ($said, $sgid, $ptr, $psaid, @inp);
    my (@gsaids, @stys, $gsaid, $sty);


    ##
    # 1a. first read atoms file and  prepare said2typ and typ2said hashes.
    #
    open(IN, "<:utf8", $_theCfg->getEle('File.Atom'))
      or die "Could not open File.Atom file.\n";

    while (<IN>) {
      chomp;
      ($said, @inp) = split(/\|/, $_);
      next if ($inp[0] =~ /^SRC/);
      if ($typ == 1) {
		$sgid = $inp[2];
	  }							# collect code info
      elsif ($typ == 2) {
		$sgid = $inp[9];
	  }							# collect scui info
      elsif ($typ == 3) {
		$sgid = $inp[10];
	  }							# collect sdui info

      if ($typ != 0) {
		$said2sgid{"$said"} = $sgid;
		push(@{$sgid2saids{"$sgid"}}, $said);
      }

      $said2nostys{"$said"}++;
    }
    my $temp = keys %said2nostys;
    prTime('', "Read atoms file: saids(noStys) reminaing: $temp");


    #
    # 1b. now form the par/chld rels from the context file.
    #
    open(IN, "<:utf8", $_theCfg->getEle('File.Context'))
      or die "Could not open File.Context.\n";
    my ($csaid, $rel, $rela, $psaid, $ign, $ptr);
    while (<IN>) {
      chomp;
      ($csaid, $rel, $ign, $psaid, $ign) = split(/\|/, $_);

      next if ($rel ne 'PAR');
      push(@{$ch2pars{"$csaid"}}, $psaid)
		unless grep($psaid, @{$ch2pars{"$csaid"}});
    }
    close(IN);



    ##
    # 2. now prepare said2stys from the generated file sty_term_ids.
    #    this file is generted during test insertion.
    #
    my $styFile = $_theCfg->getEle('File.TINS.StyTermIds', '');
    open(IN, "<:utf8", $styFile)
      or die "Could not open File.TINS.StyTermIds<$styFile> file.\n";
    while (<IN>) {
      chomp;
      ($said, $sty) = split(/\|/, $_);
      push(@{ $said2stys{"$said"} }, $sty);
      delete $said2nostys{"$said"};
    }
    close(IN);
    $temp = keys %said2nostys;
    prTime('', "Done TINS.stys file. Remining: $temp");



    ##
    # 3. now read said2stys from the file given by editors.
    #
    $styFile = $_theCfg->getEle('File.EDIT.StyTermIds', '');
    if ($styFile ne '') {
      open(IN, "<:utf8", $styFile)
		or die "Could not open File.EDIT.StyTermIds<$styFile> file.\n";
      my %to_remove=();
      while (<IN>) {
		chomp;
		($said, $sty) = split(/\|/, $_);
		push (@{$said2edstys{"$said"}}, $sty);
		if (defined($said2nostys{"$said"})) {
		  push(@{ $said2stys{"$said"} }, $sty);
		  $to_remove{"$said"}++;
		}
      }
      close(IN);
      prTime('', "Read sty file");

      # now remove the saids that are assigned from above.
      # we need this as a seperate step to deal with multiple stys.
      foreach $said (keys %to_remove) {
		delete $said2nostys{"$said"};
      }
      &constructEdStys();
    }
    $temp = keys %said2nostys;
    prTime('', "Done EDIT.stys file. Remining: $temp");


    ##
    # 4. for the missing ones, walk through the context trees
    #    and assign stys.
    #
    foreach $csaid (keys %ch2pars) {
      &findStys($csaid) if (defined($said2nostys{"$csaid"}));
    }
    $temp = keys %said2nostys;
    prTime('', "Done Cxt file. Remining: $temp");



    ##
    # 5. now using the sg_type, assign stys to those saids with the
    #    same sgid. do this only if $typ != 0.
    #
    if ($typ != 0) {
      foreach $said (keys %said2nostys) {

		#collect stys from other saids within the group.
		@stys=();
		$sgid = $said2sgid{"$said"};
		foreach $gsaid (@{$sgid2saids{"$sgid"}}) {
		  if (defined($said2stys{"$gsaid"})) {
			foreach $sty (@{$said2stys{"$gsaid"}}) {
			  push (@stys, $sty) unless grep(/$sty/, @stys);
			}
		  }
		}

		# now assign this to each of the saids for the missing ones.
		if (@stys > 0) {
		  foreach $gsaid (@{$sgid2saids{"$sgid"}}) {
			if (!defined($said2stys{"$gsaid"})) {
			  delete $said2nostys{"$gsaid"};
			  foreach $sty (@stys) {
				push(@{$said2stys{"$gsaid"}}, $sty);
			  }
			}
		  }
		}
      }
    }
    $temp = keys %said2nostys;
    prTime('', "Done propogating stys to missing saids. Remianing: $temp");


    ##
    # 6. now dump sty attrs.
    #
    foreach $said (keys %said2stys) {
      foreach $sty (@{$said2stys{"$said"}}) {
		$$styAttr->dumpAttr({sgId => $said, atv => "$sty"});
      }
    }
    print "Done dumping stys\n";

    ##
    # 7. dump saids with no stys.
    #
    my $tdir = $_theCfg->getEle('TEMPDIR', '../tmp');
    open(OUT2, ">:utf8", "$tdir/SaidsWithNoStys")
      or die "Could not open $tdir/SaidsWithNoStys\n";
    foreach $said (sort keys(%said2nostys)) {
      print OUT2 "$said\n";
    }
    close(OUT2);
    prTime('', "Done writing saids with no stys");

    # release memory
    %said2sgid=();
    %sgid2saids=();
    %said2stys = ();
    %said2nostys=();
    %said2edstys=();
    %said2ednostys=();
    %ch2pars = ();
  }


  sub findStys{
    my $csaid = shift;

    # skip if already has an sty assigned.
    return if (!defined($said2nostys{"$csaid"}));

    my ($psaid, $sty);
    # if one is available in editor provided one, assign that and return
    if (defined($said2edstys{"$csaid"})) {
      foreach $sty (@{$said2edstys{"$csaid"}}) {
		push (@{$said2stys{"$csaid"}}, $sty);
      }
      delete $said2nostys{"$csaid"};
      return;
    }

    # has no stys. so find stys for each parent fist.
    foreach $psaid (@{$ch2pars{"$csaid"}}) {
      if (defined($said2edstys{"psaid"})) {
		foreach $sty (@{ $said2edstys{"$psaid"} }) {
		  push(@{ $said2stys{"$psaid"} }, $sty)
			unless grep(/$sty/, @{ $said2stys{"$psaid"} });
		}
		delete $said2nostys{"$psaid"};
      } elsif (defined($said2stys{"$psaid"})) {
		foreach $sty (@{ $said2stys{"$psaid"} }) {
		  push(@{ $said2stys{"$psaid"} }, $sty)
			unless grep(/$sty/, @{ $said2stys{"$psaid"} });
		}
		delete $said2nostys{"$psaid"};
      } else {
		# no sty assigned. so walk the tree and assign
		&findStys($psaid);
      }
    }

    # now collect each parents stys and assign them to this node.
    foreach $psaid (@{$ch2pars{"$csaid"}}) {
      foreach $sty (@{$said2stys{"$psaid"}}) {
		push (@{$said2stys{"$csaid"}}, $sty)
		  unless grep (/$sty/, @{$said2stys{"$csaid"}});
      }
      last if ($inhrt_mode != 0);
    }
    delete $said2nostys{"$csaid"};
  }

  sub constructEdStys {
    my $csaid;
    if ((keys %said2edstys) > 0) {
      foreach $csaid (keys %ch2pars) {
		&findEdStys ($csaid) if (!defined($said2edstys{"$csaid"}));
      }
    }
  }

  sub findEdStys {
    my $csaid = shift;

    # skip if already has an edsty assigned.
    return if (defined($said2edstys{"$csaid"}));

    # has no edstys. so find edstys for each parent first.
    my ($psaid, $sty);
    foreach $psaid (@{$ch2pars{"$csaid"}}) {
      if (!defined($said2edstys{"psaid"})) {
		# no sty assigned. so walk the tree and assign
		&findEdStys($psaid);
      }
    }

    # now collect each parents stys and assign them to this node.
    foreach $psaid (@{$ch2pars{"$csaid"}}) {
      foreach $sty (@{$said2edstys{"$psaid"}}) {
		push (@{$said2edstys{"$csaid"}}, $sty)
		  unless grep (/$sty/, @{$said2edstys{"$csaid"}});
      }
      last if ($inhrt_mode != 0);
    }
  }

}


1

