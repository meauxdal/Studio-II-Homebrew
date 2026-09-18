from pathlib import Path
import subprocess
import re

ROOT = Path(__file__).resolve().parents[1]

class CPU:
    """Instruction-level check only; no raster or interrupt timing model."""
    def __init__(self, rom, bios):
        self.m = bytearray(65536)
        self.m[:len(bios)] = bios
        assert rom[:4] == b'RCA2'
        for i in range(rom[4]-1):
            a = rom[64+i]*256
            self.m[a:a+256] = rom[256*(i+1):256*(i+2)]
        self.r = [0]*16
        self.p, self.x, self.d, self.df = 3, 0, 0, 0
        self.writes = []
        self.ops = []
    def fetch(self):
        a = self.r[self.p]
        self.r[self.p] = (a+1)&65535
        return self.m[a]
    def store(self, a, v):
        self.m[a] = v
        self.writes.append((a,v))
    def step(self):
        op = self.fetch(); h,n = op>>4, op&15
        self.ops.append(op)
        r,m = self.r,self.m
        if h == 0 and n: self.d=m[r[n]]
        elif h == 1: r[n]=(r[n]+1)&65535
        elif h == 2: r[n]=(r[n]-1)&65535
        elif h == 3:
            a=r[self.p]; v=self.fetch()
            take={0:True,2:self.d==0,3:self.df==1,8:False,10:self.d!=0,11:self.df==0}[n]
            if take: r[self.p]=(a&0xff00)|v
        elif h == 4: self.d=m[r[n]]; r[n]=(r[n]+1)&65535
        elif h == 5: self.store(r[n],self.d)
        elif h == 6 and 1<=n<=7: r[self.x]=(r[self.x]+1)&65535
        elif op == 0x73: self.store(r[self.x],self.d); r[self.x]=(r[self.x]-1)&65535
        elif op == 0x7e:
            v=self.d*2+self.df; self.d=v&255; self.df=int(v>255)
        elif op == 0x76:
            v=self.d; self.d=(v>>1)|(self.df<<7); self.df=v&1
        elif h == 8: self.d=r[n]&255
        elif h == 9: self.d=r[n]>>8
        elif h == 10: r[n]=(r[n]&0xff00)|self.d
        elif h == 11: r[n]=(r[n]&255)|(self.d<<8)
        elif h == 12:
            a=self.fetch()*256+self.fetch()
            take={0:True,2:self.d==0,10:self.d!=0}[n]
            if take: r[self.p]=a
        elif h == 13: self.p=n
        elif h == 14: self.x=n
        elif h == 15:
            if n in (6,14):
                old=self.d
                self.d=(old>>1) if n==6 else (old<<1)&255
                self.df=(old&1) if n==6 else (old>>7)
            else:
                v=self.fetch() if n>=8 else m[r[self.x]]
                k=n&7
                if k==0: self.d=v
                elif k==1: self.d|=v
                elif k==2: self.d&=v
                elif k==3: self.d^=v
                else:
                    result=self.d+v if k==4 else v-self.d if k==5 else self.d-v
                    self.df=int(result>255) if k==4 else int(result>=0)
                    self.d=result&255
        else: raise AssertionError(f'unsupported {op:02x} at {(r[self.p]-1):04x}')
    def run(self, entry, stop):
        self.r[3]=entry
        for i in range(100000):
            if self.r[self.p]==stop: return i
            self.step()
        raise AssertionError('routine did not return')

def original(path, revision='197ba8f'):
    return subprocess.check_output(['git','show',f'{revision}:{path}'],cwd=ROOT)

def symbols(path):
    return {label:int(addr,16) for label,addr in re.findall(r'\b([A-Z_][A-Z_0-9]*)\s+([0-9A-F]{4})\b',path.read_text())}

def hockey(bios, folder='HockeyVisicom', revision='197ba8f'):
    path='Games/HockeyVisicom/hockey.st2'
    old,new=original(path,revision),(ROOT/'Games'/folder/'hockey.st2').read_bytes()
    sy=symbols(ROOT/'Games'/folder/'hockey.asm.lst')
    cases=0
    for game in range(4):
      for height in (3,5):
       for scores in ((0,0),(1,9),(9,8)):
        for serve in (6,56):
         cpus=[]
         for rom in (old,new):
            c=CPU(rom,bios)
            c.r[2]=0x10ff; c.r[15]=0x1002; c.r[10]=0x10cd
            c.r[7]=sy['JUMP']
            c.m[0x1000:0x1004]=bytes((*scores,game,height))
            c.m[0x1010]=serve
            # Arbitrary old pixels must not survive the reset.
            c.m[0x1100:0x1200]=bytes(range(256))
            c.m[0x1300:0x1400]=bytes(reversed(range(256)))
            c.run(sy['NEWPOINT'],sy['_WAIT0'])
            cpus.append(c)
         a,b=cpus
         assert a.m[0x1100:0x1200]==b.m[0x1100:0x1200],(game,height,scores,serve,'plane0')
         assert a.m[0x1300:0x1400]==b.m[0x1300:0x1400],(game,height,scores,serve,'plane1')
         assert a.m[0x1000:0x1014]==b.m[0x1000:0x1014],(game,height,scores,serve,'state')
         assert not any(op>>4==12 for op in b.ops),'three-cycle instruction in reset'
         cases+=1
    print(f'{folder}: {cases} reset cases, identical final planes/state; no three-cycle instructions')
    for flag in (0,0x4000,0x8000):
     for d in range(256):
      for df in (0,1):
        c=CPU(new,bios); c.p=7; c.r[7]=sy['JUMP']; c.r[2]=0x10ff
        c.d=d; c.df=df; c.x=11
        target=0x900|flag
        c.m[0x2000:0x2002]=target.to_bytes(2,'big')
        take=flag==0 or (flag==0x8000 and d==0) or (flag==0x4000 and d!=0)
        c.run(0x2000,0x900 if take else 0x2002)
        assert (c.d,c.df,c.x,c.r[2])==(d,df,11,0x10ff)
    print(f'{folder}: 1536 unconditional/conditional jump cases preserve D, DF, X and stack')

def pacman(bios):
    path='Games/PacmanVisicom/pacman.st2'
    old,new=original(path),(ROOT/path).read_bytes()
    cases=0
    for graphic in range(0x40,0x70,4):
     for x in range(8):
      for y in (0,12,25):
       cpus=[]
       for rom in (old,new):
        c=CPU(rom,bios); c.p=5; c.r[5]=0x906; c.r[4]=0x2000
        c.r[2]=0x10ff; c.r[13]=(y<<8)|x; c.d=graphic
        c.m[0x1100:0x1200]=bytes(range(256))
        c.m[0x1300:0x1400]=bytes(reversed(range(256)))
        c.run(0,0x2000)
        assert (c.d,c.r[2],c.r[13])==(graphic,0x10ff,(y<<8)|x)
        cpus.append(c)
       a,b=cpus
       assert a.m[0x1100:0x1400]==b.m[0x1100:0x1400]
       for c in cpus:
        c.p=5                         # exercise the reentrant return path too
        c.run(0,0x2000)
       assert a.m[0x1100:0x1400]==b.m[0x1100:0x1400]
       assert b.m[0x1100:0x1200]==bytes(range(256))
       assert b.m[0x1300:0x1400]==bytes(reversed(range(256)))
       assert not any(op>>4==12 for op in b.ops)
       cases+=1
    print(f'Pacman: {cases} sprite draw/erase cases match both original planes; no three-cycle instructions')

def invaders():
    path='Games/Invaders/invaders.st2'
    a,b=original(path),(ROOT/path).read_bytes()
    differences=[i for i in range(len(a)) if a[i]!=b[i]]
    assert len(differences)==8
    assert all(a[i]==7 and b[i]==5 for i in differences)
    c=CPU(b,b'')
    c.run(0xa00,0x45d)
    for y in range(8,13):
        for x in range(2,7): assert c.m[0xb00+(y//4)*8+x]==5
    print('Invaders: exactly eight white-to-yellow table bytes changed; all five score digits covered')

if __name__=='__main__':
    import sys
    hockey(Path(sys.argv[1]).read_bytes())
    hockey(Path(sys.argv[1]).read_bytes(),'HockeyVisicomV1','0fb2e25')
    pacman(Path(sys.argv[1]).read_bytes())
    invaders()
