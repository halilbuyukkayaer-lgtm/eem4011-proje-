"""Aşama 3 / Adım 4: aynı kişi katlarında üç lojistik regresyon özellik seti."""
from pathlib import Path
import os
import csv,json
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score,f1_score

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'veri').mkdir(exist_ok=True)
(ROOT/'ciktilar').mkdir(exist_ok=True)
rows=[r for r in csv.DictReader((ROOT/'veri/04_asama3_dakika_ozellikleri.csv').open()) if r['pipeline']=='suz']
keys=('mean_rr_ms','rmssd_ms','r_amplitude_std','sdnn_ms','ln_sdnn_rmssd')
for r in rows:
    r['person_group']=int(r['person_group'])
    for k in keys:
        try:r[k]=float(r[k])
        except:r[k]=np.nan
# Kat haritasını tam süzülmüş dakika tablosunda kur: eşik deneyindeki katların aynısı.
g_all=np.array([r['person_group'] for r in rows]);y_all=np.array([r['label']=='A' for r in rows]);dummy=np.zeros((len(rows),1))
person_fold={}
for fold,(_,te) in enumerate(GroupKFold(n_splits=5).split(dummy,y_all,g_all),1):
    for person in np.unique(g_all[te]):person_fold[int(person)]=fold
if len(person_fold)!=24:raise AssertionError('24 kişinin tamamına kat atanmadı')
# Üç model aynı dakikalarla karşılaştırılsın.
valid=np.array([all(np.isfinite(r[k]) for k in keys) for r in rows])
data=[r for r,ok in zip(rows,valid) if ok]
y=np.array([r['label']=='A' for r in data]);g=np.array([r['person_group'] for r in data]);record=np.array([r['record'] for r in data]);fold_id=np.array([person_fold[z] for z in g])

def ci_person(y,p,g,B=1000,seed=0):
    rng=np.random.default_rng(seed);people=np.unique(g);idx={z:np.flatnonzero(g==z) for z in people};ba=[];f1=[]
    for _ in range(B):
        ii=np.concatenate([idx[z] for z in rng.choice(people,len(people),replace=True)])
        ba.append(balanced_accuracy_score(y[ii],p[ii]));f1.append(f1_score(y[ii],p[ii],zero_division=0))
    return [float(x) for x in np.percentile(ba,[2.5,97.5])],[float(x) for x in np.percentile(f1,[2.5,97.5])]

def four(y,p):
    return int(np.sum(y&p)),int(np.sum(y&~p)),int(np.sum(~y&~p)),int(np.sum(~y&p))
sets=[('Temel 3',['mean_rr_ms','rmssd_ms','r_amplitude_std']),
      ('Temel 3 + SDNN',['mean_rr_ms','rmssd_ms','r_amplitude_std','sdnn_ms']),
      ('Temel 3 + SDNN + ln oran',['mean_rr_ms','rmssd_ms','r_amplitude_std','sdnn_ms','ln_sdnn_rmssd'])]
results=[];final_pred=None
for name,features in sets:
    X=np.array([[r[k] for k in features] for r in data],float);oof=np.zeros(len(data),bool)
    for fold in range(1,6):
        tr=fold_id!=fold;te=fold_id==fold
        if set(g[tr])&set(g[te]):raise AssertionError('Kişi sızıntısı')
        model=Pipeline([('standardscaler',StandardScaler()),
                        ('logisticregression',LogisticRegression(max_iter=1000,class_weight='balanced'))])
        model.fit(X[tr],y[tr]);oof[te]=model.predict(X[te])
    ba=float(balanced_accuracy_score(y,oof));f1=float(f1_score(y,oof,zero_division=0));baci,f1ci=ci_person(y,oof,g)
    tp,fn,tn,fp=four(y,oof)
    results.append({'model':name,'features':features,'valid_minutes':len(y),'excluded_minutes':int((~valid).sum()),
                    'BA':ba,'F1':f1,'BA_CI95':baci,'F1_CI95':f1ci,'TP':tp,'FN':fn,'TN':tn,'FP':fp})
    if name==sets[-1][0]:final_pred=oof.copy()

# Son modelde en yüksek hata oranına sahip üç kayıt.
errors=[]
for rec in np.unique(record):
    ii=record==rec;yy=y[ii];pp=final_pred[ii];tp,fn,tn,fp=four(yy,pp)
    has_both=len(np.unique(yy))==2
    errors.append({'record':rec,'person_group':int(g[ii][0]),'minutes':int(ii.sum()),'errors':int(np.sum(yy!=pp)),
                   'error_rate':float(np.mean(yy!=pp)),'BA':float(balanced_accuracy_score(yy,pp)) if has_both else '',
                   'F1':float(f1_score(yy,pp,zero_division=0)),'TP':tp,'FN':fn,'TN':tn,'FP':fp,
                   'note':'iki sınıf var' if has_both else 'kayıtta tek sınıf; BA hesaplanmadı'})
errors.sort(key=lambda r:(-r['error_rate'],r['record']))
worst=errors[:3]
(ROOT/'veri/06_lojistik_sonuclari.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
with (ROOT/'veri/06_en_kotu_3_kayit.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(worst[0]));w.writeheader();w.writerows(worst)
with (ROOT/'veri/06_kisi_katlari.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['person_group','fold']);w.writeheader();w.writerows([{'person_group':p,'fold':person_fold[p]} for p in sorted(person_fold)])
for r in results:print(f"{r['model']}: BA={r['BA']:.4f} %95GA={r['BA_CI95']}; F1={r['F1']:.4f} %95GA={r['F1_CI95']}; geçerli={r['valid_minutes']}; dışarıda={r['excluded_minutes']}")
print('En kötü 3 kayıt:')
for r in worst:print(r)
