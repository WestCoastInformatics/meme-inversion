#!/usr/bin/perl
#!/usr/bin/perl

# A perl interface to the MID services

# suresh@nlm.nih.gov 9/98 - original
# suresh@nlm 6/2002 - updated

package Midsvcs;

sub get {
  my($self, $svc) = @_;

  die "Need MIDSVCS_HOME to be set\n" unless $ENV{MIDSVCS_HOME};

  my $services = $self->load;
  if ($svc) {
	return $services->{$svc};
  }

  return $services;
}

# returns all the services and values in a hash
sub load {
  my($self) = @_;
  my($services, @x, $script);

  $services = {};
  ($script) = $ENV{MIDSVCS_HOME} . "/bin/midsvcs.pl";
  open(S, "$script|") || return $services;

  while (<S>) {
    chomp;
    @x = split /\|/, $_, 2;
    $services->{$x[0]} = $x[1];
  }
  close(S);
  return $services;
}

1;
