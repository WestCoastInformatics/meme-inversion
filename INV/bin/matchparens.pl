#!/usr/bin/perl


$lf = "(";
$rt = ")";

%count = ();

print "Found the following mismatches:\n";

while(<>){
  @x = split //;
  foreach $char (@x){
    $count{$char}++;
    #print "$char: $count{$char}\n";
   }
  if ($count{$lf} != $count{$rt}){
	if($count{$lf} eq '') {$count{$lf} = '0'}
	if($count{$rt} eq '') {$count{$rt} = '0'}
    print "line $.\t Left: $count{$lf}  Right: $count{$rt}\n";
	print "$_\n";
   }
  %count = ();
 }
print "\n";
