#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package SrcQa;

use QaAtoms;
use QaAttrs;
use QaRels;
use QaMerges;
use QaCxts;
use QaSrcs;
use QaTGs;
use QaDocs;

{
  my ($_theLog, $_theCfg, $_inDir);
  my ($_reportFile, $_pbar_cb);
  my $_dstaInfoIn = 0;
  my $_relInfoIn = 0;
  my $_relInfoIn2 = 0;
  my $_cfgFile = '';
  my $_ofErrors = '';
  my $_whichP = 31;
  my $_logWin = '';
  my $_pbar_present = 0;


  my %g_valids = (
				  # from Doc
				  Atn => {},	# valid Attribute Names
				  Rel => {},	# valid Rels
				  Rela => {},	# valid Relas
				  Tty => {},	# valid Ttys
				  # from Source
				  Vsab => {},	# valid Vsabs
				  Rsab => {},	# valid Rsabs
				  Vsab2Rsab => {}, # vsab to rsab assoc
				  language => {}, #valid languages
				  # from Termgroup
				  Tg => {},		# valid Termgroups
				  Tg2Sup => {},	# termgroup to suppress assoc.
				  # from Atoms
				  Said => {},	# valid saids
				  CdVsab => {},	# valid Code|Vsab
				  CdRsab => {},	# valid Code|Rsab
				  CdVTg => {},	# valid Code|VTermgroup
				  CdRTg => {},	# valid Code|RTermgroup
				  SauiVsab => {}, # valid Saui|Vsab
				  SauiRsab => {}, # valid Saui|Rsab
				  ScuiVsab => {}, # valid Scui|Vsab
				  ScuiRsab => {}, # valid Scui|Rsab
				  SduiVsab => {}, # valid Sdui|Vsab
				  SduiRsab => {}, # valid Sdui|Rsab
				  SrcAtoms => {}, # valid VPT/VAB atoms saids
				  # from Rels/Cxts
				  RelId => {},	# valid Relids
				  SruiVsab => {}, # valid Srui|Vsab
				  SruiRsab => {}, # valid Srui|Rsab

				  # from ExtIds file
				  AUI => {},
				 );

  # valids info from doc file
  my $_valAtnRef       = $g_valids{'Atn'};
  my $_valRelRef       = $g_valids{'Rel'};
  my $_valRelaRef      = $g_valids{'Rela'};
  my $_valTtyRef       = $g_valids{'Tty'};

  # valids info from sources file
  my $_valVsabRef      = $g_valids{'Vsab'};
  my $_valRsabRef      = $g_valids{'Rsab'};
  my $_valVsab2RsabRef = $g_valids{'Vsab2Rsab'};
  my $_vallanguageRef     = $g_valids{'language'};

  # valids info from termgroups file
  my $_valTGRef        = $g_valids{'Tg'};
  my $_valTg2SupRef    = $g_valids{'Tg2Sup'};

  # valids info from atoms file
  my $_valSaidRef      = $g_valids{'Said'};
  my $_valCdVsabRef    = $g_valids{'CdVsab'};
  my $_valCdRsabRef    = $g_valids{'CdRsab'};
  my $_valCdVTGRef     = $g_valids{'CdVTg'};
  my $_valCdRTGRef     = $g_valids{'CdRTg'};
  my $_valSauiVsabRef  = $g_valids{'SauiVsab'};
  my $_valSauiRsabRef  = $g_valids{'SauiRsab'};
  my $_valScuiVsabRef  = $g_valids{'ScuiVsab'};
  my $_valScuiRsabRef  = $g_valids{'ScuiRsab'};
  my $_valSduiVsabRef  = $g_valids{'SduiVsab'};
  my $_valSduiRsabRef  = $g_valids{'SduiRsab'};
  my $_valSrcAtomsRef  = $g_valids{'SrcAtoms'};

  # valids info from relationships
  my $_valRelIdRef     = $g_valids{'RelId'};
  my $_valSruiVsabRef  = $g_valids{'SruiVsab'};
  my $_valSruiRsabRef  = $g_valids{'SruiRsab'};

  # valids  info from ExtIds file.
  my $_valAuiRef = $g_valids{'AUI'};



  sub init {
	my ($self, $log, $cfg) = @_;
	$_theLog = $log;
	$_theCfg = $cfg;
  }


  sub new {
	my $class = shift;

	# read and set variables from config file.$_inDir and $_reportFile
	$_inDir = $$_theCfg->getEle('File.Source');
	$_inDir = &getDir($_inDir);
	$_reportFile = $$_theCfg->getEle('ofReport');
	$_whichP = $$_theCfg->getEle('Which', 31);

	my $ref = {};
	return bless ($ref, $class);
  }

  sub setLogwin {
	my $class = shift;
	if (@_ > 0) {
	  $_logWin = shift;
	}
  }

  sub setPbar {
	my $class = shift;
	$_pbar_cb = shift;
	$_pbar_present = 1;
  }
  sub msg {
	my $msg = shift;
	#print "$msg";
	$$_theLog->logIt("$msg");
	if ($_logWin ne '') {
	  $_logWin->insert('end', $msg);
	}
  }
  sub msg2 {
	my $msg = shift;
	my $mdt = `date`;

	$$_theLog->logIt("$msg => $mdt\n");
	if ($_logWin ne '') {
	  $_logWin->insert('end', "$msg => $mdt\n");
	}
  }


  sub getDir {
	my $path = shift;
	my @inp = split(/\//, $path);
	pop(@inp);
	my $dir = join('/', @inp);
	return $dir;
  }

  sub getInDir { return $_inDir; }
  sub getReportFile { return $_reportFile; }
  sub getWhich { return $_whichP; }
  sub setInDir { my $class = shift; $_inDir = shift; }
  sub setReportFile { my $class = shift; $_reportFile = shift; }
  sub setWhich { my $class = shift; $_whichP = shift; }


  sub process {
	&msg("Using:\n");
	#&msg("\t ConfigFile: $_cfgFile\n");
	&msg("\t ReportFile: $_reportFile\n");
	#&msg("\t ErrosFile:  $_ofErrors\n");
	&msg("\t which : $_whichP\n");

	my $ctime = `date`;
	print "Starting => $ctime\n";
	&msg2("Starting");

	#my $outFile = $$_theCfg->getEle('ofReport');
	if ($_whichP & 1) {
	  if (-e "$_reportFile") {
		# copy previous one.
		my $ii = 1;
		while ($ii < 21) {
		  if (-e "${_reportFile}.prev_$ii") {
		  } else {
			`mv $_reportFile ${_reportFile}.prev_$ii`;
			if (-e "${_reportFile}.err") {
			  `mv $_reportFile.err ${_reportFile}.err.prev_$ii`;
			}
			last;
		  }
		  $ii++;
		}
	  }
	  open (OUT, ">:utf8", $_reportFile)
		or die "Could not open the report file $_reportFile.\n";
	  open (OUT2, ">:utf8", "${_reportFile}.err")
		or die "Could not open the report file ${_reportFile}.err.\n";
	  print OUT "Starting applicaton: w: $_whichP at $ctime\n";
	  print OUT2 "Starting applicaton: w: $_whichP at $ctime\n";
	} else {
	  open (OUT, ">>:utf8", $_reportFile)
		or die "Could not append to the report $_reportFile.\n";
	  open (OUT2, ">>:utf8", "${_reportFile}.err")
		or die "Could not append to the report file ${_reportFile}.err.\n";
	  print OUT "Starting applicaton<Append>: w: $_whichP at $ctime\n";
	  print OUT2 "Starting applicaton<Append>: w: $_whichP at $ctime\n";

	}


	$$_theCfg->setEle('ofhReport', *OUT);
	$$_theCfg->setEle('errhReport', *OUT2);
	CharCount->init($_theLog, $_theCfg);
	FldMon->init($_theLog, $_theCfg);
	LineMon->init($_theLog, $_theCfg);
	QaAtoms->init($_theLog, $_theCfg);
	QaAttrs->init($_theLog, $_theCfg);
	QaMerges->init($_theLog, $_theCfg);
	QaRels->init($_theLog, $_theCfg);
	QaCxts->init($_theLog, $_theCfg);
	QaTGs->init($_theLog, $_theCfg);
	QaSrcs->init($_theLog, $_theCfg);
	QaDocs->init($_theLog, $_theCfg);


	&msg2("Begin");

	# before processing begins, read any external info provided by the
	# user in the file ../etc/ExtInfo; Since we are saving this info along with any
	# info captured in which == 1, we should do this only if (which & 1) case.

	my (@F, $ii);

	## 1. Doc, Sources, Termgroups, Atoms
	# -------------------------------
	my $docErrors = 0;
	if ($_whichP & 1) {

	  my $extInfoFile = "../etc/ExtInfo";
	  if (-e "$extInfoFile") {
		my $tempQaAtom = new QaAtoms();
		$tempQaAtom->recoverResults(\%g_valids, $extInfoFile);
	  }

	  # 1.1 first validate mrdoc file
	  &msg2("Reading Doc file.");
	  if (open (IN, "<:utf8", $$_theCfg->getEle('File.Doc'))) {
		my $docs = new QaDocs();
		$docs->setValidRefs(\%g_valids);
		while (<IN>) {
		  chomp;
		  next if /^\#/ || /^\s*$/;
		  if (/###/) {
			&msg2("Incomplete entries in doc with ####: $_\n");
			$docErrors = 1;
		  }
		  @F = split(/\|/, $_, 5);
		  $docs->process(@F);
		}
		close(IN);
		&msg("\n");
		&msg2("Genarating Doc Report.");
		$docs->report();

	  } else {
		$$_theLog->logIt("Could not find mrdoc. Skipping qa on that.\n");
	  }
	  if ($docErrors == 1) {
		&msg2("Fix MRDOC problems before proceeding. Exiting...");
		close(OUT);
		exit;
	  }


	  # 1.2 next validate sources.src file.
	  &msg2("Reading Source file.");
	  my $srcs = new QaSrcs();
	  $srcs->setValidRefs(\%g_valids);
	  open (IN, "<:utf8", $$_theCfg->getEle('File.Source'))
		or die "no input File.Source file.\n";
	  while (<IN>) {
		chomp;
		next if /^\#/ || /^\s*$/;
		@F = split(/\|/, $_, 21);
		$srcs->process(@F);
	  }
	  close(IN);
	  &msg("\n");
	  &msg2("Genarating Source Report.");
	  $srcs->report();
	  $srcs->setOtherValids();

	  $srcs->release();
	  &msg2("Done Source Report.");
	  &$_pbar_cb(2) if ($_pbar_present == 1);


	  # 1.3 next read and validate termgroups.src file.
	  &msg2("Reading Termgroups file.");
	  my $tgs = new QaTGs();
	  $tgs->setValidRefs(\%g_valids);
	  open (IN, "<:utf8", $$_theCfg->getEle('File.Termgroup'))
		or die "no input File.Termgroup file.\n";
	  while (<IN>) {
		chomp;
		next if /^\#/ || /^\s*$/;
		@F = split(/\|/, $_, 7);
		$tgs->process(@F);
	  }
	  close(IN);
	  &msg("\n");
	  &msg2("Genarating Termgroups Report.");
	  $tgs->report();

	  $tgs->setOtherValids();
	  $tgs->release();
	  &msg2("Done Termgroup Report.");
	  &$_pbar_cb(4) if ($_pbar_present == 1);


	  ## 1.4 now validate atoms file.
	  &msg2("Reading Atoms");
	  my $atms = new QaAtoms();
	  $atms->setValidRefs(\%g_valids);

	  open (IN, "<:utf8", $$_theCfg->getEle('File.Atom'))
		or die "no input File.Atom file.\n";
	  $ii = 0;
	  while (<IN>) {
		chomp;
		$ii++;
		if (($ii % 1000) == 0) {
		  &msg(">");
		}
		if (($ii % 50000) == 0) {
		  &msg("$ii\n");
		}
		next if /^\#/ || /^\s*$/;
		@F = split(/\|/, $_, 16);
		$atms->process(@F);
	  }
	  close(IN);

	  print "\nDone processing atoms.\n";
	  &$_pbar_cb(15) if ($_pbar_present == 1);

	  &msg("$ii\n");
	  &msg2("Generating Atoms Report - read $ii records");

	  $atms->report();
	  $atms->setOtherValids();

	  # add other valid saids here: HC.RootNodeSaid.
	  my $rnSaid = $$_theCfg->getEle('HC.RootNodeSaid', '');
	  if ($rnSaid ne '') {
		$$_valSaidRef{"$rnSaid"}++;
	  }

	  # save results
	  $atms->saveResults(\%g_valids);
	  $atms->release();
	  &msg2("Done Atoms Report");
	} else {
	  # use previously validated results.
	  my $tdir = $$_theCfg->getEle('TEMPDIR');
	  my $tfile = "$tdir/QaInt_DSTA";
	  if (!(-e $tfile)) {
		msg("Error: Atoms file was never QAed before. Do that first.\n");
		return;
	  } elsif ((-e $$_theCfg->getEle('File.Source'))
			   && (-e $$_theCfg->getEle('File.Termgroup'))
			   && (-e $$_theCfg->getEle('File.Doc'))
			   && (-e $$_theCfg->getEle('File.Atom'))) {
		my @fStats;
		@fStats = stat($tfile);
		my $qaTime = $fStats[9];
		@fStats = stat($$_theCfg->getEle('File.Source'));
		my $srcTime = $fStats[9];

		@fStats = stat($$_theCfg->getEle('File.Termgroup'));
		my $tgTime = $fStats[9];

		@fStats = stat($$_theCfg->getEle('File.Doc'));
		my $docTime = $fStats[9];

		@fStats = stat($$_theCfg->getEle('File.Atom'));
		my $atomTime = $fStats[9];
		if ($qaTime > $srcTime && $qaTime > $docTime
			&& $qaTime > $tgTime && $qaTime > $atomTime) {
		  my $atms = new QaAtoms();
		  $atms->recoverResults(\%g_valids);
		} else {
		  msg("Error: Files src/doc/tg/atoms are modified since last "
			  ."AtomQa.\n\t QA Atoms file first.\n");
		  return;
		}
	  } else {
		msg("Error: Not all files src/doc/tg/atoms are present.\n");
		return;
	  }
	}
	$ctime = `date`;
	print "Processed Atoms  => $ctime\n";
	print OUT "Processed Atoms => $ctime\n";

	&$_pbar_cb(20) if ($_pbar_present == 1);



	## 2. Relations
	## ------------
	if ($_whichP & 8) {
	  &msg2("Reading Rels");
	  my $rels = new QaRels();
	  $rels->setValidRefs(\%g_valids);

	  open (IN, "<:utf8", $$_theCfg->getEle('File.Relation'))
		or die "no input File.Relation file.\n";

	  $ii = 0;
	  while (<IN>) {
		$ii++;
		if (($ii % 1000) == 0) {
		  &msg(">");
		}
		if (($ii % 50000) == 0) {
		  &msg("$ii\n");
		}
		chomp;
		next if /^\#/ || /^\s*$/;
		@F = split(/\|/, $_, 19);
		$rels->process(@F);
	  }
	  close(IN);
	  &$_pbar_cb(55) if ($_pbar_present == 1);

	  &msg("$ii\n");

	  &msg2("Generating Rels Report - read $ii records");
	  $rels->setOtherValids();
	  $rels->saveResults(\%g_valids);

	  $rels->report();
	  $rels->release();
	  &msg2("Done Rel Report");
	} else {
	  if (($_whichP & 2) || ($_whichP & 4) || ($_whichP & 16)) {
		# use previously validated results.
		# first check if the file exists.
		my $tdir = $$_theCfg->getEle('TEMPDIR');
		my $relFile = "$tdir/QaInt_REL";
		if (-e $relFile) {
		  # check that the file is newer than rels file.
		  if (-e $$_theCfg->getEle('File.Relation')) {
			my @fStats = stat($relFile);
			my $qaTime = @fStats[9];
			@fStats = stat($$_theCfg->getEle('File.Relation'));
			my $relTime = $fStats[9];
			if ($qaTime > $relTime) {
			  my $rels = new QaRels();
			  $rels->recoverResults(\%g_valids);
			} else {
			  msg("Error: File relationshps was modified since last "
				  ." RelQa.\n\t Qa Rels file first.\n");
			  return;
			}
		  } else {
			msg("Eror relationships.src file does not exist.\n");
			return;
		  }
		} else {
		  msg("You must first validate Relations file before"
			  . " validaring attributes/cxts/merges.\n\t"
			  . " Please validate Relations.\n");
		  return;
		}
	  }
	}
	$ctime = `date`;
	print "Processed Rels  => $ctime\n";
	print OUT "Processed Rels => $ctime\n";

	&$_pbar_cb(40) if ($_pbar_present == 1);



	## 3. Contexts
	## -----------
	if ($_whichP & 16) {
	  &msg2("Reading Contexts");
	  my $cxts = new QaCxts();
	  $cxts->setValidRefs(\%g_valids);

	  if (open (IN, "<:utf8", $$_theCfg->getEle('File.Context'))) {
		$ii = 0;
		while (<IN>) {
		  $ii++;
		  if (($ii % 1000) == 0) {
			&msg(">");
		  }
		  if (($ii % 50000) == 0) {
			&msg("$ii\n");
		  }
		  chomp;
		  next if /^\#/ || /^\s*$/;
		  @F = split(/\|/, $_, 18);
		  $cxts->process(@F);
		}
		close(IN);
		&$_pbar_cb(95) if ($_pbar_present == 1);

		&msg("$ii\n");

		&msg2("Generating Contexts Report - read $ii records");
		$cxts->setOtherValids();
		$cxts->saveResults(\%g_valids);

		$cxts->report();
		$cxts->release();
		&msg2("Done Contexts Report");
	  } else {
		&msg2("No Contexts to process.");
	  }
	} else {
	  if (($_whichP & 2) || ($_whichP & 4)) {
		# use previously validated results.
		# read valid SRUIs (from cxt file) and append them to _valSrui*sabRef
		my $tdir = $$_theCfg->getEle('TEMPDIR');
		my $relFile = "$tdir/QaInt_REL2";
		if (-e $relFile) {
		  # check that the file is newer than rels file.
		  if (-e $$_theCfg->getEle('File.Context')) {
			my @fStats = stat($relFile);
			my $qaTime = @fStats[9];
			@fStats = stat($$_theCfg->getEle('File.Context'));
			my $relTime = $fStats[9];
			if ($qaTime > $relTime) {
			  my $cxts = new QaCxts();
			  $cxts->recoverResults(\%g_valids);
			} else {
			  msg("Error: File contexts was modified since last "
				  ." CxtQa.\n\t Qa Cxts file first.\n");
			  return;
			}
		  } else {
			msg("Eror contexts.src file does not exist.\n");
			return;
		  }
		} else {
		  $$_theLog->logIt("You must first validate Contexts file before"
						   . " validaring attributes/merges.\n\t"
						   . " Please validate Contexts.\n");
		  return;
		}
	  }
	}
	$ctime = `date`;
	print "Processed Contexts  => $ctime\n";
	print OUT "Processed Contexts => $ctime\n";

	&$_pbar_cb(60) if ($_pbar_present == 1);


	## 4. Attributes.
	## -------------
	if ($_whichP & 2) {
	  &msg2("Reading Attributes");
	  my $attrs = new QaAttrs();
	  $attrs->setValidRefs(\%g_valids);

	  open (IN, "<:utf8", $$_theCfg->getEle('File.Attribute'))
		or die "no input File.Attribute file.\n";
	  $ii = 0;
	  while (<IN>) {
		$ii++;
		if (($ii % 1000) == 0) {
		  &msg(">");
		}
		if (($ii % 50000) == 0) {
		  &msg("$ii\n");
		}
		chomp;
		next if /^\#/ || /^\s*$/;
		@F = split(/\|/, $_, 15);
		$attrs->process(@F);
	  }
	  close(IN);
	  &$_pbar_cb(35) if ($_pbar_present == 1);

	  &msg("$ii\n");
	  &msg2( "Generating Attributes Report - read $ii records");
	  $attrs->report();
	  $attrs->setOtherValids();
	  $attrs->release();
	  &msg2("Done Attributes Report");
	}
	$ctime = `date`;
	print "Processed Attrs  => $ctime\n";
	print OUT "Processed Attrs => $ctime\n";

	&$_pbar_cb(80) if ($_pbar_present == 1);


	## 4. Merges
	## ---------
	if ($_whichP & 4) {
	  &msg2("Reading Merges");
	  my $mrgs = new QaMerges();
	  $mrgs->setValidRefs();

	  open (IN, "<:utf8", $$_theCfg->getEle('File.Merge'))
		or die "no input File.Merge file.\n";
	  $ii = 0;
	  while (<IN>) {
		$ii++;
		if (($ii % 1000) == 0) {
		  &msg(">");
		}
		if (($ii % 50000) == 0) {
		  &msg("$ii\n");
		}
		chomp;
		next if /^\#/ || /^\s*$/;
		@F = split(/\|/, $_, 13);
		$mrgs->process(@F);
	  }
	  close(IN);
	  &$_pbar_cb(75) if ($_pbar_present == 1);

	  &msg("$ii\n");

	  &msg2("Generating Merges Report - read $ii records");
	  $mrgs->report();
	  $mrgs->release();
	  &msg2("Done Merge Report");
	}
	$ctime = `date`;
	print "Processed Merges  => $ctime\n";
	print OUT "Processed Merges => $ctime\n";

	&$_pbar_cb(100) if ($_pbar_present == 1);


	close(OUT);
	close(OUT2);
  }


  sub InvalidSg {
	my ($self, $id, $idt, $idq) = @_;
	my $key = "$id|$idq";

	# validate sgId1, sgType1, sgQual1
	if ($idt eq 'SRC_ATOM_ID') {
	  return defined($$_valSaidRef{"$id"}) ? 0 : 'VInvSrcAtomId';

	} elsif ($idt eq 'AUI') {
	  return defined($$_valAuiRef{"$id"}) ? 0 : 'VInvAUIId';

	} elsif ($idt eq 'CODE_SOURCE') {
	  return 0 if (defined($$_valCdVsabRef{"$key"}));
	  my ($val, $src) = split(/\|/, $key);
	  return 'VinvCodeSource' if ($src ne 'SRC');

	  ($val, $src) = split(/\-/, $val);
	  return 0 if ($val eq 'V' && defined($$_valRsabRef{"$src"}));
	  return 'VinvCodeSource';

	} elsif ($idt eq 'CODE_ROOT_SOURCE') {
	  return defined($$_valCdRsabRef{"$key"}) ? 0 : 'VInvCodeRootSource';

	} elsif ($idt eq 'CODE_TERMGROUP') {
	  return defined($$_valCdVTGRef{"$key"}) ? 0 : 'VInvCodeTermgroup';

	} elsif ($idt eq 'CODE_ROOT_TERMGROUP') {
	  return defined($$_valCdRsabRef{"$key"}) ?	0 : 'VInvCodeRootTermgroup';

	} elsif ($idt eq 'SOURCE_AUI') {
	  return defined($$_valSauiVsabRef{"$key"}) ? 0 : 'VInvSourceAui';

	} elsif ($idt eq 'ROOT_SOURCE_AUI') {
	  return defined($$_valSauiRsabRef{"$key"}) ? 0 : 'VInvRootSourceAui';

	} elsif ($idt eq 'SOURCE_CUI') {
	  return defined($$_valScuiVsabRef{"$key"}) ? 0 : 'VInvSourceCui';

	} elsif ($idt eq 'ROOT_SOURCE_CUI') {
	  return defined($$_valScuiRsabRef{"$key"}) ? 0 : 'VInvRootSourceCui';

	} elsif ($idt eq 'SOURCE_DUI') {
	  return defined($$_valSduiVsabRef{"$key"}) ? 0 : 'VInvSourceDui';

	} elsif ($idt eq 'ROOT_SOURCE_DUI') {
	  return defined($$_valSduiRsabRef{"$key"}) ? 0 : 'VInvRootSourceDui';

	} elsif ($idt eq 'SOURCE_RUI') {
	  return defined($$_valSruiVsabRef{"$key"}) ? 0 : 'VInvSourceRui';

	} elsif ($idt eq 'ROOT_SOURCE_RUI') {
	  return defined($$_valSruiRsabRef{"$key"}) ? 0 : 'VInvRootSourceRui';

	} elsif ($idt eq 'SRC_REL_ID') {
	  return defined($$_valRelIdRef{"$id"}) ? 0 : 'VInvSrcRelId';
	}


	return 'VUnknownSgType';
  }

  sub IsValidSrcAtom {
	my ($self, $tg, $said) = @_;
	return 1 if (grep($said, @{$$_valSrcAtomsRef{"$tg"}}));
	return 0;
  }

}

1
