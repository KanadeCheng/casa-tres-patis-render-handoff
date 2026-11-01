"""Run inside Blender; all paths are repository-relative, with resumable PNG output."""
import bpy,argparse,pathlib,json,hashlib,datetime,time,statistics,os,struct,zlib,traceback,shutil,sys,contextlib
R=pathlib.Path(__file__).resolve().parents[1];C=json.loads((R/'config/render.json').read_text(encoding='utf8'))
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['inspect','preflight','render','encode','verify'],default='render');p.add_argument('--output',type=pathlib.Path,default=R/'output');p.add_argument('--force-cpu',action='store_true');A=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
O=A.output.resolve();O.mkdir(parents=True,exist_ok=True);F=O/'frames';F.mkdir(exist_ok=True);SRC=R/C['project'];START=time.monotonic()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,data):
 temp=p.with_name(p.name+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(p)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def alive(pid):
 if os.name=='nt':
  import ctypes
  k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.restype=ctypes.c_void_p;h=k.OpenProcess(0x1000,False,int(pid))
  if not h:return ctypes.get_last_error()==5
  c=ctypes.c_ulong();ok=k.GetExitCodeProcess(ctypes.c_void_p(h),ctypes.byref(c));k.CloseHandle(ctypes.c_void_p(h));return bool(ok and c.value==259)
 try:os.kill(int(pid),0);return True
 except ProcessLookupError:return False
 except PermissionError:return True
@contextlib.contextmanager
def lock():
 path=O/'active.lock'
 if path.exists():
  d=json.loads(path.read_text());
  if alive(d['pid']):raise RuntimeError('A render worker is already active: '+str(d))
  path.unlink()
 fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,json.dumps({'pid':os.getpid(),'mode':A.mode,'started_utc':now()}).encode());os.close(fd)
 try:yield
 finally:
  if path.exists():path.unlink()
def configure(s):
 assert s.render.fps==24 and s.frame_start==1 and s.frame_end==4800,'Master timing mismatch; do not merely change FPS'
 s.render.engine='CYCLES';s.cycles.samples=C['samples'];s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=C['adaptive_threshold'];s.cycles.adaptive_min_samples=C['adaptive_minimum'];s.cycles.use_denoising=True;s.cycles.denoiser=C['denoiser']
 for key,attr in [('total','max_bounces'),('diffuse','diffuse_bounces'),('glossy','glossy_bounces'),('transmission','transmission_bounces'),('transparent','transparent_max_bounces')]:setattr(s.cycles,attr,C['bounces'][key])
 s.render.resolution_x,s.render.resolution_y=C['resolution'];s.render.resolution_percentage=100;s.render.fps_base=1;s.render.use_simplify=False;s.render.use_sequencer=False;s.render.use_compositing=True;s.render.use_persistent_data=True
 s.render.use_motion_blur=True;s.render.motion_blur_shutter=C['motion_blur_shutter']
 s.view_settings.view_transform=C['view_transform'];s.view_settings.look=C['look'];s.view_settings.exposure=C['exposure'];s.view_settings.gamma=1
 s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth=C['png_depth'];s.render.image_settings.compression=20
def device(s):
 pref=bpy.context.preferences.addons['cycles'].preferences;errors=[]
 if not A.force_cpu:
  for backend in ['OPTIX','CUDA','HIP','ONEAPI','METAL']:
   try:
    pref.compute_device_type=backend;pref.refresh_devices();ds=[d for d in pref.devices if d.type==backend]
    if not ds:continue
    for d in pref.devices:d.use=d in ds
    s.cycles.device='GPU';return {'backend':backend,'devices':[d.name for d in ds],'attempt_errors':errors}
   except Exception as e:errors.append(backend+': '+str(e))
 s.cycles.device='CPU';return {'backend':'CPU','devices':['CPU'],'gpu_unavailable_or_forced':True,'attempt_errors':errors}
def png(p,deep=False):
 b=p.read_bytes()
 if b[:8]!=b'\x89PNG\r\n\x1a\n' or len(b)<50:raise ValueError('Invalid PNG '+str(p))
 w,h,depth,color=struct.unpack('>IIBB',b[16:26]);assert (w,h,depth,color)==(1920,1080,16,2),str(p)
 if b[-8:]!=b'IEND\xaeB`\x82':raise ValueError('Incomplete PNG '+str(p))
 if deep:
  at=8
  while at<len(b):
   n=struct.unpack_from('>I',b,at)[0];end=at+12+n
   if end>len(b):raise ValueError('Truncated PNG chunk')
   crc=struct.unpack_from('>I',b,at+8+n)[0]
   if zlib.crc32(b[at+4:at+8+n])&0xffffffff!=crc:raise ValueError('PNG CRC mismatch')
   at=end
  assert at==len(b)
 return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def file_for(f):return F/f'{f:05}.png'
def load_master():
 manifest=json.loads((R/'manifest.json').read_text(encoding='utf8'));expected=manifest['files'][C['project']]['sha256'];assert sha(SRC)==expected,'Project checksum mismatch'
 bpy.ops.wm.open_mainfile(filepath=str(SRC));s=bpy.context.scene;configure(s)
 assert not bpy.data.libraries and not bpy.utils.blend_paths(absolute=True,packed=False,local=True),'Missing external assets'
 assert not any(o.type=='FONT' and not o.hide_render for o in s.objects),'Rendered text found'
 assert not s.sequence_editor or not any(x.type=='TEXT' for x in s.sequence_editor.strips_all),'Caption strips found'
 return s,expected
def inspect(s,source_hash):
 dg=bpy.context.evaluated_depsgraph_get();native=[]
 for f in [1,193,229,289,385,1849,2737,2797,2821,2941,3097,4513,4705,4800]:
  s.frame_set(f);cams=[m for m in s.timeline_markers if m.camera and m.frame<=f];cam=max(cams,key=lambda m:m.frame).camera;s.camera=cam
  native.append({'frame':f,'camera':cam.name,'position':list(cam.evaluated_get(dg).matrix_world.translation),'season':s['innovation_season'],'fade':s['tour_season_fade']})
 s.frame_set(1);s.camera=bpy.data.objects['TOUR_A_Overview']
 r={'blender_version':bpy.app.version_string,'expected_version':C['blender_version'],'source_sha256':source_hash,'frame_range':[s.frame_start,s.frame_end],'fps':s.render.fps,'resolution':C['resolution'],'cuts':[(m.frame,m.camera.name) for m in s.timeline_markers if m.camera],'external_paths':[],'third_party_addons_required':False,'model_objects':len(s.objects),'native_checks':native,'free_gib':round(shutil.disk_usage(O).free/1024**3,2),'platform':sys.platform}
 assert bpy.app.version[:3]==tuple(map(int,C['blender_version'].split('.'))),'Use the pinned Blender version'
 write(O/'environment.json',r);return r
def encode():
 assert all(file_for(f).exists() for f in range(1,4801)),'Missing PNG frames'
 s=bpy.data.scenes.new('CleanEncoding');bpy.context.window.scene=s;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.fps=24;s.render.fps_base=1;s.frame_start=1;s.frame_end=4800;s.render.use_sequencer=True;s.render.use_compositing=False;s.render.use_motion_blur=False
 s.view_settings.view_transform='Standard';s.view_settings.look='None';s.view_settings.exposure=0;s.view_settings.gamma=1
 seq=s.sequence_editor_create().strips.new_image('Clean PNG animation',filepath=str(file_for(1)),channel=1,frame_start=1)
 for f in range(2,4801):seq.elements.append(file_for(f).name)
 s.render.image_settings.media_type='VIDEO';s.render.image_settings.file_format='FFMPEG';s.render.ffmpeg.format='MPEG4';s.render.ffmpeg.codec='H264';s.render.ffmpeg.constant_rate_factor='PERC_LOSSLESS';s.render.ffmpeg.ffmpeg_preset='GOOD';s.render.filepath=str(O/C['video'])
 bpy.ops.render.render(animation=True,scene=s.name);assert (O/C['video']).stat().st_size>10000
def validate_sequence(source_hash):
 expected={'source_sha256':source_hash,'settings':C,'blender_version':bpy.app.version_string}
 assert json.loads((O/'render_manifest.json').read_text(encoding='utf8'))==expected,'Wrong sequence source/settings'
 ix=O/'frames_index.json';index=json.loads(ix.read_text(encoding='utf8')) if ix.exists() else {}
 for f in range(1,4801):
  r=png(file_for(f),True)
  if str(f) in index:assert index[str(f)]==r,'Existing PNG hash mismatch: '+str(f)
  index[str(f)]=r
 write(ix,index)
def boxes(b):
 at=0
 while at+8<=len(b):
  n,t=struct.unpack_from('>I4s',b,at);head=8
  if n==1:n=struct.unpack_from('>Q',b,at+8)[0];head=16
  if n==0:n=len(b)-at
  if n<head or at+n>len(b):raise ValueError('Invalid MP4 box')
  yield t,b[at+head:at+n];at+=n
def verify(source_hash):
 b=(O/C['video']).read_bytes();moov=next(x for t,x in boxes(b) if t==b'moov');mv=next(x for t,x in boxes(moov) if t==b'mvhd')
 if mv[0]==0:scale,duration=struct.unpack_from('>II',mv,12)
 else:scale=struct.unpack_from('>I',mv,20)[0];duration=struct.unpack_from('>Q',mv,24)[0]
 assert abs(duration/scale-200)<.001,'Wrong duration'
 tr=next(x for t,x in boxes(moov) if t==b'trak');tk=next(x for t,x in boxes(tr) if t==b'tkhd');dims=tuple(round(x/65536) for x in struct.unpack_from('>II',tk,len(tk)-8));assert dims==(1920,1080)
 out=bpy.data.scenes.new('MovieVerification');bpy.context.window.scene=out;out.render.resolution_x=1920;out.render.resolution_y=1080;out.render.resolution_percentage=100;out.render.fps=24;out.render.use_sequencer=True;out.render.use_compositing=False;out.render.use_motion_blur=False;out.view_settings.view_transform='Standard';out.view_settings.look='None';out.view_settings.exposure=0
 st=out.sequence_editor_create().strips.new_movie('Actual encoded output',filepath=str(O/C['video']),channel=1,frame_start=1);assert st.frame_duration==4800
 checks=[1,121,385,1849,2790,2797,2821,2953,3097,4081,4537,4753,4800];out.render.image_settings.media_type='IMAGE';out.render.image_settings.file_format='PNG';(O/'decoded').mkdir(exist_ok=True)
 for f in checks:out.frame_set(f);out.render.filepath=str(O/'decoded'/f'{f:05}.png');bpy.ops.render.render(write_still=True)
 assert sha(SRC)==source_hash
 result={'duration_seconds':duration/scale,'fps':4800/(duration/scale),'frames':4800,'size':dims,'decoded_frames':checks,'source_unchanged':True,'source_sha256':source_hash,'video_bytes':len(b),'verified_utc':now()};write(O/'validation.json',result);return result
def main():
 status={'phase':'loading','mode':A.mode,'started_utc':now(),'pid':os.getpid(),'target_frames':4800,'fps':24,'duration_seconds':200,'size':[1920,1080]}
 def update(**k):status.update(k);status['elapsed_seconds']=round(time.monotonic()-START,2);write(O/'status.json',status)
 with lock():
  update()
  try:
   s,h=load_master();env=inspect(s,h);update(source_sha256=h)
   if A.mode=='inspect':update(phase='inspected');return
   if A.mode=='verify':verify(h);update(phase='verified');return
   if A.mode=='encode':update(phase='checking_sequence');validate_sequence(h);update(phase='encoding');encode();verify(h);update(phase='complete',video=str(O/C['video']),source_unchanged=True,completed_utc=now());return
   dev=device(s);env['device']=dev;write(O/'environment.json',env)
   if A.mode=='preflight':
    update(phase='preflight_rendering',device=dev);s.frame_set(1);s.render.filepath=str(O/'preflight.png');bpy.ops.render.render(write_still=True);png(O/'preflight.png',True)
    write(O/'preflight.json',{'passed':True,'source_sha256':h,'device':dev,'settings':C,'seconds':round(time.monotonic()-START,2),'verified_utc':now()});assert sha(SRC)==h;update(phase='preflight_passed');return
   pre=json.loads((O/'preflight.json').read_text(encoding='utf8'));assert pre['passed'] and pre['source_sha256']==h and pre['settings']==C,'Run preflight first'
   assert pre['device']['backend']==dev['backend'],'Device changed since preflight; rerun preflight'
   assert dev['backend']!='CPU' or A.force_cpu,'GPU unavailable: inspect/install driver, or use --force-cpu after verifying this machine has no supported GPU'
   manifest={'source_sha256':h,'settings':C,'blender_version':bpy.app.version_string};mp=O/'render_manifest.json'
   if mp.exists():assert json.loads(mp.read_text(encoding='utf8'))==manifest,'Refuse mixing settings/source versions'
   else:write(mp,manifest)
   ix=O/'frames_index.json';index=json.loads(ix.read_text(encoding='utf8')) if ix.exists() else {};todo=[];reused=0
   update(phase='checking_resume',device=dev)
   for f in range(1,4801):
    path=file_for(f)
    if path.exists():
     try:
      r=png(path,True);old=index.get(str(f))
      if old and old!=r:raise ValueError('Frame hash mismatch')
      index[str(f)]=r;reused+=1;continue
     except Exception:
      path.rename(path.with_name(path.name+'.invalid.'+str(int(time.time()))))
    todo.append(f)
   if todo and shutil.disk_usage(O).free < len(todo)*9*1024**2+12*1024**3:raise RuntimeError('Insufficient disk space: reserve about 9MiB per missing frame plus 12GiB; use another --output disk')
   write(ix,index);durations=[];update(phase='rendering',reused_frames=reused,rendered_frames=reused)
   for n,f in enumerate(todo):
    s.frame_set(f);s.render.filepath=str(file_for(f));a=time.monotonic();bpy.ops.render.render(write_still=True);durations.append(time.monotonic()-a);index[str(f)]=png(file_for(f),True);write(ix,index)
    avg=statistics.mean(durations[-12:]);update(phase='rendering',source_frame=f,rendered_frames=reused+n+1,mean_recent_frame_seconds=round(avg,3),remaining_estimate_seconds=round((len(todo)-n-1)*avg))
   update(phase='encoding',rendered_frames=4800,render_seconds=round(time.monotonic()-START,2));encode();update(phase='verifying');verify(h);assert sha(SRC)==h
   update(phase='complete',video=str(O/C['video']),source_unchanged=True,total_seconds=round(time.monotonic()-START,2),completed_utc=now())
  except Exception as e:update(phase='failed',error=repr(e));traceback.print_exc();raise
if __name__=='__main__':main()
