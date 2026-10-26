"""Aşama 3 / Adım 2: 34 kayıtta ham ve süzülmüş dakika özellikleri."""
from pathlib import Path
import os
import csv
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
import wfdb

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'veri').mkdir(exist_ok=True)
(ROOT/'ciktilar').mkdir(exist_ok=True)
DATA=Path(os.environ.get('APNEA_DATA_DIR', 'data'))
groups={r['record']:int(r['person_group']) for r in csv.DictReader((ROOT/'veri/03_kayit_kisi_gruplari.csv').open())}
records=list(groups)
b,a=butter(2,[5,20],btype='bandpass',fs=100)

def tepe_bul(s):
    y=s-np.median(s)
    if abs(np.percentile(y,.5))>np.percentile(y,99.5):y=-y
    return find_peaks(y,distance=30,height=.5*np.percentile(y,99))[0]

def minute_features(pk,signal,n):
    rr=np.diff(pk)/100; dk=pk[1:]//6000
    rows=[]
    for i in range(n):
        take=dk==i; r=rr[take]; ok=(r>=.3)&(r<=2.0); rv=r[ok]
        # R genlikleri: ikinci tepenin dakikasına düşen geçerli RR'lerin ikinci tepeleri.
        rpk=pk[1:][take][ok]
        if len(rv)<30:
            rows.append((np.nan,np.nan,np.nan,np.nan,np.nan));continue
        mean_rr=np.mean(rv)*1000
        sdnn=np.std(rv)*1000
        rmssd=np.sqrt(np.mean(np.diff(rv)**2))*1000 if len(rv)>1 else np.nan
        ratio=np.log(sdnn/rmssd) if sdnn>0 and rmssd>0 else np.nan
        amp_std=np.std(signal[rpk]) if len(rpk)>1 else np.nan
        rows.append((mean_rr,sdnn,rmssd,ratio,amp_std))
    return rows

out=[]
for j,k in enumerate(records,1):
    x=wfdb.rdrecord(str(DATA/k)).p_signal[:,0]
    labels=np.asarray(wfdb.rdann(str(DATA/k),'apn').symbol); n=len(labels)
    s=filtfilt(b,a,x)
    for yol,signal in [('ham',x),('suz',s)]:
        pk=tepe_bul(signal); feats=minute_features(pk,signal,n)
        for i,(mean_rr,sdnn,rmssd,ratio,amp_std) in enumerate(feats):
            out.append({'record':k,'person_group':groups[k],'minute':i,'label':labels[i],'pipeline':yol,
                        'mean_rr_ms':mean_rr,'sdnn_ms':sdnn,'rmssd_ms':rmssd,
                        'ln_sdnn_rmssd':ratio,'r_amplitude_std':amp_std})
    print(f'[{j:02d}/{len(records)}] {k}',flush=True)

path=ROOT/'veri/04_asama3_dakika_ozellikleri.csv'
with path.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print('Satır:',len(out));print('Kayıt:',len(records));print('Kişi:',len(set(groups.values())));print(path)
