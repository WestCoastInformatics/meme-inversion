#!/usr/bin/env python3
"""Measure actual NCIt hierarchy serialization across Perl hash seeds.

Use synthetic multiple-root/multiple-parent data and the real hierarchy,
context/attribute serializers and source configuration. No inverter output or
operational library is changed. This characterizes the next separate change.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PROBE = r'''
use strict;
use warnings;
use NLMConfig;
BEGIN {
    if ($ENV{HIERARCHY_PROBE_FILE}) {
        require $ENV{HIERARCHY_PROBE_FILE};
        $INC{'Hierarchy.pm'} = $ENV{HIERARCHY_PROBE_FILE};
    }
}
use Hierarchy;
use Context;
use Attribute;
use IdGen;
use JSON::PP qw(encode_json);
{ package ProbeLog;
  sub logError { die $_[1]; }
  sub logIt {} sub logInfo {} sub logDebug {} sub logWarn {}
}
my $cfg = NLMConfig->new($ARGV[0], 0);
my $log = bless {}, 'ProbeLog';
my $ids = IdGen->new(1, 1, 1);
Hierarchy->init(\$log, \$cfg);
Context->init(\$log, \$cfg);
Attribute->init(\$log, \$cfg, \$ids);
my $hier = Hierarchy->new();
my ($contexts, $attributes) = ('', '');
open(my $cxtout, '>', \$contexts) or die $!;
open(my $attout, '>', \$attributes) or die $!;
Context->setFileHandler($cxtout);
Attribute->setFileHandler($attout);
my $root = Context->new('Context.ROOT');
my $parent = Context->new('Context.PAR');
my $attr = Attribute->new('Attribute.CONTEXT');
my %names = (31926003 => $cfg->getEle('HC.RootNodeName'));
my %codes = ();
for my $number (1001..1007) {
    $names{$number} = "Node $number";
    $codes{$number} = "C$number";
}
for my $edge ([1001,1002], [1001,1003], [1002,1004], [1003,1004],
             [1004,1005], [1006,1007], [1007,1004]) {
    $hier->addParChild(@$edge);
}
$hier->setRoot(31926003);
my $status = $hier->dumpCxtsAttrs(\$root, \$parent, 0, \$attr, \%names, 0, \%codes, 0, 0);
die "Hierarchy failed" if $status;
close($cxtout); close($attout);
print encode_json({contexts => $contexts, attributes => $attributes, perl_version => "$^V"});
'''


def probe(repo_root, hierarchy_file=None):
    inv = repo_root / 'INV'
    config = repo_root / 'sources/NCI_2026_10D/etc/nci.cfg'
    results = []
    with tempfile.TemporaryDirectory(prefix='nci-hierarchy-order-') as directory:
        combined = Path(directory) / 'combined.cfg'
        combined.write_bytes((inv / 'etc/inv_defaults.cfg').read_bytes() + config.read_bytes())
        for seed in ['1', '2', '17', '12345']:
            env = dict(os.environ, INV_HOME=str(inv.resolve()), PERL_HASH_SEED=seed, PERL_PERTURB_KEYS='2', LC_ALL='C')
            if hierarchy_file is not None:
                env['HIERARCHY_PROBE_FILE'] = str(hierarchy_file.resolve())
            process = subprocess.run([shutil.which('perl'), '-I' + str(inv.resolve() / 'lib'),
                                      '-I' + str(inv.resolve() / 'bin'), '-e', PROBE, str(combined)],
                                     cwd=directory, env=env, capture_output=True, text=True, timeout=30)
            if process.returncode:
                raise RuntimeError(process.stderr)
            data = json.loads(process.stdout)
            item = {'seed': seed, 'perl_version': data['perl_version']}
            for kind in ['contexts', 'attributes']:
                raw = data[kind].encode()
                lines = raw.splitlines(keepends=True)
                item[kind] = {'rows': len(lines), 'raw_sha256': hashlib.sha256(raw).hexdigest(),
                              'record_multiset_sha256': hashlib.sha256(b''.join(sorted(lines))).hexdigest()}
                if kind == 'attributes':
                    content = [row.split(b'|', 1)[1] for row in lines]
                    item[kind]['content_multiset_without_row_id_sha256'] = hashlib.sha256(b''.join(sorted(content))).hexdigest()
            if item['contexts']['rows'] != 11 or item['attributes']['rows'] != 12:
                raise RuntimeError('The multiple-parent paths were not preserved')
            results.append(item)
    tested = hierarchy_file if hierarchy_file is not None else inv / 'lib/Hierarchy.pm'
    return {'hierarchy_sha256': hashlib.sha256(tested.read_bytes()).hexdigest(),
            'override_tested': hierarchy_file is not None,
            'fixture': 'Seven nodes, two roots, shared descendant with three parents; 11 contexts and 12 CONTEXT attributes',
            'seeds': results,
            'context_bytes_stable': len({row['contexts']['raw_sha256'] for row in results}) == 1,
            'attribute_bytes_stable': len({row['attributes']['raw_sha256'] for row in results}) == 1,
            'context_contents_stable': len({row['contexts']['record_multiset_sha256'] for row in results}) == 1,
            'attribute_contents_stable': len({row['attributes']['content_multiset_without_row_id_sha256'] for row in results}) == 1,
            'operational_code_changed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--json-output', type=Path)
    parser.add_argument('--hierarchy-file', type=Path, help='Test a proposed module in memory without replacing the operational library')
    args = parser.parse_args()
    result = probe(args.repo_root, args.hierarchy_file)
    if args.json_output:
        args.json_output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'seeds'}, indent=2))
