#!/usr/bin/perl
#
# File:    create_vsab_dirs.pl
# Author:  Tim Kao (1/2007)
#
# REMARKS: This script creates the necessary directory structure for inversion
#			and insertion.
#
# CHANGES  9/10/2007 TK (1-FQ6VN): Created on this date.

BEGIN
{
	unshift @INC, "$ENV{ENV_HOME}/bin";
	require "env.pl";
	unshift @INC, "$ENV{INV_HOME_OLD}/lib";
}

#
# Set variables
#
$ENV{"LANG"}       = "en_US.UTF-8";
$ENV{"LC_COLLATE"} = "C";

#
# Parse arguments
#
while (@ARGV)
{
	$arg = shift(@ARGV);
	push( @ARGS, $arg ) && next unless $arg =~ /^-/;

	if ( $arg eq "-version" )
	{
		$print_version = "version";
	} elsif ( $arg eq "-v" )
	{
		$print_version = "v";
	} elsif ( $arg eq "-help" || $arg eq "--help" )
	{
		$print_help = 1;
	} else
	{
		$print_help = 1;
	}
}

if ( scalar(@ARGS) == 1 )
{
	($vsab) = @ARGS;
} else
{
	$print_help = 1;
}

#
# Print Help/Version info, exit
#
&PrintHelp                    && exit(0) if $print_help;
&PrintVersion($print_version) && exit(0) if $print_version;

#
# Program logic
#
use Archives;

print "-------------------------------------------------------\n";
print "Starting ...", scalar(localtime), "\n";
print "VSAB:              $vsab\n";
print "-------------------------------------------------------\n";

&Archives::setVSAB($vsab);
&Archives::setCurrentPath("$ENV{SRC_ROOT}");

&Archives::createInversionDir();

print qq{-------------------------------------------------
Finished ... }, scalar(localtime), qq{
-------------------------------------------------
};
exit 0;

####### Local Procedures #######

sub PrintVersion
{
	my ($type) = @_;
	print "No version info\n";
	return 1;
}

sub PrintUsage
{

	print qq{ This script has the following usage:
 Usage: create_vsab_dirs.pl <vsab>
    };
}

sub PrintHelp
{
	&PrintUsage;
	print qq{
  The following directory structure is created for inversion and insertion:
	$ENV{SRC_ROOT}/vsab
						bin
						cxt
						etc
						orig/source_provider
						src
						tmp
						insert
};
	&PrintVersion("version");
	return 1;
}


