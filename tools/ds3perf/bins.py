# bins.py <parsed.json> [bin_seconds=60]  - per-minute bins of FPS / CPU frequency / counters (input: parse.py output)
import json,sys,statistics as st
R=json.load(open(sys.argv[1])); B=int(sys.argv[2]) if len(sys.argv)>2 else 60
xp=R['xp']; t0=xp[0][0]; end=xp[-1][0]
dts={round(r[0],1):r[1] for r in xp}
def cum(name,vi):
  s=sorted((r[0],r[vi]) for r in R[name]); return s
def rate_bin(s,a,b):
  pre=[p[1] for p in s if p[0]<a]; ins=[p[1] for p in s if a<=p[0]<b]
  if not ins or not pre: return float('nan')
  hi=max(ins); lo=max(pre)
  last=max(p[0] for p in s if a<=p[0]<b); first=max(p[0] for p in s if p[0]<a)
  return (hi-lo)/(last-first) if last>first and hi>=lo else float('nan')
S={'comp':cum('cb',3),'look':cum('cb',2),'av':cum('fr',1),'md':cum('md',1),'smc':cum('smc',1),'cr':cum('cr',2)}
print(' t   fps  gpu%  draws  GHzP  mainbusy mainMinst/s Minst/f  comp/s comp/f  look/f  AV/s deliv/s smc/s callret/s xrem/s')
t=t0
while t<end:
  a,b=t,t+B
  g=[x for x in R['gp'] if a<=x[0]<b and x[5]>300]
  m=[r for r in R['main'] if a<=r[0]<b and dts.get(round(r[0],1))]
  x=[r for r in xp if a<=r[0]<b]
  fps=st.median(v[2] for v in g) if g else float('nan')
  busy=st.median((r[1]+r[2])/dts[round(r[0],1)] for r in m) if m else float('nan')
  mi=st.median(r[5]/dts[round(r[0],1)]*1000 for r in m) if m else float('nan')
  r={k:rate_bin(v,a,b) for k,v in S.items()}
  xr=sum(1 for v in R['xrem'] if a<=v<b)/B
  print('%4d %5.1f %4.0f %5.0f %5.2f %6.0f%% %8.0f %6.0f %8.0f %6.0f %7.0f %5.0f %5.0f %5.0f %6.0f %6.1f'%(a-t0,fps,st.median(v[4] for v in g) if g else float('nan'),st.median(v[5] for v in g) if g else float('nan'),st.median(v[5] for v in x) if x else 0,busy*100,mi,mi/fps,r['comp'],r['comp']/fps,r['look']/fps,r['av'],r['md'],r['smc'],r['cr'],xr))
  t+=B
