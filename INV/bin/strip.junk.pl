#!/usr/bin/perl

# 	Globally removes non-printable characters (excluding tabs, LF);
#	strips leading and trailing blanks; prints the line.
use integer;
use utf8;
binmode(STDOUT, ":utf8");


while (<>)
{
	#s/[^\040-\176\n\t]//g;
	s/\|[ \t]+/|/g;
	s/[ \t]+\|/|/g;
	s/^[ \t]+//;
	s/[ \t]+$//;
	print;
}
