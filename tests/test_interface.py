import unittest,sys,threading,json,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from serve_ui import Handler,HTTPServer
class InterfaceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=HTTPServer(('127.0.0.1',0),Handler)
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
  cls.origin=f'http://127.0.0.1:{cls.server.server_port}'
 @classmethod
 def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.thread.join()
 def test_html(self):
  with urllib.request.urlopen(self.origin) as r:
   text=r.read().decode();self.assertIn('食材／酒材進貨',text);self.assertIn('業績獎金',text);self.assertIn('/api/calculate',text)
 def test_engine(self):
  p=Path(__file__).resolve().parents[1]/'assets/example.json';body=p.read_bytes()
  req=urllib.request.Request(self.origin+'/api/calculate',data=body,headers={'Origin':self.origin,'Content-Type':'application/json'})
  with urllib.request.urlopen(req) as r:
   data=json.load(r);self.assertEqual(data['results'][0]['direct_cost'],'54.50')
 def test_foreign_origin(self):
  req=urllib.request.Request(self.origin+'/api/calculate',data=b'{}',headers={'Origin':'https://example.com'})
  with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
  self.assertEqual(e.exception.code,403)
 def test_missing_origin(self):
  req=urllib.request.Request(self.origin+'/api/calculate',data=b'{}')
  with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
  self.assertEqual(e.exception.code,403)
 def test_invalid_json(self):
  req=urllib.request.Request(self.origin+'/api/calculate',data=b'broken',headers={'Origin':self.origin})
  with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
  self.assertEqual(e.exception.code,400)
 def test_arbitrary_path(self):
  with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(self.origin+'/SKILL.md')
  self.assertEqual(e.exception.code,404)
if __name__=='__main__':unittest.main()
