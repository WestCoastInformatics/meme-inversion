#!/usr/bin/perl

# 	Globally removes non-printable characters (excluding tabs, LF); prints
#	the line.

while (<>)
{
	$_ =~ s/[^\040-\176\n\t]//g;
	print $_;
}
