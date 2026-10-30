"""QRS alanı ve QRS eğimini spektral kaliteyle birleştirip test et.

Her hedef dakika için merkezli 5 dakikalık temiz pencere kullanılır.
Özellik setleri 34 öğrenme kaydında kişi bazlı 5 katla karşılaştırılır;
x01-x35 yalnız sabit keşif testidir.
"""
from pathlib import Path
import csv
import json
import os

import numpy as np
import wfdb
from scipy.signal import butter, detrend, filtfilt, find_peaks
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.environ.get("APNEA_DATA_DIR",
    "/home/baris/.codex/.chatgpt-projects/g-p-6abd168410148191a54b53270fa904ff/Apnea Detection/data/source_full"))
OUT=ROOT/"denemeler/28_edr_kalite_agirlikli_fusion_test_sonuc.json"
groups={r["record"]:int(r["person_group"]) for r in csv.DictReader(
    (ROOT/"veri/03_kayit_kisi_gruplari.csv").open())}
learn=list(groups);test=[f"x{i:02d}" for i in range(1,36)]
FS=100; EDR_FS=4
b_peak,a_peak=butter(2,[5,20],btype="bandpass",fs=FS)
b_shape,a_shape=butter(2,[.5,35],btype="bandpass",fs=FS)
b_resp,a_resp=butter(2,[5/60,25/60],btype="bandpass",fs=EDR_FS)

base_names=["mean_rr_ms","rmssd_ms","r_amp_std","sdnn_ms"]
edr_names=["log_resp_power","log_low_resp_ratio","dominant_bpm",
           "spectral_concentration","spectral_entropy",
           "filtered_range","periodicity"]


def constant_run_seconds(x):
    same=np.diff(x)==0
    if not same.any():return 0.0
    edge=np.diff(np.r_[False,same,False].astype(np.int8))
    return float(np.max(np.flatnonzero(edge==-1)-np.flatnonzero(edge==1))/FS)


def robust_z(x):
    med=np.median(x);mad=np.median(np.abs(x-med))
    return (x-med)/max(1.4826*mad,1e-9)


def edr_components(times,values,start_s,end_s):
    take=(times>=start_s)&(times<end_s)
    t=times[take];v=values[take]
    if len(v)<100:return None
    z=robust_z(v);keep=np.abs(z)<=3.5;t=t[keep];z=z[keep]
    if len(z)<80:return None
    grid=np.arange(start_s,end_s,1/EDR_FS)
    series=np.interp(grid,t,z)
    series=detrend(series,type="linear")
    resp=filtfilt(b_resp,a_resp,series)
    return series,resp


def signal_quality(resp):
    z=robust_z(resp);freq=np.fft.rfftfreq(len(z),d=1/EDR_FS)
    power=np.abs(np.fft.rfft(z*np.hanning(len(z))))**2
    band=(freq>=5/60)&(freq<=25/60);bp=power[band];bf=freq[band]
    if bp.sum()<=0:return 0.0
    concentration=float(bp.max()/bp.sum());dom=float(bf[np.argmax(bp)])
    lag=max(1,int(round(EDR_FS/dom)))
    periodicity=abs(float(np.corrcoef(z[:-lag],z[lag:])[0,1]))
    return concentration*periodicity


def edr_features(series,resp):
    tapered=series*np.hanning(len(series))
    freq=np.fft.rfftfreq(len(series),d=1/EDR_FS)
    power=np.abs(np.fft.rfft(tapered))**2
    low=(freq>=.01)&(freq<5/60)
    band=(freq>=5/60)&(freq<=25/60)
    low_power=float(power[low].sum());band_power=float(power[band].sum())
    bp=power[band];bf=freq[band]
    if band_power<=0 or not len(bp):return np.full(7,np.nan)
    dom=float(bf[np.argmax(bp)]);prob=bp/bp.sum()
    concentration=float(bp.max()/bp.sum())
    entropy=float(-np.sum(prob*np.log(prob+1e-15))/np.log(len(prob)))
    lag=max(1,int(round(EDR_FS/dom)))
    periodicity=float(np.corrcoef(resp[:-lag],resp[lag:])[0,1]) if lag<len(resp) else np.nan
    return np.array([np.log10(band_power+1e-12),
                     np.log10((low_power+1e-12)/(band_power+1e-12)),
                     dom*60,concentration,entropy,
                     np.percentile(resp,95)-np.percentile(resp,5),periodicity])


def process(rec):
    raw=wfdb.rdrecord(str(DATA/rec)).p_signal[:,0].astype(float)
    labels=np.asarray(wfdb.rdann(str(DATA/rec),"apn").symbol)
    peak_signal=filtfilt(b_peak,a_peak,raw);shape_signal=filtfilt(b_shape,a_shape,raw)
    centered=peak_signal-np.median(peak_signal)
    if abs(np.percentile(centered,.5))>np.percentile(centered,99.5):
        centered=-centered;shape_signal=-shape_signal
    peaks=find_peaks(centered,distance=30,height=.5*np.percentile(centered,99))[0]
    rr=np.diff(peaks)/FS;rr_minute=peaks[1:]//6000
    p2p=np.array([np.ptp(raw[m*6000:min((m+1)*6000,len(raw))]) for m in range(len(labels))])
    record_median=np.median(p2p[p2p>0]);clean=np.zeros(len(labels),bool)
    base=np.full((len(labels),4),np.nan)
    for m in range(len(labels)):
        start,end=m*6000,(m+1)*6000
        if end>len(raw):continue
        take=rr_minute==m;r=rr[take];valid=(r>=.3)&(r<=2.0);rv=r[valid]
        count=int(np.sum((peaks>=start)&(peaks<end)))
        rejected=1-valid.mean() if len(r) else 1.0
        clean[m]=(constant_run_seconds(raw[start:end])<1 and p2p[m]/record_median>=.1
                  and 40<=count<=200 and valid.sum()>=30 and rejected<=.2)
        if clean[m]:
            rpeaks=peaks[1:][take][valid]
            base[m]=[np.mean(rv)*1000,np.sqrt(np.mean(np.diff(rv)**2))*1000,
                     np.std(peak_signal[rpeaks]),np.std(rv)*1000]

    beat_t=[];area=[];slope=[]
    for pos in peaks:
        if pos<13 or pos+16>=len(raw):continue
        refined=pos-3+int(np.argmax(shape_signal[pos-3:pos+4]))
        beat=shape_signal[refined-10:refined+13]
        if len(beat)!=23 or not np.isfinite(beat).all():continue
        beat=beat-np.median(beat[:3]);qrs=beat[3:20]
        beat_t.append(refined/FS)
        area.append(np.trapezoid(np.abs(qrs),dx=1/FS))
        slope.append(np.ptp(np.diff(beat[5:16])*FS))
    beat_t=np.asarray(beat_t);area=np.asarray(area);slope=np.asarray(slope)

    rows=[]
    for m in range(2,len(labels)-2):
        if not clean[m-2:m+3].all() or not np.isfinite(base[m]).all():continue
        start_s=(m-2)*60;end_s=(m+3)*60
        ac=edr_components(beat_t,area,start_s,end_s)
        sc=edr_components(beat_t,slope,start_s,end_s)
        if ac is None or sc is None:continue
        area_series,area_resp=ac;slope_series,slope_resp=sc
        if np.corrcoef(area_resp,slope_resp)[0,1]<0:
            slope_series=-slope_series;slope_resp=-slope_resp
        qa,qs=signal_quality(area_resp),signal_quality(slope_resp)
        total=max(qa+qs,1e-12)
        fusion_series=(qa*robust_z(area_series)+qs*robust_z(slope_series))/total
        fusion_resp=(qa*robust_z(area_resp)+qs*robust_z(slope_resp))/total
        area_f=edr_features(area_series,area_resp)
        slope_f=edr_features(slope_series,slope_resp)
        fusion_f=edr_features(fusion_series,fusion_resp)
        if all(np.isfinite(v).all() for v in (area_f,slope_f,fusion_f)):
            rows.append((np.r_[base[m],area_f,slope_f,fusion_f],labels[m]=="A"))
    return rows


learn_rows=[];test_rows=[]
for no,rec in enumerate(learn+test,1):
    rows=process(rec);dest=learn_rows if rec in groups else test_rows
    dest.extend((rec,x,y) for x,y in rows)
    print(f"[{no:02d}/{len(learn)+len(test)}] {rec}: {len(rows)} pencere",flush=True)


def stack(rows):
    return np.vstack([r[1] for r in rows]),np.asarray([r[2] for r in rows],bool),np.asarray([r[0] for r in rows])


X,y,record=stack(learn_rows);Xt,yt,test_record=stack(test_rows);group=np.array([groups[r] for r in record])
blocks={
    "ritim_4":list(range(4)),
    "alan_EDR_7":list(range(4,11)),
    "egim_EDR_7":list(range(11,18)),
    "fusion_EDR_7":list(range(18,25)),
    "ritim_4+alan_EDR_7":list(range(11)),
    "ritim_4+egim_EDR_7":list(range(4))+list(range(11,18)),
    "ritim_4+fusion_EDR_7":list(range(4))+list(range(18,25)),
}


def model():
    return Pipeline([("scale",StandardScaler()),
                     ("lr",LogisticRegression(max_iter=2000,class_weight="balanced",random_state=0))])


gkf=GroupKFold(n_splits=5);cv={}
for name,cols in blocks.items():
    pred=np.zeros(len(y),bool)
    for tr,va in gkf.split(X[:,cols],y,group):
        if set(group[tr])&set(group[va]):raise AssertionError("Kişi sızıntısı")
        clf=model();clf.fit(X[tr][:,cols],y[tr]);pred[va]=clf.predict(X[va][:,cols])
    cv[name]={"BA":float(balanced_accuracy_score(y,pred)),"F1":float(f1_score(y,pred))}

selected=max(cv,key=lambda k:cv[k]["BA"])
test_results={}
for name,cols in blocks.items():
    clf=model();clf.fit(X[:,cols],y);pred=clf.predict(Xt[:,cols])
    tn,fp,fn,tp=confusion_matrix(yt,pred,labels=[False,True]).ravel()
    test_results[name]={"BA":float(balanced_accuracy_score(yt,pred)),
                        "F1":float(f1_score(yt,pred)),
                        "sensitivity":float(tp/(tp+fn)),"specificity":float(tn/(tn+fp)),
                        "TP":int(tp),"FN":int(fn),"TN":int(tn),"FP":int(fp)}
result={"window":"Merkezli 5 dakika; beş dakikanın tamamı temiz",
        "learn_records":len(learn),"test_records":len(test),
        "windows":{"learn":len(y),"test":len(yt)},
        "edr_features":edr_names,"group_cv_on_learn":cv,
        "selected_without_x":selected,"x_test_exploratory_all_fixed_blocks":test_results,
        "note":"Seçim yalnız öğrenme kayıtlarında yapıldı; tüm x sonuçları yöntem karşılaştırması için keşif olarak raporlandı."}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2));print("Sonuç:",OUT)
