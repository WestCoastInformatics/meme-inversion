#!/usr/bin/perl

#$curfiles="0606E";
$curfiles = shift(@ARGV);
$data = shift(@ARGV);

print STDERR "Files to: $curfiles\n";
print STDERR "Data from: $data\n";


open (DUPPT, "> $curfiles/duppts.tmp");
open (DUPPREF, "> $curfiles/duppref.tmp");
open (NOFS, ">$curfiles/nofullsyn.tmp");
open (NOPN, ">$curfiles/noprefname.tmp");
open (MISMATCH, "> $curfiles/mismatch.tmp");
open (NAMES, "> $curfiles/syns.tmp");
open (SOURCES, "> $curfiles/subsources.tmp");

# reads the properties file

open(DATA, "$data") or die "Can't open file '$data', $!";
while (<DATA>) 
	{
	chomp;
	@fields=split(/\|/);
	($cname,$prop,$propval)=split(/\|/);
	
	if (!$hash{$cname})
		{
		$hash{$cname}=$cname;
		push (@cnames, $cname);
		}
		
	if ($prop eq "FULL_SYN") {
		#($null,$name,$null2,$group,$null3,$src,$null4,$src_code)=split(/<.*?>/,$propval);
		($cname,$name,$propval,$qual)=split(/\|/);
		$name = $propval;
		$src = $group = $src_code = '';
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
			if($qualifier eq "Syn_Term_Type"){$group = $value; last SWITCH}
			if($qualifier eq "Syn_Source_Code"){$src_code = $value; last SWITCH}
			# if we made this far, we don't know what this qualifier is
			print STDERR "Error: Unknown qualifier - $qualifier\n";
			print "$.:$_\n";
		}
		}
		print SOURCES "$src\n";

		print NAMES "$cname|$name\@$group\@$src\@$src_code\n";
		#print "$cname|$name\@$group\@$src\@$src_code\n";

		#2/2/07 per L.Roth, AQ and HD considered equivalent to PT
		if (($group eq "PT" || $group eq "AQ" || $group eq "HD") && $src eq "NCI"){     
			$fullsyn{$cname}=$name;
		}

		if ($group eq "PT" && $src eq "NCI")
			{
			$fullsynpt{$cname}=$name;
			if ($haspt{$cname})
				{
				push (@dup_pts, $cname);
				}
			if (!$haspt{$cname})
				{
				$haspt{$cname}=$name;
				}
			}
		}
	if ($prop eq "Preferred_Name")
		{
		# some Pref Name records have qualifiers
		# this is probably an error but doesn't seem to hurt
		# anything, but it does make this test fail
		#$pname{$cname}=$propval unless ($#fields!=2);
		$pname{$cname}=$propval;
		if ($hasprefname{$cname})
				{
				push (@dup_prefs, $cname);
				}
			if (!$hasprefname{$cname})
				{
				$hasprefname{$cname}=$propval;
				}
		}
	}	# end of while(<DATA>)
close DATA;

foreach $x (@dup_pts)
	{
	print DUPPT "$x\n";
	}

foreach $x (@dup_prefs)
	{
	print DUPPREF "$x\n";
	}

foreach $x (@cnames)
	{
	if (!$fullsyn{$x})
	#if (!$fullsynpt{$x})
		{
		print NOFS "$x\n";
		}
	if (!$pname{$x})
		{
		print NOPN "$x\n";
		}
	if ($fullsynpt{$x} ne $pname{$x} && $fullsynpt{$x} ne "")
		{
		print MISMATCH "CONCEPT: $x\nFULLSYN: $fullsynpt{$x}\nPreferred_Name: $pname{$x}\n\n\n";

		}
	}
