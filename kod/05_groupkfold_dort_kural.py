"""Aşama 3 / Adım 3: kişi bazlı GroupKFold ile 2x2 eşik kuralları."""
from pathlib import Path
import os
import csv,json
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.metrics import balanced_accuracy_score,f1_score

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'veri').mkdir(exist_ok=True)
(ROOT/'ciktilar').mkdir(exist_ok=True)
rows=list(csv.DictReader((ROOT/'veri/04_asama3_dakika_ozellikleri.csv').open()))
for r in rows:
    r['person_group']=int(r['person_group']);r['minute']=int(r['minute'])
    for k in ('sdnn_ms','ln_sdnn_rmssd'):
        try:r[k]=float(r[k])
        except:r[k]=np.nan

def counts(y,p):
    y=np.asarray(y,bool);p=np.asarray(p,bool)
    return int(np.sum(y&p)),int(np.sum(y&~p)),int(np.sum(~y&~p)),int(np.sum(~y&p))
def BA(y,p):
    tp,fn,tn,fp=counts(y,p);return (tp/(tp+fn)+tn/(tn+fp))/2

def person_bootstrap(y,p,g,B=1000,seed=0):
    rng=np.random.default_rng(seed);people=np.unique(g);bas=[];f1=[]
    idx={z:np.flatnonzero(g==z) for z in people}
    for _ in range(B):
        chosen=rng.choice(people,len(people),replace=True)
        ii=np.concatenate([idx[z] for z in chosen])
        bas.append(balanced_accuracy_score(y[ii],p[ii]));f1.append(f1_score(y[ii],p[ii],zero_division=0))
    return [float(x) for x in np.percentile(bas,[2.5,97.5])],[float(x) for x in np.percentile(f1,[2.5,97.5])]

all_results=[];fold_rows=[]
for pipeline in ('ham','suz'):
    data=[r for r in rows if r['pipeline']==pipeline]
    y=np.array([r['label']=='A' for r in data]);g=np.array([r['person_group'] for r in data]);dummy=np.zeros((len(data),1))
    folds=list(GroupKFold(n_splits=5).split(dummy,y,g))
    # Aynı katlar her özellik için korunur.
    for feature,name in (('sdnn_ms','SDNN'),('ln_sdnn_rmssd','ln(SDNN/RMSSD)')):
        x=np.array([r[feature] for r in data]);oof=np.zeros(len(data),bool);seen=np.zeros(len(data),bool);thresholds=[]
        for fold,(tr,te) in enumerate(folds,1):
            v=x[tr];candidates=np.nanpercentile(v,np.arange(1,100))
            best_t=None;best_ba=-np.inf
            for T in candidates:
                score=BA(y[tr],v>T) # NaN > T False
                if score>best_ba:best_ba=score;best_t=float(T)
            oof[te]=x[te]>best_t;seen[te]=True;thresholds.append(best_t)
            train_people=set(g[tr]);test_people=set(g[te])
            if train_people & test_people:raise AssertionError('Kişi sızıntısı')
            fold_rows.append({'pipeline':pipeline,'feature':feature,'fold':fold,'T':best_t,
                              'train_people':len(train_people),'test_people':len(test_people),
                              'train_minutes':len(tr),'test_minutes':len(te)})
        assert seen.all()
        ba=balanced_accuracy_score(y,oof);f1=f1_score(y,oof,zero_division=0);tp,fn,tn,fp=counts(y,oof)
        ba_ci,f1_ci=person_bootstrap(y,oof,g)
        all_results.append({'pipeline':pipeline,'feature':feature,'feature_name':name,
            'BA':float(ba),'F1':float(f1),'BA_CI95':ba_ci,'F1_CI95':f1_ci,
            'invalid_minutes':int(np.isnan(x).sum()),'thresholds':thresholds,
            'TP':tp,'FN':fn,'TN':tn,'FP':fp})

(ROOT/'veri/05_dort_kural_sonuclari.json').write_text(json.dumps(all_results,ensure_ascii=False,indent=2),encoding='utf-8')
with (ROOT/'veri/05_groupkfold_esikleri.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(fold_rows[0]));w.writeheader();w.writerows(fold_rows)
for r in all_results:
    print(f"{r['pipeline']:3s} | {r['feature_name']:16s} | BA={r['BA']:.4f} %95GA={r['BA_CI95']} | F1={r['F1']:.4f} %95GA={r['F1_CI95']} | geçersiz={r['invalid_minutes']}")
