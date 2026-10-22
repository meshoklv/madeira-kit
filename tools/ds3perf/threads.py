# threads.py <madeira-log.txt> <main-thread-id>  - per-thread busy time / frequency / instruction rate from [xp-t] lines
import re,sys,statistics as st,collections
L,main=sys.argv[1],sys.argv[2]
names={}
xp=[];T=None;dt=None
per=collections.defaultdict(list)  # tid -> (t, busy, ghz, minst/s)
gp=[]
rx=re.compile(r'^\[xp\] (\d+):(\d+):([\d.]+) \+[\d.]+ dt=(\d+)')
with open(L,errors='replace') as f:
  for l in f:
    if '[thr-name]' in l:
      m=re.search(r'tid=([0-9a-f]+).*name="([^"]*)"',l)
      if m: names[m[1]]=m[2]
      continue
    m=rx.match(l)
    if m: T=int(m[1])*3600+int(m[2])*60+float(m[3]); dt=int(m[4]); continue
    if l.startswith('[xp-t]') and dt:
      for e in l.split()[2:]:
        p=e.split(':')
        if len(p)==4 and '/' in p[1]:
          tid=p[0][1:] if p[0][0] in '-+' else p[0]
          pm,em=map(int,p[1].split('/'))
          per[tid].append((T,(pm+em)/dt, (pm, em), int(p[3])*1000/dt))
      continue
    m=re.search(r'\[gpu-perf\] ml1254 64 frames in (\d+) ms \(([\d.]+) fps\).*?= (\d+)%.*draws/frame (\d+)',l)
    if m and T: gp.append((T,float(m[2]),int(m[3]),int(m[4])))
heavy=[g for g in gp if g[3]>300]; hs=heavy[0][0]; end=gp[-1][0]
def ph(a,b,lab):
  g=[x for x in heavy if a<=x[0]<b]; fps=st.median(x[1] for x in g)
  print('==',lab,'fps %.1f frame %.1f ms'%(fps,1000/fps))
  rows=[]
  for tid,v in per.items():
    w=[x for x in v if a<=x[0]<b]
    if not w: continue
    # treat absent samples as ~0 -> use sum/len of all xp windows: approximate with mean over present * coverage
    busy=sum(x[1] for x in w)/max(1,len([1 for x in per[main] if a<=x[0]<b]))
    rows.append((busy,tid,st.median(x[3] for x in w)))
  rows.sort(reverse=True)
  for busy,tid,mi in rows[:12]: print('  %-5s %-28s busy %.0f%%  ms/frame %.1f  Minst/frame %.0f'%(tid,names.get(tid,'?')[:28],busy*100,busy*1000/fps,mi/fps))
ph(hs,hs+240,'first4min'); ph(hs+300,end,'after5min')
