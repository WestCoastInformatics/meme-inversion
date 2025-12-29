#!/usr/bin/perl
#!/usr/bin/perl
#
unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";


use strict 'vars';
use strict 'subs';

package MakeDoc;
{
  my ($_inDir, $_pbar_cb);
  my $logwin = '';
  my $_pbar_present = 0;

  my %doc12to34=();
  my %rela2irela=();
  my %infoFromSrc=();
  
  sub new {
	my $class = shift;
	$_inDir = "../src";
	my $ref = {};
	return bless ($ref, $class);
  }

  sub setLogwin {
	my $class = shift;
	if (@_ > 0) {
	  $logwin = shift;
	}
  }

  sub setPbar {
	my $class = shift;
	$_pbar_cb = shift;
	$_pbar_present = 1;
  }

  sub msg {
	my $msg = shift;
	print "$msg";
	if ($logwin ne '') {
	  $logwin->insert('end', $msg);
	}
  }

  sub getMrDoc {


      # get RELA and inverses (in both directions)
      my @rows = `$ENV{INV_HOME}/bin/api_metadata.sh rela_inverse --quiet`;
      chomp(@rows);
      my $row;
      foreach $row (@rows) {
          #print "Found a row: $row\n";
          my ($rela, $irela) = split /\|/, $row;
          $rela2irela{$rela} = $irela;
          push(@{$doc12to34{"RELA|$rela"}}, "rela_inverse|$irela");
      }

      # Get expanded forms
      @rows = `$ENV{INV_HOME}/bin/api_metadata.sh expanded_form --quiet`;
      chomp(@rows);

      foreach $row (@rows) {
          my ($type, $abbr, $key, $value) = split /\|/, $row;
	  push(@{$doc12to34{"$type|$abbr"}}, "$key|$value");
      }
      
      # Get TTY class
      @rows = `$ENV{INV_HOME}/bin/api_metadata.sh tty_class --quiet`;
      chomp(@rows);

      foreach $row (@rows) {
          my ($type, $abbr, $key, $value) = split /\|/, $row;
	  if ($value eq "UNDEFINED") {
		push(@{$doc12to34{"$type|$abbr"}}, "$key|other");
	  } elsif ($value eq 'EXPANDED') {
		push(@{$doc12to34{"$type|$abbr"}}, "$key|expanded");
	  } elsif ($value eq 'AB') {
	      push(@{$doc12to34{"$type|$abbr"}}, "$key|abbreviation");
	  } elsif ($value eq 'ET') {
	      push(@{$doc12to34{"$type|$abbr"}}, "$key|entry_term");
	  } elsif ($value eq 'PET') {
	      push(@{$doc12to34{"$type|$abbr"}}, "$key|preferred");
	      push(@{$doc12to34{"$type|$abbr"}}, "$key|entry_term");
	  } elsif ($value eq 'PN') {
	      push(@{$doc12to34{"$type|$abbr"}}, "$key|preferred");
	  } elsif ($value eq 'SY') {
	      push(@{$doc12to34{"$type|$abbr"}}, "$key|synonym");
	  } else {
	      push(@{$doc12to34{"$type|$abbr"}}, "$key|$value");
	  }
	  
      }
  }

  sub getTtyAtnRela {
	my $dt;
	my @F;
	# read TTYs from termgroups
	open(IN, "<:utf8", "$_inDir/termgroups.src")
	  or die "Could not open $_inDir/termgroups.src file\n";
	while (<IN>) {
	  chomp;
	  @F = split(/\|/, $_);
	  $infoFromSrc{"TTY|$F[5]"}++;
	}
	close(IN);
	$dt = `date`;
	&msg("Got info from $_inDir/termgroups.src <$dt>\n");
	&$_pbar_cb(20) if ($_pbar_present == 1);

	# read RELAs from relationships
	open(IN, "<:utf8", "$_inDir/relationships.src")
	  or die "Could not open $_inDir/relationships.src file\n";
	while (<IN>) {
	  chomp;
	  @F = split(/\|/, $_);
	  $infoFromSrc{"RELA|$F[4]"}++;
          
          if(defined($rela2irela{"$F[4]"})){
          my $inverserela = $rela2irela{"$F[4]"};
          $infoFromSrc{"RELA|$inverserela"}++;
          }
	}
	close(IN);

	$dt = `date`;
	&msg("Got info from $_inDir/relationships.src <$dt>\n");
	&$_pbar_cb(50) if ($_pbar_present == 1);

	# read ATNs from attributes. ignore CONTEXT, SEMANTIC_TYPE, XMAP, XMAPFROM,
	#       XMAPTO, DEFINITION, LEXICAL_TAG, COMPONENTHISTORY
	my %ignore = (CONTEXT => 0,
				  SEMANTIC_TYPE => 0,
				  XMAP => 0,
				  XMAPFROM => 0,
				  XMAPTO => 0,
				  DEFINITION => 0,
				  LEXICAL_TAG => 0,
				  COMPONENTHISTORY => 0);

	open(IN, "<:utf8", "$_inDir/attributes.src")
	  or die "Could not open $_inDir/attributes.src file\n";
	while (<IN>) {
	  chomp;
	  @F = split(/\|/, $_);
         
         #get the Hidden attribute names in ATV field for ATN=SUBSET_MEMBER
            if (($F[3] eq "SUBSET_MEMBER") && ($F[4] =~ /\~/)){
              
          my  @tempfield = split(/~/, $F[4]);
          my  $subfield = @tempfield[1];  
             $infoFromSrc{"ATN|$subfield"}++;

             }

	  next if (defined($ignore{"$F[3]"}));
	  $infoFromSrc{"ATN|$F[3]"}++;
	}
	close(IN);
	$dt = `date`;
	&msg("Got info from $_inDir/attributes.src <$dt>\n");
	&$_pbar_cb(90) if ($_pbar_present == 1);

  }

  sub makeMrDoc {
	my $class;
	($class, $_inDir) = @_;
print "class=$class";
print OUT "indir=$_inDir";

	if (-e "$_inDir/MRDOC.RRF") {
	  &msg("  **MRDOC.RRF already exists. Delete it first and run. Exiting.\n");
	  return;
	}

	my $dt = `date`;
	&msg("Starting <$dt>\n");

	&getMrDoc;
	$dt = `date`;
	&msg("Got data from db <$dt>\n");
	&$_pbar_cb(15) if ($_pbar_present == 1);


	&getTtyAtnRela;
	$dt = `date`;
	&msg("Got data from src files <$dt>\n");

	open (OUT, ">:utf8", "$_inDir/MRDOC.RRF")
	  or die "Could not open $_inDir/MRDOC.RRF\n";
	my ($key, $f1, $f2, $val);
	foreach $key (keys %infoFromSrc) {
	  if (defined($doc12to34{"$key"})) {
		# existing entry
		foreach $val (@{$doc12to34{"$key"}}) {
		  print OUT "$key|$val|\n";
		}
	  } else {
		# create new entries.
		($f1, $f2) = split(/\|/, $key);
		if ($f1 eq 'TTY') {
		  print OUT "$key|expanded_form|####|\n";
		  print OUT "$key|tty_class|####|\n";
		} elsif ($f1 eq 'RELA') {
		  print OUT "$key|expanded_form|####|\n";
		  print OUT "$key|rela_inverse|####|\n";

		  print OUT "$f1|###inverse_of###$f2###|expanded_form|####|\n";
		  print OUT "$f1|###|rela_inverse|$f2|\n";

		} elsif ($f1 eq 'ATN') {
		  print OUT "$key|expanded_form|###|\n";
		} else {
		  &msg("Illegal value $key present in files. skipping.\n");
		}
	  }
	}
	close(OUT);
	$dt = `date`;
	&msg("Done <$dt>\n");
	&$_pbar_cb(100) if ($_pbar_present == 1);
  }
}
1;
