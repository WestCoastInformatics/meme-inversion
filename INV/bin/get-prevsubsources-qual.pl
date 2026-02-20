#!/usr/bin/perl

my $out_dir = shift @ARGV;
$out_dir = "INV/tmp" unless $out_dir;
open (SOURCES, ">$out_dir/prevsubsources.tmp") or die "Cannot open $out_dir/prevsubsources.tmp: $!";

# reads the properties file
while (<>) {
	chomp;
	($cname,$pname,$pval,$qual)=split(/\|/);
	if ($pname eq "FULL_SYN"){
		$src = $tty = $src_code = '';

		# split the qualifier field on '\'
		@P = split(/\\/, $qual);

		# @P contains all fields in pairs
		# go through the array, jumping 2 elements instead of the std. 1
		for($i=0;$i<$#P;$i++,$i++){
			$qualifier = $P[$i];
			$value = $P[$i+1];

			# figure out what we've got
			# qualifiers aren't guaranteed to be in a predictable order
			SWITCH:{
				if($qualifier eq "Syn_Source"){$src = $value; last SWITCH}
				if($qualifier eq "Syn_Term_Type"){$tty = $value; last SWITCH}
				if($qualifier eq "Syn_Source_Code"){$src_code = $value; last SWITCH}

				# if we made this far, we don't know what this qualifier is
				print "Error: Unknown qualifier - $qualifier\n";
				print "$.:$_\n";
			}
		}
		$subsrc{$src}++;

		#$str = "$cname|$pname|$pval|Syn_Term_Type\\$tty\\Syn_Source\\$src";
		#if($src_code){
			$str .= "\\Syn_Source_Code\\$src_code";
		}
		#print "$str\n";
	}
foreach $src (sort(keys(%subsrc))){
	print SOURCES "$src\n";
	# print "$src\n";
}
