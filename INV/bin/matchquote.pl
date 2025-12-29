#!/usr/bin/perl


$z = "\"";

%count = ();

print "Found the following mismatches:\n";

while(<>){
  @x = split //;
  foreach $char (@x){
    $count{$char}++;
    #print "$char: $count{$char}\n";
   }
	if(($count{$z})&&($count{$z}%2)){
    print "$.\t$_\n";
   }
  %count = ();
 }
print "\n";
