#
# This script takes an env.prop file and
# sets the calling shell's environment
#
# To use
# $ . $ENV_HOME/bin/env.sh
#
if [ ! -n "$ENV_FILE" ]; then
   echo '$ENV_FILE must be set';
   exit 1;
fi

for f in `grep = $ENV_FILE | grep -v '^#'` 
do
  var=`echo $f | sed 's/=.*//'`;
  val=`echo $f | sed 's/.*=//'`;
  eval "$var=`echo $val`";
  export $var;
  #eval 'echo $var $'$var;
done
