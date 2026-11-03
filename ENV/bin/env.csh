#
# This script takes an env.prop file and
# sets the calling shell's environment
#
# To use
# % source $ENV_HOME/bin/env.csh
#
if ($?ENV_FILE != 1) then
   echo '$ENV_FILE must be set'
   exit 1
endif
foreach f (`grep = $ENV_FILE | grep -v '^#'`)
  set var = `echo $f | sed 's/=.*//'`
  set val = `echo $f | sed 's/.*=//'`
  eval setenv $var `echo $val`
end
