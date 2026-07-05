"""V6 Micro train using preprocessed NPZ directly"""
import numpy as np, time, json, os, sys, warnings
warnings.filterwarnings('ignore')
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

def _cs(c): return (c//5, c%5)

def rps_score(y_t, y_p):
    rps=0.0
    for i in range(len(y_t)):
        ah,aa=_cs(y_t[i])
        ar=0 if ah>aa else 1 if ah==aa else 2
        p=y_p[i]
        cp=[sum(p[h*5+a] for h in range(5) for a in range(5) if h>a),
            sum(p[h*5+h] for h in range(5)),
            sum(p[h*5+a] for h in range(5) for a in range(5) if a>h)]
        ca=[1.0,0,0] if ar==0 else [0,1.0,0] if ar==1 else [0,0,1.0]
        rps+=float(np.mean((np.cumsum(ca)-np.cumsum(cp))**2))
    return rps/len(y_t)

class LS(nn.Module):
    def __init__(self, sm=0.1, gm=2.0):
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

try:
    MODEL_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),'models')
except NameError:
    MODEL_DIR=os.path.join(os.getcwd(),'models')

print('Loading preprocessed data...')
d=np.load(os.path.join(MODEL_DIR,'v5_preprocessed.npz'),allow_pickle=True)
X,y=d['X'],d['y']
X=X[-200000:];y=y[-200000:]
n=len(X);sp=int(n*0.80)
print(f'{n} samples ({sp} train, {n-sp} test)')

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
sch=optim.lr_scheduler.CosineAnnealingLR(opt,T_max=50,eta_min=1e-5)

print('Training 30 epochs...')
t0=time.time();best=0
for ep in range(30):
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
    if (ep+1)%5==0:print(f'ep {ep+1}: val={ve:.2f}% best={best:.2f}% rps={vr:.4f}')

with torch.no_grad():
    tp=torch.softmax(model(torch.tensor(X_te,dtype=torch.float32)),dim=1).numpy()
tc=np.argmax(tp,1)
te=float(np.mean(tc==y[sp:]))*100
t1x2=float(np.mean(
    np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in tc]])==
    np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in y[sp:]]])
))*100
tr=rps_score(y[sp:],tp)
print(f'\n=== RESULT ===')
print(f'Exact: {te:.2f}%')
print(f'1X2: {t1x2:.2f}%')
print(f'RPS: {tr:.4f}')
print(f'Time: {time.time()-t0:.0f}s')

np.save(os.path.join(MODEL_DIR,'v6_micro_probas.npy'),tp)
torch.save(model.state_dict(),os.path.join(MODEL_DIR,'v6_micro.pt'))
json.dump({'exact':round(te,2),'1x2':round(t1x2,2),'rps':round(tr,4)},
          open(os.path.join(MODEL_DIR,'v6_micro_results.json'),'w'),indent=2)
print('Saved!')
