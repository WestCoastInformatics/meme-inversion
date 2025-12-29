#!/usr/bin/perl 
use integer;

$ENV{"LANG"} = "en_US.UTF-8";
$ENV{"LC_COLLATE"} = "C";

# show_template_attribs.pl
# Tue Jun 21 10:42:32 PDT 2005 - WAK 
#
# 
while(<>){
	#print "$. ---\n";
	next if(/^#/);
	next if(/^\s*$/);
	($attrib,$val,$comment)=split(/\|/);
	#print "$. : $attrib\n";
	print "$attrib|$val\n";
}
