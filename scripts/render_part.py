"""Render an inclusive source-frame range to lossless PNGs; never encode a partial movie."""
import bpy,pathlib,argparse,sys,runpy,json,time,datetime,statistics,hashlib,shutil,traceback
R=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--start-frame',type=int,required=True);p.add_argument('--end-frame',type=int,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--force-cpu',action='store_true');A=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
assert 1<=A.start_frame<=A.end_frame<=4800,'Range must stay inside the original 1-4800 timeline'
O=A.output.resolve();O.mkdir(parents=True,exist_ok=True);START=time.monotonic();COUNT=A.end_frame-A.start_frame+1
# Reuse the exact already-validated quality settings, source checks, GPU selection and PNG validation.
sys.argv=['render.py','--','--mode','render','--output',str(O)]+(['--force-cpu'] if A.force_cpu else [])
G=runpy.run_path(str(R/'scripts/render.py'));C=G['C'];F=G['F'];write=G['write'];sha=G['sha'];png=G['png'];src=G['SRC']
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
status={'phase':'loading','started_utc':now(),'pid':__import__('os').getpid(),'frame_range':[A.start_frame,A.end_frame],'target_frames':COUNT,'master_frame_range':[1,4800],'fps':24,'size':[1920,1080],'monitor_interval_seconds':3600,'encoding':'deferred_until_both_parts_available'}
def update(**kw):
 status.update(kw);status['elapsed_seconds']=round(time.monotonic()-START,2);write(O/'status.json',status)
def camera_at(s,f):
 markers=[m for m in s.timeline_markers if m.camera and m.frame<=f];assert markers
 s.camera=max(markers,key=lambda m:m.frame).camera
def main():
 with G['lock']():
  update()
  try:
   s,h=G['load_master']();env=G['inspect'](s,h);dev=G['device'](s);env['device']=dev;write(O/'environment.json',env)
   assert dev['backend']!='CPU' or A.force_cpu,'GPU unavailable; fix environment before falling back to explicitly requested CPU'
   update(source_sha256=h,device=dev)
   manifest={'source_sha256':h,'settings':C,'blender_version':bpy.app.version_string}
   mp=O/'render_manifest.json'
   if mp.exists():assert json.loads(mp.read_text(encoding='utf8'))==manifest,'Source/settings mismatch; do not mix frames'
   else:write(mp,manifest)
   part={'source_sha256':h,'frame_range':[A.start_frame,A.end_frame],'frame_count':COUNT,'fps':24,'size':[1920,1080],'png_depth':16,'source_start_seconds':(A.start_frame-1)/24,'source_end_seconds_exclusive':A.end_frame/24,'preserve_original_numbering':True,'no_subtitles':True}
   pp=O/'part_manifest.json'
   if pp.exists():assert json.loads(pp.read_text(encoding='utf8'))==part,'Different frame partition in this folder'
   else:write(pp,part)
   ix=O/'frames_index.json';index=json.loads(ix.read_text(encoding='utf8')) if ix.exists() else {};todo=[];reused=0
   update(phase='checking_resume')
   for f in range(A.start_frame,A.end_frame+1):
    path=G['file_for'](f)
    if path.exists():
     try:
      rec=png(path,True)
      if str(f) in index:assert index[str(f)]==rec,'PNG hash changed'
      index[str(f)]=rec;reused+=1;continue
     except Exception:path.rename(path.with_name(path.name+'.invalid.'+str(time.time_ns())))
    todo.append(f)
   assert shutil.disk_usage(O).free>=len(todo)*9*1024**2+12*1024**3,'Insufficient output disk space'
   write(ix,index);durations=[];update(phase='rendering',rendered_frames=reused,reused_frames=reused)
   for n,f in enumerate(todo):
    # Keep the full master frame range: this preserves gate, season, water and shutter timing.
    s.frame_set(f);camera_at(s,f);s.render.filepath=str(G['file_for'](f));a=time.monotonic();bpy.ops.render.render(write_still=True);durations.append(time.monotonic()-a)
    index[str(f)]=png(G['file_for'](f),True);write(ix,index)
    avg=statistics.mean(durations[-12:]);update(phase='rendering',source_frame=f,camera=s.camera.name,rendered_frames=reused+n+1,mean_recent_frame_seconds=round(avg,3),remaining_estimate_seconds=round((len(todo)-n-1)*avg))
   update(phase='validating_part')
   for f in range(A.start_frame,A.end_frame+1):assert png(G['file_for'](f),True)==index[str(f)],f
   assert sha(src)==h,'Source was changed during rendering'
   result={**part,'complete':True,'source_unchanged':True,'actual_png_count':COUNT,'crc_and_sha256_verified':True,'render_settings':C,'device':dev,'rendered_now':len(todo),'reused_frames':reused,'active_run_seconds':round(time.monotonic()-START,2),'completed_utc':now(),'awaiting_other_part_before_encoding':True}
   write(O/'part_validation.json',result)
   update(phase='part_complete',rendered_frames=COUNT,source_unchanged=True,completed_utc=now(),total_seconds=round(time.monotonic()-START,2),next_action='Collect the other part, verify source/settings and frames 1-4800, then encode once')
  except Exception as e:update(phase='failed',error=repr(e));traceback.print_exc();raise
if __name__=='__main__':main()
