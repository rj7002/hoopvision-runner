#!/usr/bin/env python3
"""Synthetic-only source-original SHA merge tests; never reads private NBA XYZ."""
import gzip,hashlib,importlib.util,io,json,tarfile,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("native",Path(__file__).with_name("nov09_reconcile_original_xyz.py"))
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class SourceOnly(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory();self.addCleanup(self.d.cleanup)
        self.root=Path(self.d.name);self.live=self.root/"live";self.live.mkdir()
        self.sdk=self.root/"sdk";self.sdk.mkdir()
        self.gid="0022600210"
    def archive(self,folder,prefix,i,t,positions,imputed=False):
        start=1794286380000+i*60000
        m={"game_id":self.gid,"start_ms":start,"successful_windows":1,
           "frames_with_players":int(any(x!="ball" for x in positions)),
           "frames_with_ball":int("ball" in positions),"observed":True,"imputed":imputed}
        row={"from":start,"to":start+4999,
             "events":[{"metadata":{"keyframes":[{"timestamp":t,"positions":positions}]}}]}
        raw=gzip.compress((json.dumps(row)+"\n").encode())
        file=folder/(prefix+str(i).zfill(2)+".tar.gz")
        with tarfile.open(file,"w:gz") as tf:
            for name,data in [("manifest.json",json.dumps(m).encode()),("raw-slots.jsonl.gz",raw)]:
                tinfo=tarfile.TarInfo(name);tinfo.size=len(data);tf.addfile(tinfo,io.BytesIO(data))
        m["archive_sha256"]=hashlib.sha256(file.read_bytes()).hexdigest()
        file.with_suffix("").with_suffix(".json").write_text(json.dumps(m))
    def originals(self):
        for i in range(8):self.archive(self.live,"live-",i,1000+i,{"7":{"x":i,"y":1}})
    def test_recover_new_original_not_modeled(self):
        self.originals()
        self.archive(self.sdk,"sdk-part-",0,2000,{"7":{"x":8,"y":2},"ball":{"x":7,"y":9}})
        folder=self.root/"out";r=mod.reconcile(self.gid,self.live,self.sdk,folder)
        self.assertEqual(r["net_new_player_utc"],1)
        self.assertEqual(r["net_new_ball_utc"],1)
        self.assertEqual(r["modeled_coordinates_added"],0)
        self.assertEqual(len(gzip.decompress((folder/"source_original_native.jsonl.gz").read_bytes()).splitlines()),9)
    def test_reject_modified_archive(self):
        self.originals()
        path=sorted(self.live.glob("*.tar.gz"))[0];path.write_bytes(path.read_bytes()+b"bad")
        with self.assertRaisesRegex(ValueError,"sha_mismatch"):
            mod.reconcile(self.gid,self.live,self.sdk,self.root/"out")
    def test_reject_imputed(self):
        for i in range(8):self.archive(self.live,"live-",i,1000+i,{"7":{"x":i}},imputed=(i==0))
        with self.assertRaisesRegex(ValueError,"nonoriginal_source"):
            mod.reconcile(self.gid,self.live,self.sdk,self.root/"out")
if __name__=="__main__":unittest.main()
