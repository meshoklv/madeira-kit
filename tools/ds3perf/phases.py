# phases.py <parsed.json>  - split a run into phases (menu / loading / heavy scenes) and print medians
import json,sys,statistics as st,bisect
R=json.load(open(sys.argv[1]))
gp=R['gp']; xp=R['xp']
t0=xp[0][0]
heavy=[g for g in gp if g[5]>300]
print('run span s', xp[-1][0]-t0, 'gpu windows',len(gp),'heavy',len(heavy))
if heavy:
  hs=heavy[0][0]
  print('first heavy at +%.0f s'%(hs-t0))
def series(name,ti=0,vi=1,filt=None):
  s=[(r[ti],r[vi]) for r in R.get(name,[]) if (filt is None or filt(r))]
  s.sort(); return s
def rate(s,a,b):
  pre=[p[1] for p in s if p[0]<a]; ins=[p[1] for p in s if a<=p[0]<b]
  if not ins or not pre: return float('nan')
  hi=max(ins); lo=max(pre)
  last=max(p[0] for p in s if a<=p[0]<b); first=max(p[0] for p in s if p[0]<a)
  return (hi-lo)/(last-first) if last>first and hi>=lo else float('nan')
counters={'mach-deliver(AV to guest)':series('md'),'fault_rip cnt':series('fr'),'smc writes':series('smc'),'unaligned':series('un'),
 'callret resets (all)':series('cr',0,2),'real_compiles':series('cb',0,3),'CB total lookups':series('cb',0,2),
 'madsync waits':series('ms'),'madsync slept':series('ms',0,2)}
def phase(a,b,label):
  g=[x for x in gp if a<=x[0]<=b and x[5]>300]
  print('\n==',label,'+%.0f..+%.0f'%(a-t0,b-t0),'heavy windows',len(g))
  if g:
    print(' fps median %.1f  p10 %.1f  GPU%% %d  draws %d'%(st.median(x[2] for x in g), sorted(x[2] for x in g)[len(g)//10], st.median(x[4] for x in g), st.median(x[5] for x in g)))
  fps=st.median(x[2] for x in g) if g else None
  x=[r for r in xp if a<=r[0]<=b]
  if x: print(' proc: GHz P %.2f E %.2f, cpu ms/s %.0f, IPC %.2f, W %.2f'%(st.median(r[5] for r in x),st.median(r[6] for r in x),st.median(r[2]/r[1]*1000 for r in x),st.median(r[8] for r in x),st.median(r[9]/r[1] for r in x)))
  m=[r for r in R.get('main',[]) if a<=r[0]<=b]
  if m:
    # need dt: approx 250-300; use xp dt matched
    dts={round(r[0],1):r[1] for r in xp}
    busy=[];mi=[];gh=[]
    for r in m:
      dt=dts.get(round(r[0],1))
      if dt: busy.append((r[1]+r[2])/dt); mi.append(r[5]/dt*1000)
      gh.append(r[3])
    print(' main 00ac: busy %.0f%% of core, P GHz %.2f, Minst/s %.0f'%(100*st.median(busy),st.median(gh),st.median(mi)), ' Minst/frame %.0f'%(st.median(mi)/fps) if fps else '')
  for k,s in counters.items():
    r=rate(s,a,b)
    if r is not None: print(' %-26s %8.0f /s'%(k,r), ' %.1f /frame'%(r/fps) if fps else '')
  for k in ['api']:
    a2=[r for r in R.get(k,[]) if a<=r[0]<=b and r[1]>0]
    if a2: print(' x64->EC %.0f/s EC->x64 %.0f/s CS contended %.0f/s CS wait %.1f ms/s'%tuple(st.median(r[i] for r in a2) for i in (1,2,3,4)))
  sc=[r for r in R.get('sc',[]) if a<=r[0]<=b]
  if sc: print(' sync-census server requests/s median %d (QPC syscalls %d)'%(st.median(r[1] for r in sc),st.median(r[2] for r in sc)))
  for k in ['mpf','xrem','bcs','hsmc']:
    n=[r for r in R.get(k,[]) if a<= (r[0] if isinstance(r,list) else r) <=b]
    print(' %s lines %.2f/s'%(k,len(n)/(b-a)))
  j=[r for r in R.get('jp',[]) if a<=r[0]<=b]
  for r in j: print('  jit-pool +%.0f %s'%(r[0]-t0,r[1][:110]))
  for r in R.get('th',[]):
    if a<=r[0]<=b: print('  thermal +%.0f %s'%(r[0]-t0,r[1]))
end=xp[-1][0]
if heavy:
  phase(hs,end,'ALL gameplay')
  phase(hs,hs+240,'first 4 min')
  phase(hs+300,end,'after 5 min')
