#!/bin/csh -f
#
#
#          This script should be run from the directory
#          containing the SRC files.

###################################################################
#
# Configuration
#
###################################################################
set mode=real
set db=memestg

set old_source="NCI_2017_04D"
set new_source="NCI_2017_06D"
set authority=$new_source
set work_id=0

#
#Set email flags
#
set subject_flag='-subject="Insertion Error - '$new_source'"'
set to=taco@txt.att.net
set from=wongjf@mail.nih.gov
if ($?to == 1) then
   set to_from_flags="-to $to -from $from"
else
   set to_from_flags=
endif

if ($?MEME_HOME == 0) then
    echo '$MEME_HOME must be set'
    exit 1
endif

if ($?NLS == 0) then
    echo '$NLS must be set'
    exit 1
endif

if ($?ORACLE_HOME == 0) then
    echo '$ORACLE_HOME must be set'
    exit 1
endif

if ($#argv == 0) then
    echo "Usage: $0 <database>"
    echo "Usage: $0 [-t] <test database> <editing database>"
    exit 1
else if ($#argv == 1) then
    set mode=run
    set db=$1
    set real_db=$1
    set host=`$MIDSVCS_HOME/bin/midsvcs.pl -s insertion-meme-server-host`
    set port=`$MIDSVCS_HOME/bin/midsvcs.pl -s insertion-meme-server-port`
    set qual=real
else if ($#argv == 3 && "$argv[1]" == "-t") then
    set mode=test
    set real_db=$3
    set db=$2
    set host=`$MIDSVCS_HOME/bin/midsvcs.pl -s test-insertion-meme-server-host`
    set port=`$MIDSVCS_HOME/bin/midsvcs.pl -s test-insertion-meme-server-port`
    set qual=test
else
    echo "Usage: $0 <database>"
    echo "Usage: $0 [-t] <test database> <editing database>"
    exit 1
endif 

set ct=`ls |fgrep -c .src`
if ($ct == 0) then
    echo "You must run this script from the directory containing the src files"
    exit 1
endif

if ((! -e sources.src) || (! -e termgroups.src)) then
    echo "The files sources.src and termgroups.src must exist"
    exit 1
endif

#
# Check $old/$new_source against sources.src
#
set chk_old_source = ` grep '^NCI_' sources.src | cut -d\| -f 2`
if ($old_source != $chk_old_source) then
            echo "Improperly set old_source $old_source"
            exit 1
endif
set chk_new_source = `grep '^NCI_' sources.src | cut -d\| -f 1`
if ($new_source != $chk_new_source) then
            echo "Improperly set new_source $new_source"
            exit 1
endif

###################################################################
# Get username/password and work_id
###################################################################
set user=`$MIDSVCS_HOME/bin/get-oracle-pwd.pl -d $db`
$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >! /tmp/work_id
    set feedback off
    set serveroutput on size 100000
    exec dbms_output.put_line ( -
         meme_utility.new_work( -
	      authority => '$new_source', -
              type => 'INSERTION', -
	      description => 'Source insertion of $new_source'));
EOF
set work_id=`cat /tmp/work_id`
\rm -f /tmp/work_id

#################################################################
# 
#  Start RECIPE
#
#################################################################

set la_status = `$MEME_HOME/bin/dump_table.pl -u $user -d $db -q "select status from system_status where system='log_actions'"`
set recipe_start_t=`perl -e 'print time'`
echo "--------------------------------------------------------------"
echo "Starting $0 ... `/bin/date`"
echo "--------------------------------------------------------------"
echo "MEME_HOME:  $MEME_HOME"
echo "mode:       $mode"
echo "db:         $db"
echo "authority:  $authority"
echo "new_source: $new_source"
echo "old_source: $old_source"
echo "work_id:    $work_id"
echo "host:       $host"
echo "port:       $port"
echo "la_status:  $la_status"
echo "time:       $recipe_start_t"
echo ""

#
# Indicate start of insertion
#
$ORACLE_HOME/bin/sqlplus -s $user@$real_db <<EOF > /dev/null
 UPDATE system_status SET status='OFF' WHERE system='log_actions';
EOF

foreach sab (`/bin/cut -d\| -f 1 sources.src`)
   $ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF > /dev/null
     UPDATE sims_info SET ${qual}_insertion_start = sysdate
     WHERE source = '$sab';
EOF
end

#################################################################
# <h2>Load Section</h2>
#################################################################

#
# Load Step (Part 1)
#
echo "    Run Load Step Part 1 (load_section.1.log) ... `/bin/date`"

$MEME_HOME/bin/load_section.csh $authority "$old_source" $new_source "NA" $db $work_id 1 >&! load_section.1.log

if ($status != 0) then 
    echo "Error running load section, see load_section.1.log"
    exit 1
endif

#################################################################
# Pre-insert merging
#################################################################

#
# Precomputed set NCI-SRC
#
echo "    Perform precomputed set 'NCI-SRC' ...`/bin/date`"

set start_t=`perl -e 'print time'`
$MEME_HOME/bin/load_src.csh $db mergefacts.src >! load_src.log
if ($status != 0) then 
    echo "Error loading mergefacts"
    exit 1
endif
$MEME_HOME/bin/log_operation.pl $db $authority Merging "Load mergefacts.src for NCI-SRC" $work_id 0 $start_t >> /dev/null

$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    WHENEVER SQLERROR EXIT -1
 
    exec MEME_SOURCE_PROCESSING.prepare_src_mergefacts( -
	authority => '$authority', -
	merge_set => 'NCI-SRC', -
	work_id => $work_id);

    exec MEME_SOURCE_PROCESSING.load_facts ( -
        merge_set => 'NCI-SRC', -
        integrity_vector => '', -
        change_status => 'N', -
        make_demotion => 'Y', -
        authority => '$authority', -
        work_id => $work_id);


    -- Replacement merges
    exec MEME_SOURCE_PROCESSING.replacement_merges ( -
        merge_set => 'NCI-SRC', -
        normalization_flag => 1, -
	ambig_flag => 0, -
        authority => '$authority', -
        work_id => $work_id);

    DELETE FROM mom_merge_facts WHERE status in ('P','F','R');
    exec MEME_SOURCE_PROCESSING.move_processed_facts ( -
        authority => '$authority', -
        work_id => $work_id);

EOF

if ($status != 0) then
    echo "Error running merge set"
    cat /tmp/t.$$.log
    exit 1
endif

#
# Precomputed set NCI-SY
#
echo "    Perform precomputed set 'NCI-SY' ...`/bin/date`"

set start_t=`perl -e 'print time'`
$MEME_HOME/bin/load_src.csh $db mergefacts.src >! load_src.log
if ($status != 0) then 
    echo "Error loading mergefacts"
    exit 1
endif
$MEME_HOME/bin/log_operation.pl $db $authority Merging "Load mergefacts.src for NCI-SY" $work_id 0 $start_t >> /dev/null

$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    WHENEVER SQLERROR EXIT -1
 
    exec MEME_SOURCE_PROCESSING.prepare_src_mergefacts( -
	authority => '$authority', -
	merge_set => 'NCI-SY', -
	work_id => $work_id);

    exec MEME_SOURCE_PROCESSING.load_facts ( -
        merge_set => 'NCI-SY', -
        integrity_vector => '', -
        change_status => 'N', -
        make_demotion => 'Y', -
        authority => '$authority', -
        work_id => $work_id);


    -- Replacement merges
    exec MEME_SOURCE_PROCESSING.replacement_merges ( -
        merge_set => 'NCI-SY', -
        normalization_flag => 1, -
	ambig_flag => 0, -
        authority => '$authority', -
        work_id => $work_id);

    DELETE FROM mom_merge_facts WHERE status in ('P','F','R');
    exec MEME_SOURCE_PROCESSING.move_processed_facts ( -
        authority => '$authority', -
        work_id => $work_id);

EOF

if ($status != 0) then
    echo "Error running merge set"
    cat /tmp/t.$$.log
    exit 1
endif

#
# Generated set NCI-REPL
# Merge all new termgroups with all old termgroups
#
echo "    Perform generated set 'NCI-REPL' ...`/bin/date`"

$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    WHENEVER SQLERROR EXIT -1
 
    exec MEME_UTILITY.drop_it('table','t1');
    exec MEME_UTILITY.drop_it('table','t2');
    CREATE TABLE t1 (termgroup VARCHAR2(40) NOT NULL);
    CREATE TABLE t2 (termgroup VARCHAR2(40) NOT NULL);
    insert into t1 select termgroup from termgroup_rank
    where termgroup like '$new_source%/%';
    insert into t2 select termgroup from termgroup_rank
    where termgroup like '$old_source%/%';

    exec MEME_SOURCE_PROCESSING.generate_facts ( -
	termgroup_table_1 => 't1', -
	termgroup_table_2 => 't2', -
	merge_set => 'NCI-REPL', -
	string_parameter => 'BOTH', -
	code_parameter => 'EXACT', -
	source_aui_parameter => 'NONE', source_cui_parameter => 'NONE', -
	source_dui_parameter => 'NONE', tty_parameter => 'NONE', -
	table_name => 'source_classes_atoms', -
	source => '$new_source', -
	authority => '$authority', -
	work_id => $work_id );

    -- Use exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_1 => 'EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_2 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-REPL', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Use norm exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_1 => 'NORM_EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_2 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-REPL', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Use exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_2 => 'EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_1 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-REPL', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Use norm exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_2 => 'NORM_EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_1 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-REPL', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Ad hoc filter
    delete from mom_candidate_facts where atom_id_2 in
    (select b.atom_id from classes a, classes b, string_ui c
     where a.concept_id = b.concept_id
       and b.source in (select current_name from source_version where source='SNOMEDCT_US')
       and b.sui = c.sui
       and c.string_pre like 'Entire%' and c.string like 'Entire%(body structure)');

    -- Ad hoc filter
    delete from mom_candidate_facts where atom_id_1 in
      (select atom_id from classes where concept_id in
        (select a.concept_id from classes a, atoms b
         where a.source='$new_source' and a.atom_id = b.atom_id
         and lower(b.atom_name) like '%allele%'));

    -- Replacement merges in both directions
    exec MEME_SOURCE_PROCESSING.replacement_merges ( -
        merge_set => 'NCI-REPL', -
        normalization_flag => 1, -
	ambig_flag => 1, -
        authority => '$authority', -
        work_id => $work_id);

    DELETE FROM mom_merge_facts WHERE status in ('P','F','R');
    exec MEME_SOURCE_PROCESSING.move_processed_facts ( -
        authority => '$authority', -
        work_id => $work_id);

EOF
if ($status != 0) then
    echo "Error during pre-insert merge operation"
    cat /tmp/t.$$.log
    exit 1
endif

#
# Load Step (Part 2)
#
echo "    Run Load Step Part 2 (load_section.2.log) ... `/bin/date`"

$MEME_HOME/bin/load_section.csh $authority "$old_source" $new_source "NA" $db $work_id 2 >&! load_section.2.log

if ($status != 0) then 
    echo "Error running load section, see load_section.2.log"
    exit 1
endif


#
# Refresh cache
#
echo "    Refreshing Caches ... `/bin/date`"
$MEME_HOME/bin/admin.pl -s refresh_db -d $db -host $host -port $port >&! /tmp/t.$$.log
if ($status != 0) then
    echo "    Error refreshing db"
    cat /tmp/t.$$.log
    exit 1
endif


#################################################################
# <h2>Update Merge Section</h2>
#################################################################

#
# Precomputed set NCI-SRC
#
echo "    Perform precomputed set 'NCI-SRC' ...`/bin/date`"

set start_t=`perl -e 'print time'`
$MEME_HOME/bin/load_src.csh $db mergefacts.src >! load_src.log
if ($status != 0) then 
    echo "Error loading mergefacts"
    exit 1
endif
$MEME_HOME/bin/log_operation.pl $db $authority Merging "Load mergefacts.src for NCI-SRC" $work_id 0 $start_t >> /dev/null

$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    WHENEVER SQLERROR EXIT -1
 
    exec MEME_SOURCE_PROCESSING.prepare_src_mergefacts( -
	authority => '$authority', -
	merge_set => 'NCI-SRC', -
	work_id => $work_id);

    exec MEME_SOURCE_PROCESSING.load_facts ( -
        merge_set => 'NCI-SRC', -
        integrity_vector => '', -
        change_status => 'N', -
        make_demotion => 'Y', -
        authority => '$authority', -
        work_id => $work_id);


EOF
if ($status != 0) then
    echo "Error loading merge set"
    cat /tmp/t.$$.log
    exit 1
endif

set start_t=`perl -e 'print time'`
$MEME_HOME/bin/merge.pl -host=$host -port=$port NCI-SRC $authority $work_id $db >&! merge.nci-src.log
if ($status != 0) then
    echo "Error merging"
    exit 1
endif
$MEME_HOME/bin/log_operation.pl $db $authority Merging "Call merge.pl for NCI-SRC" $work_id 0 $start_t >> /dev/null

#
# Move Processed Facts
#
$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    WHENEVER SQLERROR EXIT -1
 
    DELETE FROM mom_merge_facts WHERE status in ('P','F');
    exec MEME_SOURCE_PROCESSING.move_processed_facts ( -
        authority => '$authority', -
        work_id => $work_id);

EOF
if ($status != 0) then
    echo "Error moving facts"
    cat /tmp/t.$$.log
    exit 1
endif


#
# Precomputed set NCI-SY
#
echo "    Perform precomputed set 'NCI-SY' ...`/bin/date`"

set start_t=`perl -e 'print time'`
$MEME_HOME/bin/load_src.csh $db mergefacts.src >! load_src.log
if ($status != 0) then 
    echo "Error loading mergefacts"
    exit 1
endif
$MEME_HOME/bin/log_operation.pl $db $authority Merging "Load mergefacts.src for NCI-SY" $work_id 0 $start_t >> /dev/null

$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    WHENEVER SQLERROR EXIT -1
 
    exec MEME_SOURCE_PROCESSING.prepare_src_mergefacts( -
	authority => '$authority', -
	merge_set => 'NCI-SY', -
	work_id => $work_id);

    exec MEME_SOURCE_PROCESSING.load_facts ( -
        merge_set => 'NCI-SY', -
        integrity_vector => '', -
        change_status => 'N', -
        make_demotion => 'Y', -
        authority => '$authority', -
        work_id => $work_id);

    -- Set All Checks
    update mom_merge_facts
    set integrity_vector = (select integrity_Vector from
    ic_applications where application='MERGE_O_MATIC');

EOF
if ($status != 0) then
    echo "Error loading merge set"
    cat /tmp/t.$$.log
    exit 1
endif

set start_t=`perl -e 'print time'`
$MEME_HOME/bin/merge.pl -host=$host -port=$port NCI-SY $authority $work_id $db >&! merge.nci-sy.log
if ($status != 0) then
    echo "Error merging"
    exit 1
endif
$MEME_HOME/bin/log_operation.pl $db $authority Merging "Call merge.pl for NCI-SY" $work_id 0 $start_t >> /dev/null

#
# Move Processed Facts
#
$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    WHENEVER SQLERROR EXIT -1
 
    DELETE FROM mom_merge_facts WHERE status in ('P','F');
    exec MEME_SOURCE_PROCESSING.move_processed_facts ( -
        authority => '$authority', -
        work_id => $work_id);

EOF
if ($status != 0) then
    echo "Error moving facts"
    cat /tmp/t.$$.log
    exit 1
endif

#
# Unary Integrity Check
#
$ORACLE_HOME/bin/sqlplus -s $user@$db << EOF >&! /tmp/t.$$.log
    WHENEVER SQLERROR EXIT -1
    set feedback off

    INSERT INTO ic_single
    (ic_name, negation, type, value)
    VALUES
     ('MGV_SCUI','N','SOURCE','$new_source');

EOF
if ($status != 0) then
    echo "Error handling binary check"
    cat /tmp/t.$$.log
    exit 1
endif

#
# Refresh cache
#
echo "    Refreshing Caches ... `/bin/date`"
$MEME_HOME/bin/admin.pl -s refresh_db -d $db -host $host -port $port >&! /tmp/t.$$.log
if ($status != 0) then
    echo "    Error refreshing db"
    cat /tmp/t.$$.log
    exit 1
endif



#
# Generated set NCI-REPL
# Merge all new termgroups with all old termgroups
#
echo "    Perform generated set 'NCI-REPL' ...`/bin/date`"

$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    WHENEVER SQLERROR EXIT -1
 
    exec MEME_UTILITY.drop_it('table','t1');
    exec MEME_UTILITY.drop_it('table','t2');
    CREATE TABLE t1 (termgroup VARCHAR2(40) NOT NULL);
    CREATE TABLE t2 (termgroup VARCHAR2(40) NOT NULL);
    insert into t1 select termgroup from termgroup_rank
    where termgroup like '$new_source%/%';
    insert into t2 select termgroup from termgroup_rank
    where termgroup like '$old_source%/%';

    exec MEME_SOURCE_PROCESSING.generate_facts ( -
	termgroup_table_1 => 't1', -
	termgroup_table_2 => 't2', -
	merge_set => 'NCI-REPL', -
	string_parameter => 'BOTH', -
	code_parameter => 'EXACT', -
	source_aui_parameter => 'NONE', source_cui_parameter => 'NONE', -
	source_dui_parameter => 'NONE', tty_parameter => 'NONE', -
	table_name => 'classes', -
	source => '$new_source', -
	authority => '$authority', -
	work_id => $work_id );

    -- Use exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_1 => 'EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_2 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-REPL', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Use norm exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_1 => 'NORM_EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_2 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-REPL', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Use exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_2 => 'EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_1 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-REPL', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Use norm exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_2 => 'NORM_EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_1 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-REPL', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Ad hoc filter
    delete from mom_candidate_facts where atom_id_2 in
    (select b.atom_id from classes a, classes b, string_ui c
     where a.concept_id = b.concept_id
       and b.source in (select current_name from source_version where source='SNOMEDCT_US')
       and b.sui = c.sui
       and c.string_pre like 'Entire%' and c.string like 'Entire%(body structure)');

    -- Ad hoc filter
    delete from mom_candidate_facts where atom_id_1 in
      (select atom_id from classes where concept_id in
        (select a.concept_id from classes a, atoms b
         where a.source='$new_source' and a.atom_id = b.atom_id
         and lower(b.atom_name) like '%allele%'));

    exec MEME_SOURCE_PROCESSING.load_facts ( -
        merge_set => 'NCI-REPL', -
        integrity_vector => '', -
        change_status => 'Y', -
        make_demotion => 'Y', -
        authority => '$authority', -
        work_id => $work_id);


    -- Set All Checks
    update mom_merge_facts
    set integrity_vector = (select integrity_Vector from
    ic_applications where application='MERGE_O_MATIC');

EOF
if ($status != 0) then
    echo "Error loading merge set"
    cat /tmp/t.$$.log
    exit 1
endif

set start_t=`perl -e 'print time'`
$MEME_HOME/bin/merge.pl -host=$host -port=$port NCI-REPL $authority $work_id $db >&! merge.nci-repl.log
if ($status != 0) then
    echo "Error merging"
    exit 1
endif
$MEME_HOME/bin/log_operation.pl $db $authority Merging "Call merge.pl for NCI-REPL" $work_id 0 $start_t >> /dev/null

#
# Move Processed Facts
#
$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    WHENEVER SQLERROR EXIT -1
 
    DELETE FROM mom_merge_facts WHERE status in ('P','F');
    exec MEME_SOURCE_PROCESSING.move_processed_facts ( -
        authority => '$authority', -
        work_id => $work_id);

EOF
if ($status != 0) then
    echo "Error moving facts"
    cat /tmp/t.$$.log
    exit 1
endif



#################################################################
# <h2>Safe Replacement Section</h2>
#################################################################

#
# Source Safe Replacement Step
#
echo "    Perform source safe replacement (BOTH,EXACT,NONE,NONE,NONE,NONE) ...`/bin/date`"

$ORACLE_HOME/bin/sqlplus -s $user@$db << EOF >&! /tmp/t.$$.log
    WHENEVER SQLERROR EXIT -1
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    set serveroutput on size 100000

    exec MEME_UTILITY.drop_it('table','t1');
    exec MEME_UTILITY.drop_it('table','t2');
    CREATE TABLE t1 (source VARCHAR2(40));
    CREATE TABLE t2 (source VARCHAR2(40));
    INSERT INTO t1 VALUES ('$new_source');
    INSERT INTO t2 VALUES ('$old_source');

    exec meme_source_processing.safe_replacement( -
        string_parameter => 'BOTH', code_parameter => 'EXACT', -
        source_aui_parameter => 'NONE', source_cui_parameter => 'NONE', -
        source_dui_parameter => 'NONE', tty_parameter => 'NONE', -
        old_source_table => 't2', new_source_table => 't1', -
        old_termgroup_table => '', new_termgroup_table => '', -
        change_status => 'Y', source => '$new_source', authority => '$authority', -
work_id => $work_id);

    exec meme_source_processing.delete_demotions (-
       source => '$new_source', -
	authority => '$authority', -
	work_id => $work_id);

EOF
if ($status != 0) then
    echo "Error handling safe replacement"
    cat /tmp/t.$$.log
    exit 1
endif

foreach value (`$MEME_HOME/bin/dump_table.pl -u $user -d $db -q "select a.high_source,a.low_source,b.stripped_source from source_source_rank a, source_rank b where a.low_source=b.source and a.stripped_source=b.stripped_source and b.stripped_source!='NCI'"`)
    set ns=`echo $value | perl -ne 'split /\|/; print "$_[0]\n";'`
    set os=`echo $value | perl -ne 'split /\|/; print "$_[1]\n";'`
    set ss=`echo $value | perl -ne 'chop;split /\|/; print "$_[2]\n";'`

    echo "    Perform source safe replacement $ns (EXACT,NONE,NONE,NONE,NONE,NONE) ...`/bin/date`"

    $ORACLE_HOME/bin/sqlplus -s $user@$db << EOF >&! /tmp/t.$$.log
    WHENEVER SQLERROR EXIT -1
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    set serveroutput on size 100000

    exec MEME_UTILITY.drop_it('table','t1');
    exec MEME_UTILITY.drop_it('table','t2');
    CREATE TABLE t1 (source VARCHAR2(40));
    CREATE TABLE t2 (source VARCHAR2(40));
    INSERT INTO t1 VALUES ('$ns');
    INSERT INTO t2 VALUES ('$os');

    exec meme_source_processing.safe_replacement( -
        string_parameter => 'EXACT', code_parameter => 'NONE', -
        source_aui_parameter => 'NONE', source_cui_parameter => 'NONE', -
        source_dui_parameter => 'NONE', tty_parameter => 'NONE', -
        old_source_table => 't2', new_source_table => 't1', -
        old_termgroup_table => '', new_termgroup_table => '', -
        change_status => 'Y', source => '$new_source', -
        authority => '$authority', work_id => $work_id);

    -- Demotions owned by $new_source, delete those
    exec meme_source_processing.delete_demotions (-
       source => '$new_source', -
	authority => '$authority', -
	work_id => $work_id);

EOF
    if ($status != 0) then
        echo "Error handling safe replacement for $ns"
	cat /tmp/t.$$.log
	exit 1
    endif

end

#################################################################
# <h2>New Merge Section</h2>
#################################################################

#
# Generated set NCI-MID
#
echo "    Perform generated set 'NCI-MID' ...`/bin/date`"

$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    WHENEVER SQLERROR EXIT -1
 
    exec MEME_UTILITY.drop_it('table','t1');
    exec MEME_UTILITY.drop_it('table','t2');
    CREATE TABLE t1 (termgroup VARCHAR2(40) NOT NULL);
    CREATE TABLE t2 (termgroup VARCHAR2(40) NOT NULL);
    insert into t1 select high_termgroup
    from source_termgroup_rank;

    insert into t2 select * from t1;
    insert into t2 select low_termgroup from source_termgroup_rank;

    -- Exclude the t2 list
    exec MEME_UTILITY.drop_it('table','t3');
    CREATE TABLE t3 AS SELECT termgroup 
    FROM termgroup_rank MINUS SELECT * FROM t2;

    DELETE FROM t2; 

    INSERT INTO t2 SELECT * FROM t3;

    DROP TABLE t3;


    exec MEME_SOURCE_PROCESSING.generate_facts ( -
	termgroup_table_1 => 't1', -
	termgroup_table_2 => 't2', -
	merge_set => 'NCI-MID', -
	string_parameter => 'BOTH', -
	code_parameter => 'NONE', -
	source_aui_parameter => 'NONE', source_cui_parameter => 'NONE', -
	source_dui_parameter => 'NONE', tty_parameter => 'NONE', -
	table_name => 'classes', -
	source => '$new_source', -
	authority => '$authority', -
	work_id => $work_id );

    -- Exclude safe replacement
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_1 => 'SAFE_REPLACEMENT', -
       arg_1 => '', not_1 => '', type_2 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-MID', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Use exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_1 => 'EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_2 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-MID', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Use norm exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_1 => 'NORM_EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_2 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-MID', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Restrict to new atoms only
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_1 => 'NEW_ATOMS', -
       arg_1 => '', not_1 => '', type_2 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-MID', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Use exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_2 => 'EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_1 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-MID', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Use norm exclude list
    exec MEME_SOURCE_PROCESSING.filter_facts ( -
       type_2 => 'NORM_EXCLUDE_LIST', -
       arg_1 => '', not_1 => '', type_1 => '', arg_2 => '', -
       not_2 => '', merge_set => 'NCI-MID', -
       source => '$new_source', authority => '$authority', -
       work_id => $work_id );

    -- Ad hoc filter
    delete from mom_candidate_facts where atom_id_2 in
    (select a.atom_id from classes a, classes b, string_ui c
     where a.concept_id = b.concept_id
       and b.source in (select current_name from source_version where source='SNOMEDCT_US')
       and b.sui = c.sui
       and c.string_pre like 'Entire%' and c.string like 'Entire%(body structure)');

    -- Ad hoc filter
    delete from mom_candidate_facts where atom_id_1 in
      (select atom_id from classes where concept_id in
        (select a.concept_id from classes a, atoms b
         where a.source='$new_source' and a.atom_id = b.atom_id
         and lower(b.atom_name) like '%allele%'));

    -- Ad hoc filter
    delete from mom_candidate_facts where atom_id_1 in
      (select atom_id from classes where concept_id in
        (select a.concept_id from classes a, atoms b
         where a.source='$new_source' and a.tty='SY' 
         and a.atom_id = b.atom_id
         and length(b.atom_name)<4));

    exec MEME_SOURCE_PROCESSING.load_facts ( -
        merge_set => 'NCI-MID', -
        integrity_vector => '', -
        change_status => 'Y', -
        make_demotion => 'Y', -
        authority => '$authority', -
        work_id => $work_id);


    -- Set All Checks
    update mom_merge_facts
    set integrity_vector = (select integrity_Vector from
    ic_applications where application='MERGE_O_MATIC');

EOF
if ($status != 0) then
    echo "Error loading merge set"
    cat /tmp/t.$$.log
    exit 1
endif

set start_t=`perl -e 'print time'`
$MEME_HOME/bin/merge.pl -host=$host -port=$port NCI-MID ENG-$authority $work_id $db >&! merge.nci-mid.log
if ($status != 0) then
    echo "Error merging"
    exit 1
endif
$MEME_HOME/bin/log_operation.pl $db $authority Merging "Call merge.pl for NCI-MID" $work_id 0 $start_t >> /dev/null

#
# Move Processed Facts
#
$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    WHENEVER SQLERROR EXIT -1
 
    DELETE FROM mom_merge_facts WHERE status in ('P','F');
    exec MEME_SOURCE_PROCESSING.move_processed_facts ( -
        authority => '$authority', -
        work_id => $work_id);

EOF
if ($status != 0) then
    echo "Error moving facts"
    cat /tmp/t.$$.log
    exit 1
endif

#
# Remove demotions connected to NCI atoms that are in the same
# concept as another NCI (or subsource) atom with the same code
# and also have a C level relationship to the concept on
# the other side of the demotion.  Make the C level rels
# status R as well
#
echo "    Delete unnecessary demotions from 'NCI-MID' ...`/bin/date`"

$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    WHENEVER SQLERROR EXIT -1
 
    exec MEME_UTILITY.drop_it('table','t1');
    CREATE TABLE t1 AS
    SELECT relationship_id row_id, concept_id_1, concept_id_2
    FROM relationships r
    WHERE r.source = '$new_source'
      AND status = 'D'
      AND atom_id_1 IN
        (SELECT a.atom_id FROM classes a, classes b
         WHERE a.concept_id = b.concept_id
           AND a.code = b.code
           AND r.atom_id_1 = a.atom_id
           AND b.status = 'R'
           AND a.tobereleased in ('Y','y')
           AND b.tobereleased in ('Y','y'))
      AND (concept_id_1, concept_id_2) IN
        (SELECT concept_id_1, concept_id_2 FROM relationships
         WHERE relationship_level = 'C'
         UNION ALL
         SELECT concept_id_2, concept_id_1 FROM relationships
         WHERE relationship_level = 'C');

    exec MEME_UTILITY.drop_it('table','t2');
    CREATE TABLE t2 AS
    SELECT relationship_id row_id
    FROM relationships
    WHERE status='N' 
      AND (concept_id_1, concept_id_2) IN
     (SELECT concept_id_1, concept_id_2 FROM t1
      UNION ALL
      SELECT concept_id_2, concept_id_1 FROM t1);

EOF
if ($status != 0) then
    echo "Error removing demotions"
    cat /tmp/t.$$.log
    exit 1
endif

$MEME_HOME/bin/batch.pl -a D -t R -s t t1 $db $new_source >&! batch.remove.d.log
if ($status != 0) then
    echo "Error removing demotions"
    cat batch.remove.d.log
    exit 1
endif

$MEME_HOME/bin/batch.pl -a S -n R -t R -s t t2 $db $new_source >&! batch.approve.c.log
if ($status != 0) then
    echo "Error making C level rels releasable"
    cat batch.approve.c.log
    exit 1
endif

#
# Cleanup
#
$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    WHENEVER SQLERROR EXIT -1
 
    exec MEME_UTILITY.drop_it('table','t1');
    exec MEME_UTILITY.drop_it('table','t2');

EOF
if ($status != 0) then
    echo "Error removing demotions"
    cat /tmp/t.$$.log
    exit 1
endif

#################################################################
# <h2>Post-Merge Section</h2>
#################################################################

#
# Resove Semantic Types
#
echo "    Resolve Semantic Types ...`/bin/date`"

if ($mode == "test") then
    $ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >! sty_term_ids 
    WHENEVER SQLERROR EXIT -2
    set wrap off
    set feedback off
    set pagesize 0
    set verify off
    set trimspool on
    set linesize 9999
    SELECT DISTINCT source_row_id || '|' ||
	attribute_value || '|' || classes_flag
    FROM attributes a, source_id_map b, 
	(SELECT concept_id,atom_id, decode(sign(insertion_date-(sysdate-10)),1,1,0) classes_flag 
  FROM classes
	 WHERE source='$new_source') c
    WHERE a.concept_id = c.concept_id
    AND c.atom_id=local_row_id
    AND table_name='C' AND b.source='$new_source'
    AND attribute_name='SEMANTIC_TYPE';
EOF
endif

$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF  >&! /tmp/t.sty.$$.log 
    WHENEVER SQLERROR EXIT -2
    set serveroutput on size 100000
    set feedback off
    ALTER SESSION SET sort_area_size=200000000;
    ALTER SESSION SET hash_area_size=200000000;
    exec MEME_SOURCE_PROCESSING.resolve_stys ( -
	source => '$new_source', -
        sty_fate => 'L', -
        authority => '$authority', -
        work_id => $work_id );
EOF



#
# Update Releasability
#
# Map obsolete rels, update releasability, and insert bequeathal rels
#
foreach value (`$MEME_HOME/bin/dump_table.pl -u $user -d $db -q "select a.high_source,a.low_source,b.stripped_source from source_source_rank a, source_rank b where a.low_source=b.source and a.stripped_source=b.stripped_source"`)
    set ns=`echo $value | perl -ne 'split /\|/; print "$_[0]\n";'`
    set os=`echo $value | perl -ne 'split /\|/; print "$_[1]\n";'`
    set ss=`echo $value | perl -ne 'chop;split /\|/; print "$_[2]\n";'`
    echo "    Map Obsolete Relationships ($ss) ...`/bin/date`"

    $ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
        WHENEVER SQLERROR EXIT -2
        set serveroutput on size 100000
        set feedback off
        ALTER SESSION SET sort_area_size=200000000;
        ALTER SESSION SET hash_area_size=200000000;
        exec MEME_SOURCE_PROCESSING.map_obsolete_rels (-
            stripped_source => '$ss', -
            authority => '$authority', -
            work_id => $work_id );
EOF
    if ($status != 0) then
        echo "Error mapping obsolete rels"
        cat /tmp/t.$$.log
    if ($?to == 1)  eval $MEME_HOME/bin/mail.pl $subject_flag $to_from_flags '-message="Error mapping obsolete rels"' 
        exit 1
    endif

    echo "    Update Releasability ($os)...`/bin/date`"
    $ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF  >&! /tmp/t.ur.$ss.$$.log 
        WHENEVER SQLERROR EXIT -2
        set serveroutput on size 100000
        set feedback off
        ALTER SESSION SET sort_area_size=200000000;
        ALTER SESSION SET hash_area_size=200000000;
        exec MEME_SOURCE_PROCESSING.update_releasability (-
            old_source => '$os', -
            new_source => '$ns', -
            authority => '$authority', -
            new_value => 'n', -
            work_id => $work_id );
EOF

    #
    # Bequeath old versioned SRC concepts
    #
    $ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    WHENEVER SQLERROR EXIT -2
    set serveroutput on size 100000
    set feedback off

    exec MEME_UTILITY.drop_it('table','t_os');
    CREATE TABLE t_os (
        row_id NUMBER );

    INSERT INTO t_os
    SELECT atom_id FROM classes
    WHERE source = 'SRC'
      AND concept_id IN
      (SELECT concept_id FROM classes a, atoms b
       WHERE source='SRC'
         AND termgroup = 'SRC/VAB'
         AND a.atom_id = b.atom_id
         AND atom_name = '$os' );

    exec MEME_UTILITY.drop_it('table','t_rel_os');
    CREATE TABLE t_rel_os AS
    SELECT  concept_id_1,concept_id_2,atom_id_1,atom_id_2,
                   relationship_name,relationship_attribute,
                   source, source_of_label,status,generated_status,
                   relationship_level,released,tobereleased,
                   relationship_id, suppressible,
                   sg_id_1, sg_type_1, sg_qualifier_1,
                   sg_id_2, sg_type_2, sg_qualifier_2
    FROM relationships WHERE 1=0;

    INSERT INTO t_rel_os
    SELECT concept_id_1,concept_id_2,0,0,
                   'BRT','',
                   'MTH', 'MTH','R','Y',
                   'C', 'N', 'Y', 0, 'N','','','','','',''
    FROM relationships
    WHERE atom_id_1 IN (SELECT * FROM t_os)
      AND relationship_attribute = 'has_version'
      AND relationship_level = 'S'
    UNION
    SELECT concept_id_2,concept_id_1,0,0,
                   'BRT','',
                   'MTH', 'MTH','R','Y',
                   'C', 'N', 'Y', 0, 'N','','','','','',''
    FROM relationships
    WHERE atom_id_2 IN (SELECT * FROM t_os)
      AND relationship_attribute = 'version_of'
      AND relationship_level = 'S';

EOF
    if ($status != 0) then
        echo 'Error preparing bequeathal rels'
        cat /tmp/t.$$.log
        exit 1
    endif

    $MEME_HOME/bin/insert.pl -w $work_id -host=$host -port=$port -rels t_rel_os $db $ns >&! insert.bequeathal.log

    #
    # Clean up temp tables
    #
    $ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.$$.log
    set serveroutput on size 100000
    set feedback off
    exec MEME_UTILITY.drop_it('table','t_os');
    exec MEME_UTILITY.drop_it('table','t_rel_os');
EOF

end


#
# Wait for resolve STYs and update releasability
#
set ef = 0
wait
if ($status != 0) then
    set ef = 1
endif

if (`grep -c ORA- /tmp/t.sty.$$.log` > 0) then
    echo "Error resolving STYs"
    cat /tmp/t.$$.log
    if ($?to == 1)  eval $MEME_HOME/bin/mail.pl $subject_flag $to_from_flags '-message="Error resolving STYs"'
    set ef = 1
endif
foreach value (`$MEME_HOME/bin/dump_table.pl -u $user -d $db -q "select a.high_source,a.low_source,b.stripped_source from source_source_rank a, source_rank b where a.low_source=b.source and a.stripped_source=b.stripped_source"`)
	    set ns=`echo $value | perl -ne 'split /\|/; print "$_[0]\n";'`
	    set os=`echo $value | perl -ne 'split /\|/; print "$_[1]\n";'`
	    set ss=`echo $value | perl -ne 'chop;split /\|/; print "$_[2]\n";'`
	    if (`grep -c ORA- /tmp/t.ur.$ss.$$.log` > 0) then
	        echo "Error updating releasability"
	        cat /tmp/t.ur.$ss.$$.log
	        if ($?to == 1)  eval $MEME_HOME/bin/mail.pl $subject_flag $to_from_flags '-message="Error updating releasability"'
	        set ef = 1;
	    endif

end

if ($ef == 1) then
    exit 1
endif

#
# Update String/Word Indexes
#
echo "    Update String/Word Indexes ...`/bin/date`"
$MEME_HOME/bin/add_words.csh -w $work_id $db >&! add_words.log 


#
# Generate standard report tables
#
echo "    Generate standard report tables ... `/bin/date`"
foreach value (`$MEME_HOME/bin/dump_table.pl -u $user -d $db -q "select a.stripped_source from source_source_rank a"`)

     set ss=`echo $value | perl -ne 'chop; split /\|/; print "$_[0]\n";'`
     echo "    Generate standard report tables - $ss ... `/bin/date`"
     $ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! counts.$ss.rpt 
          WHENEVER SQLERROR EXIT -2
          set serveroutput on size 100000
          set feedback off
          ALTER session SET sort_area_size=200000000;
          ALTER session SET hash_area_size=200000000;
          exec MEME_SOURCE_PROCESSING.report_tables( -
              root_source => '$ss', -
              authority => '$authority', -
              work_id => '$work_id' );
EOF
 
end


#
# Set Core Table Ranks
#
echo "    Set Core Table Ranks ...`/bin/date`"
$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF >&! /tmp/t.ranks.$$.log 
    WHENEVER SQLERROR EXIT -2
    set serveroutput on size 100000
    set feedback off
    ALTER session SET sort_area_size=200000000;
    ALTER session SET hash_area_size=200000000;
    
    -- Reset last release rank values from original source_classes_atoms load
    update classes set last_release_rank=0 where last_release_rank=5;
    
    exec MEME_RANKS.set_ranks( -
      classes_flag => 'Y', -
      attributes_flag => 'N', -
      relationships_flag => 'N', work_id => $work_id );
    COMMIT;
    exec MEME_RANKS.set_preference(work_id => $work_id);
EOF

#
# Set atom ordering: CODE
#
foreach value (`$MEME_HOME/bin/dump_table.pl -u $user -d $db -q "select high_source from source_source_rank where stripped_source!='NCI'"`)
    set ns=`echo $value | perl -ne 'split /\|/; print "$_[0]\n";'`
    echo "    Set atom ordering ($ns, CODE) ...`/bin/date`"

    $ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF  >&! /tmp/t.ar.$ns.$$.log 
        WHENEVER SQLERROR EXIT -2
        set serveroutput on size 100000
        set feedback off
        ALTER session SET sort_area_size=200000000;
        ALTER session SET hash_area_size=200000000;

        exec MEME_SOURCE_PROCESSING.set_atom_ordering( -
          source => '$ns', -
          ordering => 'CODE', -
          authority => '$authority', work_id => $work_id);
EOF
end

#
# Set atom ordering: DEPTH-FIRST,CODE
#
foreach value (`$MEME_HOME/bin/dump_table.pl -u $user -d $db -q "select high_source from source_source_rank where stripped_source='NCI'"`)
    set ns=`echo $value | perl -ne 'split /\|/; print "$_[0]\n";'`
    echo "    Set atom ordering ($ns, DEPTH-FIRST,CODE) ...`/bin/date`"

    $ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF  >&! /tmp/t.ar.$ns.$$.log 
        WHENEVER SQLERROR EXIT -2
        set serveroutput on size 100000
        set feedback off
        ALTER session SET sort_area_size=200000000;
        ALTER session SET hash_area_size=200000000;

        exec MEME_SOURCE_PROCESSING.set_atom_ordering( -
          source => '$ns', -
          ordering => 'DEPTH-FIRST,CODE', -
          authority => '$authority', work_id => $work_id);
EOF
end

#
# Wait for parallel processes
#
set ef = 0
wait
if ($status != 0) then
    set ef = 1
endif

#
# Error check report tables
#
foreach f (counts.*.rpt)
    if (`grep -c ORA- $f` > 0) then
        cat $f
        echo "Error generating counts $f"
        set ef = 1
    endif
end
if ($ef == 0) then
    foreach value (`$MEME_HOME/bin/dump_table.pl -u $user -d $db -q "select a.stripped_source from source_source_rank a"`)

        set ss=`echo $value | perl -ne 'chop; split /\|/; print "$_[0]\n";'`
        set sst=`echo $ss | perl -pe 's/-//g; s/\.//g;'`
        $MEME_HOME/bin/dump_table.pl -d $db -t ${sst}_demotions -u MTH | $EMS_HOME/bin/make-checklist.pl -d $db -m 100 -c chk_${sst}_demotions
        $MEME_HOME/bin/dump_table.pl -d $db -t ${sst}_merges -u MTH | $EMS_HOME/bin/make-checklist.pl -d $db -m 100 -c chk_${sst}_merges
        $MEME_HOME/bin/dump_table.pl -d $db -t ${sst}_need_review -u MTH | $EMS_HOME/bin/make-checklist.pl -d $db -m 100 -c chk_${sst}_need_review
        $MEME_HOME/bin/dump_table.pl -d $db -t ${sst}_replaced -u MTH | $EMS_HOME/bin/make-checklist.pl -d $db -m 100 -c chk_${sst}_replaced
        $MEME_HOME/bin/dump_table.pl -d $db -t ${sst}_sample -u MTH | $EMS_HOME/bin/make-checklist.pl -d $db -m 100 -c chk_${sst}_sample
end
endif

#
# Error check set ranks
#
if (`grep -c ORA- /tmp/t.ranks.$$.log` > 0) then
    echo "Error calculating ranks"
    cat /tmp/t.ranks.$$.log
    if ($?to == 1)  eval $MEME_HOME/bin/mail.pl $subject_flag $to_from_flags '-message="Error calculating ranks"'
    set ef = 1
endif

#
# Error check atom ordering
#
foreach value (`$MEME_HOME/bin/dump_table.pl -u $user -d $db -q "select high_source from source_source_rank"`)
    set ns=`echo $value | perl -ne 'split /\|/; print "$_[0]\n";'`
    if (`grep -c ORA- /tmp/t.ar.$ns.$$.log` > 0) then
        echo "Error setting atom ordering"
        cat /tmp/t.ar.$ns.$$.log
        if ($?to == 1)  eval $MEME_HOME/bin/mail.pl $subject_flag $to_from_flags '-message="Error setting atom_ordering"'
        set ef = 1
    endif
end

if ($ef == 1) then
    exit
endif

#
# Run matrix initializer
#
echo "    Run matrix initializer ...`/bin/date`"
$MEME_HOME/bin/matrixinit.pl -w $work_id -I $db >&! matrixinit.log
if ($status != 0) then
    echo "Error initializing matrix"
    if ($?to == 1)  eval $MEME_HOME/bin/mail.pl $subject_flag $to_from_flags '-message="Error initializing matrix"' 
    exit 1
endif


#
# Repartition MID
#
echo "    Repartition MID ...`/bin/date`"
$EMS_HOME/bin/chemconcepts.pl -d $db
$EMS_HOME/bin/batchpartition.pl -d $db >&! batch.partition.log 




##############################################################
# Cleanup
##############################################################
echo "    Removing temporary indexes ... `/bin/date`"
$ORACLE_HOME/bin/sqlplus -s $user@$db <<EOF
    whenever sqlerror exit -1
    set serveroutput on size 100000
    set feedback off
    exec MEME_UTILITY.drop_it('index','x_classes_scui');
    exec MEME_UTILITY.drop_it('index','x_classes_sdui');
    exec MEME_UTILITY.drop_it('index','x_classes_saui');
    exec MEME_UTILITY.drop_it('index','x_classes_aui');
    exec MEME_UTILITY.drop_it('index','x_fclasses_scui');
    exec MEME_UTILITY.drop_it('index','x_fclasses_sdui');
    exec MEME_UTILITY.drop_it('index','x_fclasses_saui');
    exec MEME_UTILITY.drop_it('index','x_rels_srui');
    exec MEME_UTILITY.drop_it('index','x_cxt_rels_srui');
    exec MEME_UTILITY.drop_it('index','x_ssui_string');
EOF

#
# Indicate end of insertion, compute stats
#
$ORACLE_HOME/bin/sqlplus -s $user@$real_db <<EOF > /dev/null 
   exec dbms_stats.gather_schema_stats( -
        ownname => 'MTH', degree => 2, options => 'GATHER STALE');
   exec dbms_stats.gather_schema_stats( -
        ownname => 'MEOW', degree => 2, options => 'GATHER STALE');
EOF

foreach sab (`/bin/cut -d\| -f 1 sources.src`)
   $ORACLE_HOME/bin/sqlplus -s $user@$real_db <<EOF > /dev/null
    UPDATE sims_info SET ${qual}_insertion_end = sysdate
    WHERE source = '$sab';
EOF
end


$MEME_HOME/bin/log_operation.pl $db $authority "$new_source Insertion"   "Done inserting $new_source" $work_id 0 $recipe_start_t >> /dev/null

set subject_flag='-subject="Insertion Complete - '$new_source'"'
if ($?to == 1)  eval $MEME_HOME/bin/mail.pl $subject_flag $to_from_flags '-message="Insertion finished."' 

echo "--------------------------------------------------------------"
echo "Finished $0 ... `/bin/date`"
echo "--------------------------------------------------------------"
