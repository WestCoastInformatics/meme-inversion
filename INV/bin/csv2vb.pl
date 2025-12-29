#!/usr/bin/perl

# Convert from csv (comma separated variable?) to vertical bar separated fields
# There must be a better way!

# suresh@nlm.nih.gov 7/12

while (<>) {
    chomp;

    $_=~s/
//;
    $rec = $_;
    while ($rec) {
	if ($rec eq ",") {
	    push @fields, "";
	    push @fields, "";
	    last;
	} elsif ($rec =~ /^,/) {
	    push @fields, "";
	    $rec =~ s/^,//;
	} elsif ($rec =~ /^\"/) {
	    $rec =~ /^\"([^\"]*)\"(.*)/;
	    $fields = $1;
	    $rec = $2;
	    push @fields, $1;
	    $rec =~ s/^,//;
	} else {
	    if ($rec =~ /^([^,]*),(.*)/) {
		$field = $1;
		$rec = $2;
	    } else {
		$field = $rec;
		$rec = "";
	    }
	    push @fields, $field;
	}
    }
    print join('|', @fields), "\n";
    @fields = ();
}
