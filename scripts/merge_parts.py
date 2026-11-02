"""Combine verified original-numbered PNG ranges without rendering or re-encoding."""
import argparse,pathlib,json,hashlib,struct,zlib,shutil,os,datetime
R=pathlib.Path(__file__).resolve().parents[1];C=json.loads((R/'config/render.json').read_text(encoding='utf8'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def png(p):
 b=p.read_bytes();assert b[:8]==b'\x89PNG\r\n\x1a\n' and b[-8:]==b'IEND\xaeB`\x82',str(p)
 assert struct.unpack('>IIBB',b[16:26])==(1920,1080,16,2),str(p)
 at=8
 while at<len(b):
  n=struct.unpack_from('>I',b,at)[0];assert at+12+n<=len(b),str(p)
  assert zlib.crc32(b[at+4:at+8+n])&0xffffffff==struct.unpack_from('>I',b,at+8+n)[0],str(p)
  at+=12+n
 assert at==len(b),str(p)
 return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def main():
 p=argparse.ArgumentParser();p.add_argument('--first',type=pathlib.Path,required=True);p.add_argument('--second',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();dest=a.output.resolve()
 first=a.first.resolve();second=a.second.resolve();assert dest not in [first,second],'Use a separate merged output folder'
 assert not (dest/'active.lock').exists(),'Output has an active worker lock; inspect it first'
 source=json.loads((R/'manifest.json').read_text(encoding='utf8'))['files'][C['project']]['sha256'];expected=None;records=[]
 for root,lo,hi in [(first,1,3000),(second,3001,4800)]:
  manifest=json.loads((root/'render_manifest.json').read_text(encoding='utf8'));assert manifest['source_sha256']==source and manifest['settings']==C,'Different master or quality settings'
  if expected is None:expected=manifest
  else:assert manifest==expected,'Different source, settings or Blender version'
  index=json.loads((root/'frames_index.json').read_text(encoding='utf8'));part=root/'part_manifest.json'
  if part.exists():assert json.loads(part.read_text(encoding='utf8'))['frame_range']==[lo,hi],'Incorrect partition range'
  for f in range(lo,hi+1):
   path=root/'frames'/f'{f:05}.png';rec=png(path);assert str(f) in index and rec==index[str(f)],'Frame/index mismatch: '+str(path);records.append((f,path,rec))
 # Validate both complete parts before writing any combined frames.
 frames=dest/'frames';frames.mkdir(parents=True,exist_ok=True);new_index={};counts={'hardlinked':0,'copied':0,'already_present':0}
 for f,path,rec in records:
  out=frames/path.name
  if out.exists():assert png(out)==rec,'Conflicting existing merged frame';counts['already_present']+=1
  else:
   try:os.link(path,out);counts['hardlinked']+=1
   except OSError:shutil.copy2(path,out);counts['copied']+=1
  new_index[str(f)]=rec
 assert len(new_index)==4800
 for name,data in [('render_manifest.json',expected),('frames_index.json',new_index),('merge_validation.json',{'source_sha256':source,'frames':4800,'fps':24,'duration_seconds':200,'first_range':[1,3000],'second_range':[3001,4800],'original_numbering_preserved':True,'png_crc_and_sha_verified':True,'source_parts_unchanged':True,'file_operations':counts,'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})]:
  (dest/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
 print('MERGED_4800_VERIFIED_PNGS. Next: python scripts/start_render.py --mode encode --output <merged output folder>')
if __name__=='__main__':main()
