"""Regression checks against accidental duplicate/foreign Workshop identities."""
from pathlib import Path
import importlib.util,json,tempfile,unittest

TOOLS=Path(__file__).resolve().parents[1]/'tools'
spec=importlib.util.spec_from_file_location('workshop_identity',TOOLS/'workshop_identity.py')
identity=importlib.util.module_from_spec(spec);spec.loader.exec_module(identity)

class WorkshopIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.pub=Path(self.tmp.name);self.mid='ExampleMainMod';self.item='3834692575'
    def record(self,**changes):
        value={'app_id':108600,'mod_id':self.mid,'publishedfileid':self.item}
        value.update(changes);(self.pub/'workshop-item.json').write_text(json.dumps(value),encoding='utf-8')
    def test_new_draft_remains_idless(self):
        value=identity.resolve_workshop_item(self.pub,self.mid,{'visibility':'private','publishedfileid':None})
        self.assertIsNone(value);self.assertEqual(identity.native_item_id_lines(value),[])
    def test_assigned_item_is_reused_in_native_output(self):
        self.record();value=identity.resolve_workshop_item(self.pub,self.mid,{'workshop_id':self.item})
        self.assertEqual(value,self.item);self.assertEqual(identity.native_item_id_lines(value),['id='+self.item])
    def test_other_mod_is_rejected(self):
        self.record(mod_id='AnotherMainMod')
        with self.assertRaisesRegex(ValueError,'Mod ID'):identity.resolve_workshop_item(self.pub,self.mid)
    def test_other_app_is_rejected(self):
        self.record(app_id=480)
        with self.assertRaisesRegex(ValueError,'Steam app'):identity.resolve_workshop_item(self.pub,self.mid)
    def test_missing_canonical_record_cannot_reset_assigned_metadata(self):
        with self.assertRaisesRegex(ValueError,'requires'):identity.resolve_workshop_item(self.pub,self.mid,{'publishedfileid':self.item})
    def test_conflicting_metadata_is_rejected(self):
        self.record()
        with self.assertRaisesRegex(ValueError,'conflicts'):identity.resolve_workshop_item(self.pub,self.mid,{'workshop_item_id':'3834692923'})
    def test_conflicting_canonical_aliases_are_rejected(self):
        self.record(workshop_id='3834692923')
        with self.assertRaisesRegex(ValueError,'consistent'):identity.resolve_workshop_item(self.pub,self.mid)
    def test_malformed_ids_never_become_create_requests(self):
        for invalid in [0,-1,True,' ','0','123.0','3\n4',str(2**64)]:
            with self.subTest(value=invalid):
                self.record(publishedfileid=invalid)
                with self.assertRaises(ValueError):identity.resolve_workshop_item(self.pub,self.mid)
    def test_multi_mod_identity_is_rejected(self):
        self.record(mod_ids=[self.mid,'Other'])
        with self.assertRaisesRegex(ValueError,'exactly'):identity.resolve_workshop_item(self.pub,self.mid)

if __name__=='__main__':unittest.main()
