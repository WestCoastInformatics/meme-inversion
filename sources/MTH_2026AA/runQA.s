#!/bin/tcsh -f

source bin/env.s
# fix wrong INV_HOME_OLD setting from env.s
setenv INV_HOME_OLD /local/content/MEME/MEME5/inv/INV_OLD

setenv PERL5LIB $INV_HOME_OLD/lib

# need INV_HOME set too since QA4_util.pm still gets files from $INV_HOME
setenv INV_HOME /local/content/MEME/INV_OLD

$INV_HOME_OLD/bin/QA4.pl . >& runQA.log
