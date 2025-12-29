#!/usr/bin/perl
#
unshift(@INC,".");
use lib "$ENV{INV_HOME}/lib";
use lib "$ENV{INV_HOME}/bin";
use lib ".";
use strict 'vars';
use strict 'subs';

use List::Util qw(min max);

use Getopt::Std;
use NLMConfig;
use Logger;
use SrcQa;


my %options=();
getopts("hc:w:i:o:", \%options);


if (defined $options{h}) {
  print "Usage: srcQa.pl -ciowh\n";
  print "This method runs quality assurance checks on the output src files\n";
  print "\t-c - config file name\n";
  print "\t-i - input directory where .src files are\n";
  print "\t-o - output report file to store resutls\n";
  print "\t-w - which files to do QA on. uses the following bit flags.\n";
  print "\t\t 1 - atoms\n";
  print "\t\t 2 - attributes\n";
  print "\t\t 4 - merges\n";
  print "\t\t 8 - relationships\n";
  print "\t\t 16 - contexts\n";
  print "\t-h - prints this help message.\n";
}


our ($Cfg, $Log, $cfgFile) = ('', '');
our($max_srcid,$min_srcid,$maxsaid, $minsaid);
our %srcids = ();
our @IF = ();
our %codestring = ();

our %rpthash = ();
our %rptrelhash = ();
our %styhash = ();
our %srcids = ();
our %relas=();
our %invrelas=();

print "INV_HOME is $ENV{INV_HOME}\n";
if (!defined $options{c}) {
  print "Must supply a valid config file as -c option.\n";
  exit;
}
$cfgFile = $options{c};

my $libDir = "$ENV{INV_HOME}/lib";
print "libDir: $libDir\ncfgDir: $cfgFile\n";

# create the config object
$Cfg = new NLMConfig($cfgFile);

# create the log object.
my $vsab = $Cfg->getEle('VSAB', 'NONE');
my $lmode = $Cfg->getEle('LogMode', 'Append');
my $lLevel = $Cfg->getEle('LogLvl', 'INFO');
my $classfile = $Cfg->getEle('File.Atom');
my $attfile = $Cfg->getEle('File.Attribute');
my $mergefile = $Cfg->getEle('File.Merge');
my $relfile = $Cfg->getEle('File.Relation');
my $docfile = $Cfg->getEle('File.Doc');

my $outclass = $Cfg->getEle('File.ForClass'); 
my $outattr = $Cfg->getEle('File.ForAttr');

my @tt = split(/\//, $cfgFile);
my $ttLn = @tt;
if ($ttLn > 1) {
	splice(@tt, $ttLn-1, 1);
	my $ttDir = join("/", @tt);
	$Log = new Logger("$ttDir/qa/Qa_${vsab}.log", $lmode, $lLevel);
	#print "log dir: $ttDir/qa/\n";
} else {
	$Log = new Logger("qa/Qa_${vsab}.log", $lmode, $lLevel);
	#print "log dir: qa/\n";
}

SrcQa->init(\$Log, \$Cfg);

# Obtain from api_metadata.sh script
my $max_srcid = `$ENV{INV_HOME}/bin/api_metadata.sh max_src_atom_id --vsab $vsab --quiet`;
chomp($max_srcid);
my $min_srcid = `$ENV{INV_HOME}/bin/api_metadata.sh min_src_atom_id --vsab $vsab --quiet`;
chomp($min_srcid);

open (IN, "$classfile")
                or die "no input File.Atom file.\n";
my $i = 1;

while (<IN>){
   chomp;
($IF[1],$IF[2],$IF[3],$IF[4],$IF[5],$IF[6],$IF[7],$IF[8],$IF[9],$IF[10],$IF[11],$IF[12],$IF[13],$IF[14],$IF[15]) = split(/\|/);
$srcids{"$IF[1]"}++;
push(@{$codestring{"$IF[4]|$IF[8]"}}, $IF[1]);

if ($IF[3] eq "SRC/RPT"){
   my $I1 = $i++;
   $rpthash{"$I1|V-MTH"}++;
    }
}
close (IN);
#--------------------------------------------
#open mergefacts file and collect id1 and id2

open (IN1, "$mergefile")
                    or die "no input File.Merge file.\n";
while (<IN1>){
chomp;
($IF[1],$IF[2],$IF[3],$IF[4],$IF[5],$IF[6],$IF[7],$IF[8],$IF[9],$IF[10],$IF[11],$IF[12]) = split(/\|/);
#$mergeid1{$IF[1]}++;
#$mergeid2{$IF[3]}++;

}
close (IN1);

#----------------------------------------------
#open relations
open (IN2, "$relfile")
                    or die "no input File.Relation File.\n";

my $j = 1;

while (<IN2>){
   chomp;

($IF[1],$IF[2],$IF[3],$IF[4],$IF[5],$IF[6],$IF[7],$IF[8],$IF[9],$IF[10],$IF[11],$IF[12],$IF[13],$IF[14],$IF[15],$IF[16],$IF[17],$IF[18]) = split(/\|/);

   if ($IF[3] eq "V-MTH"){
     my $I2 = $j++;
     $rptrelhash{"$I2|$IF[3]"}++;
     }
}
close (IN2);

#------------------------------------------------
#open attributes
open (IN3, "$attfile")
                    or die "no input File.attribute File.\n";
my $k = 1;

while (<IN3>){
   chomp;

($IF[1],$IF[2],$IF[3],$IF[4],$IF[5],$IF[6],$IF[7],$IF[8],$IF[9],$IF[10],$IF[11],$IF[12],$IF[13],$IF[14]) = split(/\|/);

   if (($IF[4] eq "SEMANTIC_TYPE") && ($IF[5] eq "Intellectual Product")){
     my $I3 = $k++;
     $styhash{"$I3|V-MTH"}++;
     }
}
close (IN3);

#----------------------------------------------------
#open MRDOC.RRF file
open (IN4, "$docfile")
                   or die "no input File.doc File.\n";

while (<IN4>){
chomp;
($IF[1], $IF[2], $IF[3], $IF[4]) = split(/\|/);
      if ($IF[1] eq 'RELA' && $IF[3] eq 'rela_inverse'){
           $relas{$IF[2]}++;
           $invrelas{$IF[4]}++;
           }
  }
close (IN4);
#-------------------------------------------------
#check if the inverse relas are present in the MRDOC.RRF file
foreach my $relakey(keys %invrelas){
             if (!defined($relas{$relakey})){
          print "WARNING--Inverse Rela not present in MRDOC.RRF : $relakey.\n";
             }
           }

  
#-----------------------------------------------------
#check if V-MTH exists for each rpt atom
   foreach my $rptkey(keys %rpthash){
     if (!defined($rptrelhash{$rptkey})){
        print "RPT relation is missing for one of the sources please check the realtionships.src file\n";
        print "exiting QA!\n";
        exit;
         }
     }

#check if STY exists for RPT atom
    foreach my $stykey(keys %rpthash){
           if (!defined ($styhash{$stykey})){
        print "STY attribute is missing for rpt atoms please check the attributes.src file\n";
        print "exiting QA!\n";
        exit;
          }
       }

#-----------------------------------------------------
     $minsaid = min keys %srcids;
     # print "classes minid: $minsaid";

     $maxsaid = (sort {$b <=> $a} keys %srcids)[0];
     #print "classes maxid: $maxsaid";



        #5 check if the min src_atom id of classes is the same as that of DB
     if ($minsaid ne $min_srcid){
           print "Min class said: $minsaid is not equal to the DB min said :$min_srcid\n";
           print "Please check the src_atom_id range, exiting QA now\n";
        #exit;
         }

    #6 check if the max src_atomid of classes is less than that of the DB
     if ($maxsaid > $max_srcid){
          print "Max class said: $maxsaid is greater than Max DB said: $max_srcid\n";
          print "Please check the src_atom_id range, exiting QA now\n";
         #     exit;
            }

#----------------------------------------------

print "CHECKING forbidden CHARACTERS\n";

system('$INV_HOME/bin/show-forbidden.pl ../src/classes_atoms.src > ../etc/qa/Forbidden_classes.txt');

print "DONE CHECKING FOR FORBIDDEN CHARACTERS IN CLASSES_ATOMS.SRC FILE. PLEASE REFER TO forbidden_classes.txt FOR ADDITIONAL INFO\n";

system('$INV_HOME/bin/show-forbidden.pl ../src/attributes.src > ../etc/qa/Forbidden_attr.txt');

print "DONE CHECKING FOR FORBIDDEN CHARACTERS IN ATTRIBUTES.SRC FILE. PLEASE REFER TO forbidden_attributes.txt FOR ADDITIONAL INFO\n";

#------------------------------------------------


our $qa = new SrcQa();

# now set any command line parms overriding the ones in cfg file.
$qa->setInDir($options{i}) if (defined $options{i});
$qa->setReportFile($options{o}) if (defined $options{o});
$qa->setWhich($options{w}) if (defined $options{w});
$qa->process();
print "Done QA checks\n";


