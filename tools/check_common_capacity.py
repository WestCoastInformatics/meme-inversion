#!/usr/bin/env python3
"""Check version-specific reviewed capacity profiles and unchanged defaults."""
import copy
from types import SimpleNamespace
from unittest.mock import patch

import inversion_worker as worker


def check():
    values=[]
    lock={'request':{'source':'MTH','version':'MTH_2026AA'},'case':{}}
    with patch.object(worker,'available_memory',return_value=32*1024**3),patch.object(worker.shutil,'disk_usage',return_value=SimpleNamespace(free=47*1024**3)):
        try:worker.capacity(lock)
        except RuntimeError:values.append('Default 50 GiB guard remains enforced')
        else:raise AssertionError('Default reserve bypassed')
        lock['case']['capacity_profile']={'id':'mth-2026aa-core-v1','minimum_free_disk_gib':45}
        assert worker.capacity(lock)['minimum_free_disk_gib']==45;values.append('Reviewed MTH profile accepts measured available space')
        for field,value in [('minimum_free_disk_gib',1),('id','unknown')]:
            changed=copy.deepcopy(lock);changed['case']['capacity_profile'][field]=value
            try:worker.capacity(changed)
            except RuntimeError:values.append('Unreviewed capacity override rejected: '+field)
            else:raise AssertionError('Unreviewed budget accepted')
        changed=copy.deepcopy(lock);changed['request']['source']='NCI'
        try:worker.capacity(changed)
        except RuntimeError:values.append('Capacity profile cannot move to another source')
        else:raise AssertionError('Cross-source profile accepted')
        with patch.object(worker.shutil,'disk_usage',return_value=SimpleNamespace(free=44*1024**3)):
            try:worker.capacity(lock)
            except RuntimeError:values.append('MTH minimum remains enforced below 45 GiB')
            else:raise AssertionError('Insufficient space accepted')
    return values


if __name__=='__main__':
    for item in check():print('PASS',item)
