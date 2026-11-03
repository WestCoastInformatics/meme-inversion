#!/usr/bin/perl
#
# Generate 3 MMSYS config files for the MSH, SNOMEDCT (or SCTSPA if SNOMEDCT
# isn't being updated) and "other" subsets.

open(MRSAB, "Meta/MRSAB.RRF");
while (<MRSAB>) {
    ($VCUI, $RCUI, $VSAB, $RSAB, $SON, $SF) = split(/[|\n]/);
    $SF{$RSAB} = $SF;
}

# skip the following since we no longer do a SNOMED "part2"
#open(SCTSPEC, "grep '^SNOMEDCT' ncisources.spec |");
#while (<SCTSPEC>) {
#    ($RSAB, $VSAB, $TYPE, $NOTES) = split(/[|\n]/);
#    $part2 = ($TYPE eq 'KEEP') ? 'SCTSPA' : 'SNOMEDCT';
#}

# this is still used to exclude SNOMEDCT from the "REST" set
$part2 = 'SNOMEDCT_US';

open(SPEC, "ncisources.spec");
while (<SPEC>) {
    ($RSAB, $VSAB, $TYPE, $NOTES) = split(/[|\n]/);
    if ($NOTES =~ /^exclude termgroups: (.*)/) {
	$ttys = $1;
	foreach $tty (split(/, */, $ttys)) {
	    $excl .= "$RSAB|${tty};";
	}
    }
#    if ($RSAB !~ /^(MSH|$part2)$/ && $TYPE =~ /^(NEW|UPDATE|KEEP)$/) {
    if ($RSAB !~ /^($part2)$/ && $TYPE =~ /^(NEW|UPDATE|KEEP)$/) {
	$SF = $SF{$RSAB};
	$restkeep .= "$RSAB|${SF};";
    }
}
chop($excl);
chop($restkeep);

#foreach $part ('MSH', $part2, 'REST') {
foreach $part ('REST') {
    if ($part eq 'MSH') {
	open(OUT, ">ncimsh.prop");
    } elsif ($part eq 'REST') {
	open(OUT, ">ncirest.prop");
    } else {
	open(OUT, ">ncisct.prop");
    }
    open(TEMPL, "template.prop");
    while (<TEMPL>) {
	chomp;
	if (/active_filters=/) {
	    s/^(active_filters=.*)/$1;gov.nih.nlm.umls.mmsys.filter.SourceTermTypesFilter;gov.nih.nlm.umls.mmsys.filter.AttributesFilter/;
	    print OUT $_, "\n";
	    print OUT "gov.nih.nlm.umls.mmsys.filter.SourceTermTypesFilter.remove_selected_sabttys=true\n";
	    print OUT "gov.nih.nlm.umls.mmsys.filter.SourceTermTypesFilter.selected_sabttys=$excl\n";
	} elsif (/\.remove_selected_sources=true/) {
	    s/(\.remove_selected_sources)=.*/$1=false/;
	    print OUT $_, "\n";
	} elsif (/\.remove_mth_only=false/) {
	    s/(\.remove_mth_only)=.*/$1=true/;
	    print OUT $_, "\n";
	} elsif (/\.selected_sources=/) {
	    s/(\.selected_sources=).*$/$1/;
	    $keep = ($part eq 'REST') ? "${restkeep};SRC|SRC" : "$part|${part};SRC|SRC";
	    print OUT "$_$keep\n";
	} elsif (/\.versioned_output=false/) {
	    s/(\.versioned_output)=.*/$1=true/;
	    print OUT $_, "\n";
        # remove NH attributes
	} elsif (/\.selected_attribute_types=/) {
	    s/(\.selected_attribute_types=).*$/${1}MTH|NH/;
	    print OUT $_, "\n";
	} else {
	    print OUT $_, "\n";
	}
    }
    close(OUT);
}
