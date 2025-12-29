#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package LineMon;

{
  my ($_theLog, $_theCfg, $_OUT, $_EOUT);
  my %_valids = (name => 0, tally => 0, query => 0, unique => 0);

  sub init {
	my ($self, $log, $cfg) = @_;
	$_theLog = $log;
	$_theCfg = $cfg;
	$_OUT = $$_theCfg->getEle('ofhReport');
	$_EOUT = $$_theCfg->getEle('errhReport');
  }

  sub new {
	my ($class, $file, $monNum) = @_;
	my $ref = {file => $file,
			   fnum => $monNum,
			   name => 'NONE',
			   tally => '',
			   query => '',
			   unique => 0,

			   errs => '',
			   all => '',
			   queryErrsN => 0,

			   doFldCt => 0,
			   doTally => 0,
			   doQuery => 0};


	my ($temp, $key, $val);
	my %thsh = ();
	$$ref{'errs'} = \%thsh;
	my %thsh2=();
	$$ref{'all'} = \%thsh2;

	# now apply provided vals from config file.
	my $nm = "LineMon.$file.$monNum";
	$$ref{'name'} = $$_theCfg->getEle("$nm.name", $nm);
	$$ref{'tally'} = $$_theCfg->getEle("$nm.tally", '');
	$$ref{'query'} = $$_theCfg->getEle("$nm.query", '');
	$$ref{'unique'} = $$_theCfg->getEle("$nm.unique", 0);

	$$ref{'doTally'} = 1 if ($$ref{'tally'} ne '');
	if ($$ref{'query'} ne '') {
	  $$ref{'doQuery'} = 1;
	}
	$$ref{'unique'} = 0 if ($$ref{'unique'} eq '');
	my ($i,$j, $k);
	$i = $ref->{'doTally'};
	$j = $ref->{'doQuery'};
	$k = $ref->{'unique'};
	#print "created $nm <$i, $j, $k>\n";
	return bless ($ref, $class);
  }


  sub process {
	my $self = $_[0];
	my $href = $self->{'errs'};
	my $recId = $self->{'numRecs'}++;
	my ($msg, $ln, $monNm, $res);
	#print "LMON.process called with @_\n";

	# check tally if any
	# check invalid pattern
	if ($self->{'doQuery'} == 1) {
	  #print "doing Query\n";
	  $res = eval ($self->{'query'});
	  if ($@) {
		warn $@;
		$$_theLog->logIt("Illegal query pattern1: \n\t<$self->{'query'}>\n");
	  }
	  if ($res) {
		#print "query returned positive\n";
		# process depend on unique flag.
		if ($self->{'unique'} == 0) {
		  #print "\tNot unique\n";
		  # error
		  if ($self->{'queryErrsN'}++ < 10) {
			$monNm = $self->{'name'};
			if ($self->{'doTally'} == 1) {
			  $$href{"Vquery_${monNm}_$recId"} = eval($self->{'tally'});
			  if ($@) {
				warn $@;
				$$_theLog->logIt("Illegal tally pattern2: \n\t<$self->{'tally'}>\n");
			  }
			} else {
			  # print the whole line.
			  $$href{"Vquery_${monNm}_$recId"} = join('|', @_[1..$#{@_}]);
			}
		  }
		} else {
		  # report only if more than 1 rec exists.
		  if ($self->{'doTally'} == 1) {
			$msg = eval($self->{'tally'});
			if ($@) {
			  warn $@;
			  $$_theLog->logIt("Illegal tally pattern3: \n\t<$self->{'tally'}>\n");
			}
		  } else {
			$msg = join('|', @_[1..$#{@_}]);
		  }
		  $ln = ${$self->{'all'}}{"$msg"}++;
		  #$ln = $$self->{'all'}{"$msg"}++;
		  if ($ln > 0) {
			if ($self->{'queryErrsN'}++ < 10) {
			  $monNm = $self->{'name'};
			  $$href{"VQuery_${monNm}_$recId"} = $msg;
			}
		  }
		}
	  } else {
		#print "Query failed\n";
	  }
	} elsif ($self->{'doTally'} == 1) {
	  # process depending on unique flag.
	  $msg = eval($self->{'tally'});
	  if ($@) {
		warn $@;
		$$_theLog->logIt("Illegal tally pattern4: \n\t<$self->{'tally'}>\n");
	  }

	  $ln = ${$self->{'all'}}{"$msg"}++;
	  if (($self->{'unique'} != 0) && ($ln > 0)) {
		if ($self->{'queryErrsN'}++ < 10) {
		  $monNm = $self->{'name'};
		  $$href{"Vquery_${monNm}_$recId"} = $msg;
		}
	  }
	}
	#print "LMON.exit\n";
  }

  sub reportNOTNEEDED {
	my $self = shift;

	print $_OUT "\nLM File: $self->{'file'}\tField: $self->{'name'} "
	  ."<$self->{'fnum'}>\n";


	my $temp = uc($self->{'type'});
	my $temp1;
	if ($temp eq 'ERROR') {
	  $temp1 = "***ERR: ";
	} elsif ( $temp eq 'WARNING') {
	  $temp1 = "WARN: ";
	} else {
	  $temp1 = "INFO: ";
	}
	print $_OUT "\tfldCtVoils:  $self->{'fldCtErrsN'} \n"
	  if ($self->{'doFldCt'} == 1 && $self->{'fldCtErrsN'} > 0);
	print $_OUT "\tqueryVoils:  $self->{'queryErrsN'} \n"
	  if (($self->{'doQuery'} == 1 || $self->{'doTally'} == 1)
		  && $self->{'queryErrsN'} > 0);

	my ($err, $val, $href);
	$href = $self->{'errs'};
	foreach $err (sort keys (%$href)) {
	  $val = $$href{"$err"};
	  print $_OUT "\t$temp1 $err => $val\n";
	}

	my $ele;
	my $allRef = $self->{'all'};
	if ($self->{'doTally'} == 1 && $self->{'doQuery'} == 0
		&& $self->{'unique'} == 0) {
	  print $_OUT "  Tally: $self->{'tally'}\n";
	  foreach $ele (sort keys (%$allRef)) {
		$val = ${$allRef}{"$ele"};
		print $_OUT "\t$ele => $val\n";
	  }
	  print $_OUT "\n";
	}
  }

  sub reportInfo {
	my $self = shift;
	# only simple tally goes here.
	return if (!($self->{'doTally'} != 0 && $self->{'doQuery'} == 0
				 && $self->{'unique'} == 0));

	print $_OUT "\nLM $self->{'file'}.$self->{'fnum'}.$self->{'name'}\n";
	print $_OUT "  Tally: $self->{'tally'}\n";
	my $allRef = $self->{'all'};
	my ($ele, $val);
	foreach $ele (sort keys (%$allRef)) {
	  $val = ${$allRef} {"$ele"};
	  print $_OUT "\t$ele => $val\n";
	}
	print $_OUT "\n";
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

	if ($self->{'queryErrsN'} > 0) {
	  print $_EOUT "\nLM $self->{'file'}.$self->{'fnum'}.$self->{'name'}\n";
	  print $_EOUT "\tqueryVoils:  $self->{'queryErrsN'} \n";

	  my ($err, $val, $href);
	  $href = $self->{'errs'};
	  foreach $err (sort keys (%$href)) {
		$val = $$href{"$err"};
		print $_EOUT "\t$EW $err => $val\n";
	  }
	}
  }

  sub getErrsHsh { my $self = shift; return $self->{'errs'}; }
}


1

