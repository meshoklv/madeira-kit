# parse.py <madeira-log.txt> <out.json>  - extract [xp]/[gpu-perf]/[smc]/... time series from a Madeira log into JSON
import re,sys,json,collections
L=sys.argv[1]; out=sys.argv[2]
T=None
rows=collections.defaultdict(list)
def ts(h,m,s): return int(h)*3600+int(m)*60+float(s)
rx_xp=re.compile(r'^\[xp\] (\d+):(\d+):([\d.]+) \+([\d.]+) dt=(\d+) cpu=(\d+) .*?P=(\d+) E=(\d+) run=(\d+).*GHz P=([\d.]+) E=([\d.]+) Minst=(\d+) IPC=([\d.]+) mJ=(\d+)')
rx_t=re.compile(r'^\[xp-t\] (\d+):(\d+):([\d.]+) (.*)')
rx_gp=re.compile(r'\[gpu-perf\] ml1254 64 frames in (\d+) ms \(([\d.]+) fps\): GPU busy (\d+) ms = (\d+)% .*draws/frame (\d+)')
rx_md=re.compile(r'^\[mach-deliver\] rev=\S+ #(\d+) code=(\w+) pc=(\w+) excaddr=\w+ addr=(\w+)')
rx_fr=re.compile(r'^\[fault_rip\] cnt=(\d+) rip=(\w+) pc=\w+ addr=(\w+) kr=(\d+)\((\w+)\)')
rx_smc=re.compile(r'\[smc\] ml1055 (\d+) self-modifying')
rx_un=re.compile(r'UNALIGNED-BACKPATCH #(\d+)')
rx_cr=re.compile(r'^E (\w+) \[callret\] ml610 resets=(\d+)')
rx_cb=re.compile(r'^E (\w+) \[CB_SUMMARY\] total=(\d+) real_compiles=(\d+)')
rx_hs=re.compile(r'^E (\w+) \[hot-smc\] stats (.*)')
rx_hs2=re.compile(r'^E (\w+) \[hot-smc\] v2 stats (.*)')
rx_ms=re.compile(r'^\[madsync\] ml1058 (\d+) waits \((\d+) slept')
rx_sc=re.compile(r'\[sync-census\] ml1115 .*server requests (\d+)/s, QPC syscalls (\d+)/s')
rx_api=re.compile(r'^\[xp-api\] (\d+):(\d+):([\d.]+) x64->EC (\d+)/s .*?EC->x64 (\d+)/s(?: \| CS contended (\d+)/s .*?wait ([\d.]+) ms/s)?')
rx_jp=re.compile(r'^\[jit-pool\] (tail \w+|.*?SHRINK.*|.*?reset.*|.*?flush.*)',re.I)
rx_db=re.compile(r'^\[srv-doorbell\] (\d+) passes/s')
rx_th=re.compile(r'\[thermal\] (\S+ -> \S+)')
cnt=collections.Counter()
with open(L,errors='replace') as f:
  for l in f:
    m=rx_xp.match(l)
    if m:
      T=ts(*m.group(1,2,3)); g=m.groups()
      rows['xp'].append((T,int(g[4]),int(g[5]),int(g[6]),int(g[7]),float(g[9]),float(g[10]),int(g[11]),float(g[12]),int(g[13]))); continue
    if T is None: continue
    if l.startswith('[xp-t]'):
      m=rx_t.match(l)
      if m:
        t=ts(*m.group(1,2,3))
        for e in m.group(4).split():
          p=e.split(':')
          if len(p)==4 and p[0].endswith('00ac'):
            pm,em=p[1].split('/'); gp,ge=p[2].split('/')
            rows['main'].append((t,int(pm),int(em),float(gp),float(ge),int(p[3])))
      continue
    m=rx_gp.search(l)
    if m: rows['gp'].append((T,int(m[1]),float(m[2]),int(m[3]),int(m[4]),int(m[5]))); continue
    m=rx_md.match(l)
    if m: rows['md'].append((T,int(m[1]),m[2],m[3],m[4])); continue
    m=rx_fr.match(l)
    if m: rows['fr'].append((T,int(m[1]),m[2],m[3],m[5])); continue
    m=rx_smc.search(l)
    if m: rows['smc'].append((T,int(m[1]))); continue
    m=rx_un.search(l)
    if m: rows['un'].append((T,int(m[1]))); continue
    m=rx_cr.match(l)
    if m: rows['cr'].append((T,m[1],int(m[2]))); continue
    m=rx_cb.match(l)
    if m: rows['cb'].append((T,m[1],int(m[2]),int(m[3]))); continue
    m=rx_hs.match(l)
    if m: rows['hs'].append((T,m[1],m[2])); continue
    m=rx_hs2.match(l)
    if m: rows['hs2'].append((T,m[1],m[2])); continue
    m=rx_ms.match(l)
    if m: rows['ms'].append((T,int(m[1]),int(m[2]))); continue
    m=rx_sc.search(l)
    if m: rows['sc'].append((T,int(m[1]),int(m[2]))); continue
    m=rx_api.match(l)
    if m: rows['api'].append((T,int(m[4]),int(m[5]),int(m[6] or 0),float(m[7] or 0))); continue
    m=rx_jp.match(l)
    if m: rows['jp'].append((T,l.strip()[:200])); continue
    m=rx_db.match(l)
    if m: rows['db'].append((T,int(m[1]))); continue
    m=rx_th.search(l)
    if m: rows['th'].append((T,m[1])); continue
    if 'Failed to mprotect last page' in l: rows['mpf'].append((T,l[2:6].strip())); continue
    if 'iOS-xrem' in l: cnt['xrem']+=1; rows['xrem'].append(T); continue
    if '[bc-stream]' in l: rows['bcs'].append(T); continue
    if l.startswith('[thread-stacks] ----'): rows['tsd'].append((T,l.strip())); continue
    if 'Handled self-modifying' in l or 'Handled inline self-mod' in l: rows['hsmc'].append(T); continue
json.dump(rows,open(out,'w'))
for k,v in rows.items(): print(k,len(v))
