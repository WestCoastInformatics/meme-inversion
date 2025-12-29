#!/usr/bin/perl
#!/usr/bin/perl
#

unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

package Logger;


# Error, Warning, Info, Debug
our %_valids = (ERROR => 1, WARNING => 2, INFO => 3, DEBUG => 4);

sub new {
  my ($class, $logFile, $logMode, $logLevel) = @_;
  open(LF, $logMode eq 'Append' ? ">>:utf8" : ">:utf8", $logFile)
    or die "Could not open log file $logFile\n";
  my $temp = 1;
  if (defined($_valids{"$logLevel"})) {
    $temp = $_valids{"$logLevel"};
  }

  my $ref = { _LOG => \*LF,
			  _level => $temp,
			  _toScreen => $temp,
			  _totErrs => 0,
			  _totWrns => 0,
			  _totInfo => 0,
			  _totDbgs => 0};
  return bless ($ref, $class);
}

sub setFileHandle {
  my ($self, $temp) = @_;
  $self->{'_LOG'} = $temp if (defined($temp));
}


sub printToScreen {
  my ($self, $temp) = @_;
  $temp = 1 if (!defined($temp) || !defined($_valids{"$temp"}));
  $self->{'_toScreen'} = $_valids{"$temp"};

  print {$self->{'_LOG'}} "PrintToScreen set to $temp\n";
  #my $temp = $self->{'_LOG'};
  #print $temp "PrintToScreen set to $temp\n";

  print "PrintToScreen set to $temp\n";
}

sub setLevel {
  my ($self, $temp) = @_;
  $temp = 1 if (!defined($temp) || !defined($_valids{"$temp"}));
  $self->{'_level'} = $_valids{"$temp"};

  print {$self->{'_LOG'}} "LogLevel set to $temp\n";
  print "LogLevel set to $temp\n";

  # set the print to screen also.
  $self->printToScreen($temp);
}

sub logError {
  my ($self, $msg) = @_;
  if ($self->{'_level'} > 0) {
    print {$self->{'_LOG'}} "ERR:\t$msg";
    print "ERR:\t$msg" if ($self->{'_toScreen'} > 0);
    $self->{'_totErrs'}++;
  } else {
    my $temp = $self->{'_level'};
    print "logError <$temp> called with $msg.\n";
  }
}

sub logWarning {
  my ($self, $msg) = @_;
  if ($self->{'$_level'} > 1) {
    print {$self->{'_LOG'}} "WARN:\t$msg";
    print "WARN:\t$msg" if ($self->{'_toScreen'} > 1);
    $self->{'_totWrns'}++;
  }
}
sub logInfo {
  my ($self, $msg) = @_;
  if ($self->{'_level'} > 2) {
    print {$self->{'_LOG'}} "INFO:\t$msg";
    print "INFO:\t$msg" if ($self->{'_toScreen'} > 2);
    $self->{'_totInfo'}++;
  }
}
sub logDebug {
  my ($self, $msg) = @_;
  if ($self->{'_level'} > 3) {
    print {$self->{'_LOG'}} "DBG:\t$msg";
    print "DBG:\t$msg" if ($self->{'_toScreen'} > 3);
    $self->{'_totDbgs'}++;
  }
}

# unconditional loggging. (example for times etc..)
sub logIt {
  my ($self, $msg) = @_;
  print {$self->{'_LOG'}} "$msg";
  print "$msg";
}

sub getLogStats {
  my ($self) = @_;
  return "$self->{_totErrs}|$self->{_totWrns}|"
    ."$self->{_totInfo}|$self->{_totDbgs}"; 
}

sub closeLog {
  my ($self) = @_;
  print {$self->{'_LOG'}} "# of errors:\t$self->{'_totErrs'}\n";
  print {$self->{'_LOG'}} "# of warnings:\t$self->{'_totWrns'}\n";
  print {$self->{'_LOG'}} "# of Infos:\t$self->{'_totInfo'}\n";
  print {$self->{'_LOG'}} "# of Debugs:\t$self->{'_totDbgs'}\n\n";
  close($self->{'_LOG'});
}

1

