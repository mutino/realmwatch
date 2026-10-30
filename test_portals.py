import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import portals

def endpoint(tag='home', conn=None, x=1):
    flags=64|(1 if conn else 0)
    raw=struct.pack('<Hfffi',flags,x,2.,3.,-661882940)
    if conn: raw+=struct.pack('<Bi',*conn)
    text=tag.encode()
    return raw+struct.pack('<BiB',1,696029674,len(text))+text

def index(n=2, revision=5, version=42):
    return struct.pack('<HiiHBIi',version,n,1,1,0,revision,n)

def chunk(records): return struct.pack('<Hi',42,len(records))+b''.join(records)

class PortalTests(unittest.TestCase):
    def test_saved_links_not_tag_guessing(self):
        ps=portals.classify(portals.parse_portals(chunk([endpoint('a',(1,123)),endpoint('a',(17,123),4)]),2))
        self.assertEqual([p['status'] for p in ps],['linked','linked'])
        self.assertEqual(ps[0]['target'],ps[1]['id'])
        ps=portals.classify(portals.parse_portals(chunk([endpoint(),endpoint(x=4)]),2))
        self.assertTrue(all(p['status']=='unpaired' for p in ps))
    def test_blank_tags_and_duplicate_hashes(self):
        ps=portals.classify(portals.parse_portals(chunk([endpoint('',(1,123)),endpoint('',(17,123),4),endpoint('',(1,123),8)]),3))
        self.assertTrue(all(p['status']=='unresolved' for p in ps))
        self.assertEqual(ps[0]['tag'],'')
    def test_reject_truncation_count_mismatch_unknown_version(self):
        for raw,n in ((chunk([endpoint()])[:-1],1),(chunk([endpoint()]),2),(b'\xff\xff'+chunk([])[2:],0)):
            with self.assertRaises(ValueError): portals.parse_portals(raw,n)
        with self.assertRaises(ValueError): portals.portal_index(index(version=43))
    def test_nonfinite_coordinates(self):
        with self.assertRaises(ValueError): portals.parse_portals(chunk([endpoint(x=float('nan'))]),1)
    def test_index_selects_referenced_chunk_and_ignores_uncommitted(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for ext in ('ok','db2','fwl2'): (p/f'_main.1.{ext}').write_bytes(b'')
            (p/'_main.1.chunks').write_bytes(index(n=1))
            (p/'00_01__0_5.chunk').write_bytes(chunk([endpoint()]))
            (p/'00_01__0_6.chunk').write_bytes(b'corrupt future chunk')
            (p/'_main.2.chunks').write_bytes(b'future index')
            before={f.name:f.read_bytes() for f in p.iterdir()}
            result=portals.scan(p)
            self.assertEqual(result['generation'],1)
            self.assertEqual(len(result['portals']),1)
            self.assertEqual(before,{f.name:f.read_bytes() for f in p.iterdir()})
    def test_no_portal_chunk_is_empty_world(self):
        self.assertEqual(portals.portal_index(struct.pack('<Hii',42,0,0)),(42,None))
    def test_failed_scan_retains_last_good_result(self):
        c={'Name':'test'}
        portals._CACHE.clear()
        with patch('portals.world_path',return_value=Path('/world')),patch('portals.committed',return_value=1),patch('portals.scan',return_value={'generation':1,'portals':[{'tag':'a'}]}):
            portals.snapshot(c)
        with patch('portals.world_path',return_value=Path('/world')),patch('portals.committed',side_effect=ValueError('Unavailable')):
            result=portals.snapshot(c)
        self.assertTrue(result['stale']);self.assertEqual(result['portals'],[{'tag':'a'}])
    def test_changed_world_never_inherits_cached_portals(self):
        c={'Name':'changed'}
        portals._CACHE['changed']={'_path':'/old','generation':1,'portals':[{'tag':'old world'}]}
        with patch('portals.world_path',return_value=Path('/new')),patch('portals.committed',side_effect=ValueError('Unavailable')):
            result=portals.snapshot(c)
        self.assertEqual(result['portals'],[])

    def test_missing_connection_target_not_linked(self):
        ps=portals.classify(portals.parse_portals(chunk([endpoint('a',(1,123))]),1))
        self.assertEqual(ps[0]['status'],'unresolved')
if __name__=='__main__': unittest.main()
