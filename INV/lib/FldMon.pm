#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';


package FldMon;

use CharCount;

{
  my ($_theLog, $_theCfg, $_OUT, $_EOUT);
  my $disableCharTally = 0;
  my %_valids = (name => 0, fieldNum => 0, minLimit => 0, maxLimit => 0,
				 nullable => 0,	unique => 0, valPat => 0, invPat => 0,
				 charTally => 0, tally => 0, utf8 => 0, type => 0,
				 checkWS => 0);
  my %seenErrors=();

  sub init {
	my ($self, $log, $cfg) = @_;
	$_theLog = $log;
	$_theCfg = $cfg;
	$_OUT = $$_theCfg->getEle('ofhReport');
	$_EOUT = $$_theCfg->getEle('errhReport');
	$disableCharTally = $$_theCfg->getEle('FieldMon.DisableCharTally', 0);
  }

  sub new {
	my ($class, $defTag, $which) = @_;
	my $ref = {file => $defTag,
			   fieldNum => 0,
			   name => 'NONE',
			   minLimit => -1,
			   maxLimit => -1,
			   nullable => 1,
			   unique => 0,
			   valPat => '',
			   invPat => '',
			   charTally => 0,
			   tally => 0,
			   utf8 => 0,
			   type => '',
			   checkWS => 1,

			   valPatCmpl => '',
			   invPatCmpl => '',
			   min => 1000000,
			   max => 0,
			   avg => 0,
			   zeroFlds => 0,
			   numRecs => 0,
			   EWhiteSpace => 0,
			   EMinLimit => 0,
			   EMaxLimit => 0,
			   ENullFlds => 0,
			   EValPat => 0,
			   EInvPat => 0,
			   EUnique => 0,
			   EUtf8 => 0,

			   errs => '',
			   all => '',

			   doValPat => 0,
			   doInvPat => 0,
			   logType => '',
			   ccRef => new CharCount()};

	my ($temp, $key, $val);
	my %thsh = ();
	$$ref{'errs'} = \%thsh;
	my %thsh2 = ();
	$$ref{'all'} = \%thsh2;
	# now apply specific defaults
	if ($defTag ne '') {
	  $temp = \%{$$_theCfg->getHashRef("FieldMon.$defTag.$which")};
	  while (($key, $val) = each %{$temp}) {
		if (defined ($_valids{"$key"})) {
		  $$ref{"$key"} = $val;
		} else {
		  $$_theLog->logError("Invalid QaFld attribute <$key> encountered".
							  " while processing FieldMon.$defTag.$which.\n".
							  "\tIgnoring..\n");
		}
	  }
	}
	if ($$ref{"valPat"} ne '') {
	  $$ref{'doValPat'} = 1;
	  $$ref{'valPatCmpl'} = qr/$$ref{'valPat'}/;
	}
	if ($$ref{"invPat"} ne '') {
	  $$ref{'doInvPat'} = 1;
	  $$ref{'invPatCmpl'} = qr/$$ref{'invPat'}/;
	}

	if ($$ref{"unique"} eq '') {
	  $$ref{'unique'} = 0;
	}
	if ($$ref{"charTally"} eq '') {
	  $$ref{'charTally'} = 0;
	}

	if ($$ref{"minLimit"} eq '') {
	  $$ref{'minLimit'} = -1;
	}
	if ($$ref{"maxLimit"} eq '') {
	  $$ref{'maxLimit'} = -1;
	}
	if ($$ref{"nullable"} eq '') {
	  $$ref{'nullable'} = 1;
	}
	if ($$ref{"charTally"} eq '') {
	  $$ref{'charTally'} = 0;
	}
	if ($$ref{"tally"} eq '') {
	  $$ref{'tally'} = 0;
	}

	return bless ($ref, $class);
  }

  sub setTally {
	my ($self, $val) = @_;
	if (!defined($val) || $val eq '') {
	  $val = 0;
	}
	$self->{'charTally'} = $val;
  }

  sub process {
	my ($self, $data, $temp) = @_;
	my $recId = "${temp}_$self->{'fieldNum'}";

	my ($ln, $key, $val, $cur, $href, $ch);

	if (!defined($data)) {
	  $data = '';
	}
	$ln = length($data);
	$self->{'numRecs'}++;

	$self->{'min'} = $ln if ($ln < $self->{'min'});
	$self->{'max'} = $ln if ($ln > $self->{'max'});
	$self->{'avg'} += $ln;
	if ($ln == 0) {
	  $self->{'zeroFlds'}++;
	}

	# check multiple whitespace
	#if ($self->{'checkWS'} && $data =~ /\s{2,}/) {
	if ($self->{'checkWS'} && $data =~ /^\s|\s{2,}|\s$/) {
	  $self->{'EWhiteSpace'}++;
	}

	$href = $self->{'errs'};

	# check min length
	if ($self->{'minLimit'} >= 0 && $ln < $self->{'minLimit'}) {
	  if ($self->{'EMinLimit'}++ < 10) {
		$$href{"EMinLimit_$recId"} = $data;
	  }
	}
	# check max length
	if ($self->{'maxLimit'} >= 0 && $ln > $self->{'maxLimit'}) {
	  if ($self->{'EMaxLimit'}++ < 10) {
		$$href{"EMaxLimit_$recId"} = $data;
	  }

	}
	# check null vals.
	if ($ln == 0) {
	  if ($self->{'nullable'}++ == 0) {
		if ($self->{'ENullFlds'} < 10) {
		  $$href{"ENullFlds_$recId"} = $data;
		}
	  }
	}
	# check valid pattern
	if ($self->{'doValPat'} == 1 && $data ne ''
		&& $data !~ /$self->{'valPatCmpl'}/) {
	  if ($self->{'EValPat'}++ < 10) {
		if (!defined($seenErrors{"ValPat|$data"})) {
		  $$href{"EValPat_$recId"} = $data;
		  $seenErrors{"ValPat|$data"}++;
		} else {
		  $self->{'EValPat'}--;
		}
	  }
	}
	# check invalid pattern
	if ($self->{'doInvPat'} == 1 && $data ne ''
		&& $data =~ /$self->{'invPatCmpl'}/) {
	  if ($self->{'EInvPat'}++ < 10) {
		if (!defined($seenErrors{"InvPat|$data"})) {
		  $$href{"EInvPat_$recId"} = $data;
		  $seenErrors{"InvPat|$data"}++;
		} else {
		  $self->{'EInvPat'}--;
		}
	  }
	}
	# check for unique
	if ($self->{'unique'} == 1 && $data ne '' 
		&& defined($self->{'all'}{"$data"})) {
	  if ($self->{'EUnique'}++ < 10) {
		if (!defined($seenErrors{"EUnique|$data"})) {
		  $$href{"EUnique_$recId"} = $data;
		  $seenErrors{"EUnique|$data"}++;
		} else {
		  $self->{'EUnique'}--;
		}
	  }
	}
	# collect the val if specified.
	# make sure to do this check after the above unique check.
	if ($self->{'tally'} == 1 || $self->{'unique'} == 1) {
	  ${$self->{'all'}}{"$data"}++;
	}
	# check utf8 chars. Deal with charTally here.??????????????
	if (!$disableCharTally) {
	  if ($self->{'charTally'} || $self->{'utf8'}) {
		if (($temp = $self->{'ccRef'}->doLine($data)) > 0) {
		  if ($temp == 2 || $self->{'utf8'} == 0) {
			# invalid char
			if ($self->{'EUtf8'}++ < 10) {
			  $$href{"EUtf8_$recId"} = $data;
			}
		  }
		}
	  }
	}
  }

  sub reportNOTNEEDED {
	my $self = shift;
	print $_OUT "\nFM File: $self->{'file'}\tField: $self->{'name'} "
	  ."<$self->{'fieldNum'}>\n";

	my $avg = 0;
	if ($self->{'numRecs'} > 0) {
	  $avg = $self->{'avg'} / $self->{'numRecs'};
	  $avg = sprintf("%.3f", $avg);
	}

	print $_OUT "  Field Stats:\n";
	print $_OUT "\tNumber of records: $self->{'numrecs'}\n";
	print $_OUT "\tMinLength: $self->{'min'}\n";
	print $_OUT "\tMaxLength: $self->{'max'}\n";
	print $_OUT "\tAvgLength: $avg\n";
	print $_OUT "\tNum of Null fields: $self->{'ENullFlds'}\n";

	print $_OUT "  Violations: \n";
	print $_OUT "\tWhiteSpaces: $self->{EWhiteSpace}\n" 
	  if ($self->{'EWhiteSpace'} > 0);
	print $_OUT "\tMin: $self->{EMinLimit}\n"
	  if ($self->{'EMinLimit'} > 0);
	print $_OUT "\tMax: $self->{EMaxLimit}\n"
	  if ($self->{'EMaxLimit'} > 0);
	print $_OUT "\tValPat: $self->{EValpat}\n"
	  if ($self->{'EValPat'} > 0);
	print $_OUT "\tInvPat: $self->{EInvPat}\n"
	  if ($self->{'EInvPat'} > 0);
	print $_OUT "\tNull Fields: $self->{ENullFlds}\n"
	  if ($self->{'nullable'} == 1 && $self->{'ENullFlds'} > 0);
	print $_OUT "\tNonUnique: $self->{EUnique}\n"
	  if ($self->{'unique'} == 1 && $self->{'EUnique'} > 0);

	my $temp = uc($self->{'type'});
	my $temp1;
	if ($temp eq 'ERROR') {
	  $temp1 = "***ERR: ";
	} elsif ( $temp eq 'WARNING') {
	  $temp1 = "WARN: ";
	} else {
	  $temp1 = "INFO: ";
	}

	#print $_OUT "  $temp\n";
	my ($err, $val, $href);
	$href = $self->{'errs'};
	foreach $err (sort keys (%$href)) {
	  $val = $$href{"$err"};
	  print $_OUT "\t$temp1 $err => $val\n";
	}

	my $ele;
	my $allRef = $self->{'all'};
	if ($self->{'tally'} == 1) {
	  print $_OUT "  Tally Field:\n";
	  foreach $ele (sort keys (%$allRef)) {
		$val = $$allRef{"$ele"};
		print $_OUT "\t$ele => $val\n";
	  }
	  print $_OUT "\n";
	}
  }

  sub reportInfo {
	my $self = shift;
	print $_OUT "\nFM $self->{'file'}.$self->{'fieldNum'}.$self->{'name'}\n";
	my $avg = 0;
	if ($self->{'numRecs'} > 0) {
	  $avg = $self->{'avg'} / $self->{'numRecs'};
	  $avg = sprintf("%.3f", $avg);
	}

	print $_OUT "  Field Stats:\n";
	print $_OUT "\tNumber of records: $self->{'numrecs'}\n";
	print $_OUT "\tMinLength: $self->{'min'}\n";
	print $_OUT "\tMaxLength: $self->{'max'}\n";
	print $_OUT "\tAvgLength: $avg\n";
	print $_OUT "\tNum of Null fields: $self->{'EWhiteSpace'}\n";

	my ($ele, $val);
	my $allRef = $self->{'all'};
	if ($self->{'tally'} == 1) {
	  print $_OUT "  Tally Field:\n";
	  foreach $ele (sort keys (%$allRef)) {
		$val = $$allRef{"$ele"};
		print $_OUT "\t$ele => $val\n";
	  }
	  print $_OUT "\n";
	}
	if ($self->{'charTally'} == 1) {
	  print $_OUT "  CharTally Field:\n";
	  $self->{'ccRef'}->report($_OUT);
	  print $_OUT "\n";
	}
  }

  sub reportErrors {
	my $self = shift;
	$self->reportEW('****ERR: ') if ('ERROR' eq uc($self->{'type'}));
  }
  sub reportWarnings {
	my $self = shift;
	$self->reportEW('WARN: ') if ('WARNING' eq uc($self->{'type'}));
  }

  sub reportEW {
	my ($self, $EW) = @_;

	if ($self->{'EWhiteSpace'} > 0 ||
		$self->{'EMinLimit'} > 0 ||
		$self->{'EMaxLimit'} > 0 ||
		$self->{'EValPat'} > 0 ||
		$self->{'EInvPat'} > 0 ||
		($self->{'nullable'} == 1 && $self->{'ENullFlds'} > 0) ||
		($self->{'unique'} == 1 && $self->{'EUnique'} > 0)) {

	  print $_EOUT "\nFM $self->{'file'}.$self->{'fieldNum'}.$self->{'name'}\n";
	  print $_EOUT "  Violations: \n";

	  print $_EOUT "\tWhiteSpaces: $self->{EWhiteSpcae}\n"
		if ($self->{'EWhiteSpace'} > 0);

	  print $_EOUT "\tMin: $self->{EMinLimit}\t[Limit: $self->{minLimit}]\n"
		if ($self->{'EMinLimit'} > 0);

	  print $_EOUT "\tMax: $self->{EMaxLimit}\t[Limit: $self->{maxLimit}]\n"
		if ($self->{'EMaxLimit'} > 0);

	  print $_EOUT "\tValPat: $self->{EValPat}\t[Pat: $self->{valPat}]\n"
		if ($self->{'EValPat'} > 0);

	  print $_EOUT "\tInvPat: $self->{EInvPat}\t[InvPat: $self->{invPat}]\n"
		if ($self->{'EInvPat'} > 0);

	  print $_EOUT "\tNull Fields: $self->{ENullFlds}\n"
		if ($self->{'nullable'} == 1 && $self->{'ENullFlds'} > 0);

	  print $_EOUT "\tNonUnique: $self->{EUnique}\t[Given: $self->{unique}]\n"
		if ($self->{'unique'} == 1 && $self->{'EUnique'} > 0);

	  #print $_OUT "  $temp\n";
	  print $_EOUT "\n";
	  my ($err, $val, $href);
	  $href = $self->{'errs'};
	  foreach $err (sort keys (%$href)) {
		$val = $$href{"$err"};
		print $_EOUT "\t$EW $err => $val\n";
	  }
	}
  }

  sub getErrsHsh { my $self = shift; return $self->{'errs'}; }
  sub getAllHsh {my $self = shift; return $self->{'all'}; }

}
1

