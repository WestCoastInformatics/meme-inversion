#!/usr/bin/env python3
"""Exercise actual MDR history code and hierarchy serialization across hash seeds."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

PROBE=r'''
use strict;
use warnings;
use NLMConfig;
BEGIN { require $ENV{HIERARCHY_PROBE_FILE}; $INC{'Hierarchy.pm'}=$ENV{HIERARCHY_PROBE_FILE}; }
use Hierarchy;
use Context;
use Attribute;
use IdGen;
use JSON::PP qw(encode_json);
{ package ProbeLog; sub logError { die $_[1]; } sub logIt {} sub logInfo {} sub logDebug {} sub logWarn {} }
our ($Log,$Cfg,$Hier);
our (%cdTty2said,%said2name,%said2sgid);
our $smqtlAttr;
my $cfg=NLMConfig->new($ARGV[0],0);my $log=bless {},'ProbeLog';my $ids=IdGen->new(1,1,1);
Hierarchy->init(\$log,\$cfg);Context->init(\$log,\$cfg);Attribute->init(\$log,\$cfg,\$ids);
my $hier=Hierarchy->new();$Cfg=\$cfg;$Log=\$log;$Hier=\$hier;
%cdTty2said=('1001|OS'=>1001,'2001|HG'=>1002,'3001|HT'=>1003,'4001|PT'=>1004,
             '1005|OS'=>1005,'2002|HG'=>1006,'3002|HT'=>1007,
             '1008|OS'=>1008,'2003|HG'=>1009,'3003|HT'=>1010);
for my $id (1001..1010) {$said2name{$id}="Node $id";$said2sgid{$id}="C$id";}
open(my $source,'<',$ARGV[1]) or die $!;my $text;{local $/;$text=<$source>;}close($source);
my ($body)=$text=~/(sub readHierInfo\{.*?)(?=\nsub prepareCxts)/s;
die 'Unknown source hierarchy function boundary' unless $body;
eval $body;die $@ if $@;
readHierInfo();
my ($contexts,$attributes)=('','');open(my $cout,'>',\$contexts) or die $!;open(my $aout,'>',\$attributes) or die $!;
Context->setFileHandler($cout);Attribute->setFileHandler($aout);
my $root=Context->new('Context.ROOT');my $parent=Context->new('Context.PAR');my $sibling=Context->new('Context.SIB');my $attr=Attribute->new('Attribute.CXT');
die 'Hierarchy failed' if $hier->dumpCxtsAttrs(\$root,\$parent,\$sibling,\$attr,\%said2name,0,\%said2sgid,0,1);
close($cout);close($aout);print encode_json({contexts=>$contexts,attributes=>$attributes,perl_version=>"$^V"});
'''


def check(candidate,stable_hierarchy,baseline_hierarchy):
    candidate=Path(candidate).resolve();inv=candidate/'INV';checks=[];observations={}
    with tempfile.TemporaryDirectory(prefix='mdr-corrections-') as temporary:
        root=Path(temporary)
        for directory in ['bin','src','orig']:(root/directory).mkdir()
        classes=b''.join(f'{i}|MDR_29_1|MDR_29_1/{tty}|{code}|R|Y|A|fixture|N||{code}||ENG||\n'.encode() for i,tty,code in [(100,'PT',1),(101,'LLT',2),(102,'OL',3)])
        (root/'src/classes_atoms.src').write_bytes(classes)
        outputs=[]
        for name,raw in [('lf',b'1|8.0\n2|8.1\n3|9.0\n'),('crlf',b'1|8.0\r\n2|8.1\r\n3|9.0\r\n'),('mixed-eof',b'1|8.0\r\n2|8.1\n3|9.0')]:
            (root/'src/attributes.src').write_bytes(b'1|fixture\n');(root/'orig/mdr_by_version.txt').write_bytes(raw)
            process=subprocess.run(['/usr/bin/perl',str(candidate/'sources/MDR_29_1/bin/append_atn.pl')],cwd=root/'bin',env=dict(os.environ,INV_HOME_OLD=str(inv)),capture_output=True,timeout=30)
            if process.returncode:raise RuntimeError(process.stderr.decode())
            value=(root/'src/attributes.src').read_bytes();outputs.append(value)
            rows=value.splitlines()[1:];assert len(rows)==3 and b'\r' not in value
            for row,code,version in zip(rows,[b'1',b'2',b'3'],[b'8.0',b'8.1',b'9.0']):
                fields=row.split(b'|');assert fields[1]==code and fields[4]==version and fields[13]==hashlib.md5(version).hexdigest().encode()
            checks.append('Actual appender produces clean values and matching digests: '+name)
        assert len(set(outputs))==1;checks.append('LF, CRLF and mixed endings/no final newline produce identical attribute bytes')
        (root/'src/attributes.src').write_bytes(b'1|fixture\n');(root/'orig/mdr_by_version.txt').write_bytes(b'1|8\r.0\n')
        failure=subprocess.run(['/usr/bin/perl',str(candidate/'sources/MDR_29_1/bin/append_atn.pl')],cwd=root/'bin',capture_output=True,timeout=30)
        assert failure.returncode and b'Unexpected carriage return' in failure.stderr;checks.append('Unexpected embedded carriage returns reject the input')
        native=root/'hierarchy.txt'
        native.write_text(''.join('$'.join([str(4001),str(ht),str(hg),str(soc),'PT','HT','HG','SOC','AB','','','N'])+'\n' for ht,hg,soc in [(3001,2001,1001),(3002,2002,1005),(3003,2003,1008)]))
        config=root/'combined.cfg';config.write_bytes((inv/'etc/inv_defaults.cfg').read_bytes()+(candidate/'sources/MDR_29_1/etc/MDR.cfg').read_bytes()+('\nFile.INP.MDHIER = '+str(native)+'\n').encode())
        for label,library in [('production-serializer',baseline_hierarchy),('stable-serializer',stable_hierarchy)]:
            results=[]
            for seed in ['1','2','17','12345']:
                env=dict(os.environ,INV_HOME=str(inv),HIERARCHY_PROBE_FILE=str(Path(library).resolve()),PERL_HASH_SEED=seed,PERL_PERTURB_KEYS='2',LC_ALL='C')
                process=subprocess.run(['/usr/bin/perl','-I'+str(inv/'lib'),'-I'+str(inv/'bin'),'-e',PROBE,str(config),str(candidate/'sources/MDR_29_1/bin/invert_mdr.pl')],cwd=root,env=env,capture_output=True,timeout=30)
                if process.returncode:raise RuntimeError(process.stderr.decode())
                data=json.loads(process.stdout);item={'seed':seed,'perl_version':data['perl_version']}
                for name in ['contexts','attributes']:
                    raw=data[name].encode();item[name]={'rows':raw.count(b'\n'),'sha256':hashlib.sha256(raw).hexdigest(),'record_multiset_sha256':hashlib.sha256(b''.join(sorted(raw.splitlines(keepends=True)))).hexdigest()}
                assert item['contexts']['rows']==15 and item['attributes']['rows']==13
                results.append(item)
            observations[label]=results
        stable=observations['stable-serializer'];legacy=observations['production-serializer']
        assert len({x['contexts']['sha256'] for x in stable})==len({x['attributes']['sha256'] for x in stable})==1
        checks.append('Actual corrected MDR hierarchy function and stable serializers produce identical context/attribute bytes for four hash seeds')
        assert len({x['contexts']['record_multiset_sha256'] for x in stable+legacy})==1
        checks.append('Stable ordering preserves every multiple-root/multiple-parent hierarchy record and sibling pair')
        assert len({x['attributes']['sha256'] for x in legacy})>1
        checks.append('Production serializer control still exposes generated-ID/order variation')
    return {'checks':checks,'hash_seed_fixture':observations,'candidate_source_paths':str(candidate),
            'stable_hierarchy_sha256':hashlib.sha256(Path(stable_hierarchy).read_bytes()).hexdigest(),
            'production_hierarchy_sha256':hashlib.sha256(Path(baseline_hierarchy).read_bytes()).hexdigest()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',required=True,type=Path);parser.add_argument('--stable-hierarchy',required=True,type=Path);parser.add_argument('--baseline-hierarchy',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    result=check(args.candidate,args.stable_hierarchy,args.baseline_hierarchy)
    with args.output.open('x') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    for item in result['checks']:print('PASS',item)
