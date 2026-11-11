#!/bin/tcsh -f
#
# run preinvert{1,2}.s before running invert{1,2}.s
#
# Before running this:
# - >>> update sab.vsab.map to set the proper version (VSAB) for the MTH RSAB.
# - update the "set release" line in runmmsys.s (it's used by updatevsabs.s),
# - create the old/ and Meta/ links and make sure Meta/MRSAB.RRF exists,
# - pre-run "./updatevsabs.s" to make updatevsabs.log listing needed updates,
# - update sab.vsab.map (as necessary according to updatevsabs.log: update the
#   UMLS VSABs to be correct and update the corresponding NCI-formated VSABs
#   accordingly) for the current release's sources
#
# After running preinvert1.s, edit ncisources.spec as needed, and
# then run preinvert2.s

# incantation to fix broken "sort" command:
setenv _POSIX2_VERSION 1

chmod a+w .
#chgrp memegrp .

./updatevsabs.s
if ($status != 0) then
    echo "VSAB preparation failed; ncisources.spec was not replaced." >& /dev/stderr
    exit 1
endif

# Keep the current reviewed plan until a complete proposal succeeds. Retain
# failed candidates and separate diagnostics for inspection in this directory.
set proposal = `mktemp ncisources.spec.guessed.XXXXXXXX`
if ("$proposal" == "") then
    echo "Could not create a source-plan proposal; ncisources.spec was not replaced." >& /dev/stderr
    exit 1
endif
set diagnostics = "${proposal}.stderr"
(./guess.ncisources.spec.pl >! "$proposal") >&! "$diagnostics"
if ($status != 0) then
    echo "Source-plan proposal failed; inspect $proposal and $diagnostics. ncisources.spec was not replaced." >& /dev/stderr
    exit 1
endif
if (! -s "$proposal") then
    echo "Source-plan proposal is empty; inspect $proposal and $diagnostics. ncisources.spec was not replaced." >& /dev/stderr
    exit 1
endif
# Match ordinary redirection permissions without changing the caller's umask.
# Preserve an existing plan's access bits; a new plan uses 0666 & ~umask.
/usr/bin/perl -e 'my ($old, $new) = @ARGV; my $mode; if (-e $old) { my @s = stat($old); @s or die "Cannot stat $old: $!\n"; $mode = $s[2] & 0777; } else { my $mask = umask; $mode = 0666 & ~$mask; } chmod($mode, $new) == 1 or die "Cannot set proposal permissions: $!\n";' ncisources.spec "$proposal" >>& "$diagnostics"
if ($status != 0) then
    echo "Could not set proposal permissions; inspect $proposal and $diagnostics. ncisources.spec was not replaced." >& /dev/stderr
    exit 1
endif
/bin/cp -p "$proposal" ncisources.spec.guessed
if ($status != 0) then
    echo "Could not save the complete guessed plan; inspect $proposal and $diagnostics. ncisources.spec was not replaced." >& /dev/stderr
    exit 1
endif
/bin/mv -f "$proposal" ncisources.spec
if ($status != 0) then
    echo "Could not publish the complete guessed plan; inspect $proposal and $diagnostics." >& /dev/stderr
    exit 1
endif
