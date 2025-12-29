#!/usr/bin/perl

# changes
# 02/12/2013 NEO: allow multiple sources separated by "-=-=-" in the input file
# 06/28/2007 WAK (1-ELQTB): changes for subfields in MRSAB 
#

# use this script to convert the filled in template file created by
# dump_src_info.pl into a sources.src file
#
# this version expects sub fields for 
#	Content Contact
#	License Contact
#	Citation
#
# there should be a line preceeding the sub fields that starts with '***' and
# the end of the subfields should have a line that says '- end of <field>

# script to make sources.src from a template
# copy this file and fill in the 2nd field:
#  sources.src.template
# or use a sources.txt file dumped using $INV_HOME/bin/dump_src_info.pl

# usage: make.sources.src.s <filled-in-template> > sources.src
# e.g. make.sources.src.s sources.txt >sources.src

while (<>){
	chomp;
	$line++;
	next if (/^\#/);
    if (/^-=-=-$/) {
        print "\n";
        next;
    }
	($tag,$value,$desc)=split(/\|/);
	
	# sections that are for the sub-fields start with a line that
	# has a '*' at the beginning of the line
	if(/^\*/){
		while($_ = <>){
			$line++;

			# a line that starts with "- end of ..." ends the sub-field section
			last if($_ =~ /^- end of /);
			($tag,$value,$desc) = split(/\|/);
			$value =~ s/^\s*//;
			$value =~ s/\s*$//;
			print "$value;";
		}
		print "|";
	}
	else{print "$value|";}
}

print "\n";

