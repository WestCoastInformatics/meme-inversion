#!/site/bin/perl

#1/6/05 SLQ
#compare the 'sty_term_ids' file with the 'all.terms' file and output
#those atoms with no sty 

open(IN,"<../tmp/sty_term_ids.said.tmp") or die "can't open IN, $!";
open(OUT,">../tmp/no_sty_term_ids") or die "can't open OUT, $!";

while(<IN>){
	chomp;
	$hash{$_}++;
}
close(IN);

open(ALL,"<../tmp/all.terms.needing.sty.sort.tmp") or die "can't open IN, $!";

while(<ALL>){
	chomp;
	if($hash{$_}){
	}

	else{
		print OUT "$_\n";
	}
}
close(ALL);

