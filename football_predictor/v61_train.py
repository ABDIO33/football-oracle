"""
V6.1 Trainer — 200K matches, 50 epochs, M5_deep
"""
import numpy as np, time, json, os, sys, warnings, sqlite3
warnings.filterwarnings('ignore')
_BASE = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor'
sys.path.insert(0, _BASE)
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

MODEL_DIR = os.path.join(_BASE, 'models')

def log(m): print(f'[{time.strftime("%H:%M:%S")}] {m}', flush=True)
def _cs(c): return (c//5, c%5)

def rps_score(yt, yp):
    r=0.0
    for i in range(len(yt)):
        ah,aa=_cs(yt[i]); ar=0 if ah>aa else 1 if ah==aa else 2
        p=yp[i]
        cp=[sum(p[h*5+a] for h in range(5) for a in range(5) if h>a),
            sum(p[h*5+h] for h in range(5)),
            sum(p[h*5+a] for h in range(5) for a in range(5) if a>h)]
        ca=[1.,0,0] if ar==0 else [0,1.,0] if ar==1 else [0,0,1.]
        r+=float(np.mean((np.cumsum(ca)-np.cumsum(cp))**2))
    return r/len(yt)

class LS(nn.Module):
    def __init__(self,sm=0.1,gm=2.0):
        super().__init__();self.sm=sm;self.gm=gm
    def forward(self,i,t):
        nc=i.size(1)
        with torch.no_grad():
            s=torch.full_like(i,self.sm/(nc-1))
            s.scatter_(1,t.unsqueeze(1),1.0-self.sm)
        l=-(s*nn.functional.log_softmax(i,dim=1)).sum(dim=1)
        if self.gm>0:
            p=torch.softmax(i,dim=1).gather(1,t.unsqueeze(1)).squeeze()
            l*=((1-p)**self.gm)
        return l.mean()

class M5(nn.Module):
    def __init__(self,d,nc,layers,dr=0.25):
        super().__init__()
        m=[];p=d
        for i,sz in enumerate(layers):
            m+=[nn.Linear(p,sz)]
            if sz>=64:m+=[nn.BatchNorm1d(sz)]
            m+=[nn.ELU(),nn.Dropout(dr*(0.5 if i==len(layers)-1 else 1.0))]
            p=sz
        m+=[nn.Linear(p,nc)]
        self.net=nn.Sequential(*m)
    def forward(self,x):return self.net(x)

log('V6.1 TRAIN - 200K matches, 50 epochs')
n_epochs = 80

data=np.load(os.path.join(MODEL_DIR,'v5_preprocessed.npz'),allow_pickle=True)
X,y=data['X'],data['y']
X=X[-500000:];y=y[-500000:]
n=len(X);sp=int(n*0.80)
log(f'{n} samples ({sp} train, {n-sp} test)')

imp=SimpleImputer(strategy='median')
sc=StandardScaler()
X_tr=imp.fit_transform(X[:sp]);X_te=imp.transform(X[sp:])
X_ts=sc.fit_transform(X_tr);X_te=sc.transform(X_te)

tds=TensorDataset(torch.tensor(X_ts,dtype=torch.float32),torch.tensor(y[:sp],dtype=torch.long))
vds=TensorDataset(torch.tensor(X_te,dtype=torch.float32),torch.tensor(y[sp:],dtype=torch.long))
tl=DataLoader(tds,256,shuffle=True)
vl=DataLoader(vds,512)

model=M5(X_ts.shape[1],25,[256,512,256,128])
crit=LS(sm=0.1,gm=2.0)
opt=optim.AdamW(model.parameters(),lr=0.001,weight_decay=1e-5)
sch=optim.lr_scheduler.CosineAnnealingLR(opt,T_max=n_epochs,eta_min=1e-5)

log('M5_deep training...')
t0=time.time();best=0.0
for ep in range(n_epochs):
    model.train()
    for xb,yb in tl:
        opt.zero_grad();crit(model(xb),yb).backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step()
    model.eval();ap,at=[],[]
    with torch.no_grad():
        for xb,yb in vl:
            ap.append(torch.softmax(model(xb),dim=1).numpy());at.append(yb.numpy())
    ap=np.concatenate(ap);at_=np.concatenate(at)
    ve=float(np.mean(np.argmax(ap,1)==at_))*100
    vr=rps_score(at_,ap)
    sch.step()
    if ve>best:best=ve
    if (ep+1)%5==0:log(f'ep{ep+1}: val={ve:.2f}% best={best:.2f}% rps={vr:.4f}')

with torch.no_grad():
    tp=torch.softmax(model(torch.tensor(X_te,dtype=torch.float32)),dim=1).numpy()
tc=np.argmax(tp,1)
te=float(np.mean(tc==y[sp:]))*100
t1x2=float(np.mean(
    np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in tc]])==
    np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in y[sp:]]])
))*100
tr=rps_score(y[sp:],tp)
elapsed=time.time()-t0

log(f'')
log(f'=== V6.1 RESULT (200K matches, {n_epochs} ep) ===')
log(f'Exact: {te:.2f}%')
log(f'1X2: {t1x2:.2f}%')
log(f'RPS: {tr:.4f}')
log(f'Time: {elapsed:.0f}s ({elapsed/60:.1f}min)')

np.save(os.path.join(MODEL_DIR,'v61_probas.npy'),tp)
torch.save(model.state_dict(),os.path.join(MODEL_DIR,'v61_model.pt'))
json.dump({'exact':round(te,2),'1x2':round(t1x2,2),'rps':round(tr,4),'time':round(elapsed)},
          open(os.path.join(MODEL_DIR,'v61_results.json'),'w'),indent=2)
log('Saved!')
