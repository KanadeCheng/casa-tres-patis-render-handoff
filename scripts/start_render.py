"""Host Python 3.10+, stdlib only. Detect/install Blender and launch durable jobs."""
import argparse,hashlib,json,os,pathlib,platform,re,shutil,subprocess,sys,tarfile,urllib.request,zipfile
R=pathlib.Path(__file__).resolve().parents[1];RT=R/'.runtime';RT.mkdir(exist_ok=True)
C=json.loads((R/'config/render.json').read_text(encoding='utf8'))
BASE='https://download.blender.org/release/Blender5.2/'
HASHES={
 'blender-5.2.3-windows-x64.zip':'723f08a4401502561eb763cdeacf8745b31e5f3f154d287d3830d97cf75dc2fb',
 'blender-5.2.3-windows-arm64.zip':'a539e484b1200e4a2e463560eb1672b60de846850af0e867b52a08607b910698',
 'blender-5.2.3-linux-x64.tar.xz':'78486c018b4443efe5e75ab54c290ed8c15abafd249b862c2c9ce2530a918eec',
 'blender-5.2.3-macos-arm64.dmg':'acc05374485a272342d4b323c15ac01953e7f697da2f1bad8af9c3bf087267a4'}
def version(p):
 try:
  t=subprocess.check_output([str(p),'--version'],stderr=subprocess.STDOUT,text=True,timeout=30)
  return re.search(r'Blender (\d+\.\d+\.\d+)',t).group(1)
 except Exception:return None
def candidates():
 for k in ['BLENDER_BIN']:
  if os.environ.get(k):yield pathlib.Path(os.environ[k])
 q=shutil.which('blender')
 if q:yield pathlib.Path(q)
 for p in (RT/'blender').glob('**/blender.exe'):yield p
 for p in (RT/'blender').glob('**/blender'):yield p
 for root in [pathlib.Path(os.environ.get('LOCALAPPDATA','~')).expanduser()/'Programs/Blender Foundation',pathlib.Path('C:/Program Files/Blender Foundation')]:
  if root.exists():yield from root.glob('Blender */blender.exe')
 for p in ['/Applications/Blender.app/Contents/MacOS/Blender','/usr/bin/blender','/snap/bin/blender']:
  yield pathlib.Path(p)
def download_install():
 system=platform.system();arm=platform.machine().lower() in ['arm64','aarch64']
 if system=='Windows':name='blender-5.2.3-windows-'+('arm64' if arm else 'x64')+'.zip'
 elif system=='Linux' and not arm:name='blender-5.2.3-linux-x64.tar.xz'
 elif system=='Darwin' and arm:name='blender-5.2.3-macos-arm64.dmg'
 else:raise RuntimeError('No pinned official build for this OS/architecture. Read handoff environment section; do not silently use an older Blender.')
 target=RT/name
 if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=HASHES[name]:
  part=target.with_suffix(target.suffix+'.part');print('Downloading official Blender:',BASE+name,flush=True)
  urllib.request.urlretrieve(BASE+name,part)
  if hashlib.sha256(part.read_bytes()).hexdigest()!=HASHES[name]:raise RuntimeError('Official Blender archive checksum mismatch')
  part.replace(target)
 dest=RT/'blender';dest.mkdir(exist_ok=True)
 if name.endswith('.zip'):
  with zipfile.ZipFile(target) as z:
   for entry in z.infolist():
    if not (dest/entry.filename).resolve().is_relative_to(dest.resolve()):raise RuntimeError('Unsafe archive member')
   z.extractall(dest)
 elif name.endswith('.tar.xz'):
  with tarfile.open(target,'r:xz') as t:
   for e in t.getmembers():
    if not (dest/e.name).resolve().is_relative_to(dest.resolve()):raise RuntimeError('Unsafe archive member')
    if e.issym() or e.islnk():
     resolved=((dest/e.name).parent/e.linkname).resolve() if e.issym() else (dest/e.linkname).resolve()
     if not resolved.is_relative_to(dest.resolve()):raise RuntimeError('Unsafe archive link')
   t.extractall(dest)
 else:
  mount=RT/'dmg_mount';mount.mkdir(exist_ok=True)
  subprocess.run(['hdiutil','attach',str(target),'-nobrowse','-readonly','-mountpoint',str(mount)],check=True)
  try:subprocess.run(['ditto',str(mount/'Blender.app'),str(dest/'Blender.app')],check=True)
  finally:subprocess.run(['hdiutil','detach',str(mount)],check=True)
 if system=='Darwin':return dest/'Blender.app/Contents/MacOS/Blender'
 exe='blender.exe' if system=='Windows' else 'blender'
 return next(dest.rglob(exe))
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['inspect','preflight','render','encode','verify'],default='render');p.add_argument('--blender');p.add_argument('--output',type=pathlib.Path);p.add_argument('--foreground',action='store_true');p.add_argument('--force-cpu',action='store_true');a=p.parse_args()
 binary=pathlib.Path(a.blender) if a.blender else next((b for b in candidates() if b.is_file() and version(b)==C['blender_version']),None)
 if binary and version(binary)!=C['blender_version']:raise RuntimeError('Explicit Blender must be '+C['blender_version'])
 if not binary:binary=download_install()
 assert version(binary)==C['blender_version']
 settings=RT/'local_settings.json';previous=json.loads(settings.read_text(encoding='utf8')) if settings.exists() else {}
 output=(a.output or pathlib.Path(previous.get('output',str(R/'output')))).resolve();output.mkdir(parents=True,exist_ok=True)
 settings.write_text(json.dumps({'blender':str(binary),'output':str(output)},indent=2),encoding='utf8')
 command=[str(binary),'--background','--factory-startup','--enable-autoexec','--python-exit-code','1','--python',str(R/'scripts/render.py'),'--','--mode',a.mode,'--output',str(output)]
 if a.force_cpu:command.append('--force-cpu')
 if a.foreground:return subprocess.call(command)
 stdout=open(output/(a.mode+'.log'),'ab');stderr=open(output/(a.mode+'_error.log'),'ab')
 kw={'stdin':subprocess.DEVNULL,'stdout':stdout,'stderr':stderr,'cwd':str(R),'close_fds':True}
 if os.name=='nt':kw['creationflags']=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP
 else:kw['start_new_session']=True
 job=subprocess.Popen(command,**kw);stdout.close();stderr.close()
 record={'pid':job.pid,'mode':a.mode,'output':str(output),'command':command};(RT/'job.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(record,ensure_ascii=True,indent=2));return 0
if __name__=='__main__':sys.exit(main())
