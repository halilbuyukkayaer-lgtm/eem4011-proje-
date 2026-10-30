"""Sekiz eşzamanlı solunum kaydında beş EDR yöntemini doğrula.

Ana ölçüt: göğüs/karın solunum eforuyla ±10 s gecikmede en yüksek mutlak
korelasyon. Ayrıca burun akımı korelasyonu ve baskın solunum hızı hatası.
"""
from pathlib import Path
import json
import os

import numpy as np
import wfdb
from scipy.signal import butter, detrend, filtfilt, find_peaks

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.environ.get("APNEA_DATA_DIR",
    "/home/baris/.codex/.chatgpt-projects/g-p-6abd168410148191a54b53270fa904ff/Apnea Detection/data/source_full"))
REF=ROOT/"veri/edr_reference"
OUT=ROOT/"denemeler/27_edr_birlestirme_dogrulama_sonuc.json"
records=["a01","a02","a03","a04","b01","c01","c02","c03"]
FS=100;EFS=4
b_peak,a_peak=butter(2,[5,20],btype="bandpass",fs=FS)
b_shape,a_shape=butter(2,[.5,35],btype="bandpass",fs=FS)
b_resp100,a_resp100=butter(2,[5/60,25/60],btype="bandpass",fs=FS)
b_resp4,a_resp4=butter(2,[5/60,25/60],btype="bandpass",fs=EFS)
methods=("qrs_area","slope_range","fusion_mean","fusion_pca",
         "fusion_quality_weighted","fusion_quality_select")


def constant_run_seconds(x):
    same=np.diff(x)==0
    if not same.any():return 0.0
    edge=np.diff(np.r_[False,same,False].astype(np.int8))
    return float(np.max(np.flatnonzero(edge==-1)-np.flatnonzero(edge==1))/FS)


def robust_z(x):
    med=np.median(x);mad=np.median(np.abs(x-med))
    return (x-med)/max(1.4826*mad,1e-9)

def fill_missing(x):
    x=np.asarray(x,float);good=np.isfinite(x)
    if good.sum()<2:return np.zeros_like(x)
    return np.interp(np.arange(len(x)),np.flatnonzero(good),x[good])


def edr(times,values,grid):
    z=robust_z(values);keep=np.abs(z)<=3.5
    if keep.sum()<80:return None
    x=np.interp(grid,times[keep],z[keep]);x=detrend(x)
    return filtfilt(b_resp4,a_resp4,x)


def max_abs_corr(x,y,maxlag=40):
    x=robust_z(x);y=robust_z(y);best=0.0
    for lag in range(-maxlag,maxlag+1):
        if lag<0:a,b=x[-lag:],y[:lag]
        elif lag>0:a,b=x[:-lag],y[lag:]
        else:a,b=x,y
        c=np.corrcoef(a,b)[0,1]
        if np.isfinite(c):best=max(best,abs(float(c)))
    return best


def dominant_bpm(x):
    x=detrend(x)*np.hanning(len(x));f=np.fft.rfftfreq(len(x),1/EFS)
    p=np.abs(np.fft.rfft(x))**2;take=(f>=5/60)&(f<=25/60)
    return float(f[take][np.argmax(p[take])]*60)

def spectral_quality(x):
    z=robust_z(x);f=np.fft.rfftfreq(len(z),1/EFS)
    p=np.abs(np.fft.rfft(z*np.hanning(len(z))))**2
    take=(f>=5/60)&(f<=25/60);bp=p[take];bf=f[take]
    if bp.sum()<=0:return 0.0
    concentration=float(bp.max()/bp.sum());dom=float(bf[np.argmax(bp)])
    lag=max(1,int(round(EFS/dom)))
    periodicity=abs(float(np.corrcoef(z[:-lag],z[lag:])[0,1]))
    return concentration*periodicity

def fuse(area,slope):
    a=robust_z(area);s=robust_z(slope)
    if np.corrcoef(a,s)[0,1]<0:s=-s
    mean=robust_z((a+s)/2)
    matrix=np.column_stack([a,s]);matrix-=matrix.mean(axis=0,keepdims=True)
    _,_,vt=np.linalg.svd(matrix,full_matrices=False)
    pca=robust_z(matrix@vt[0])
    qa,qs=spectral_quality(a),spectral_quality(s)
    weighted=robust_z((qa*a+qs*s)/max(qa+qs,1e-12))
    selected=a if qa>=qs else s
    return {"fusion_mean":mean,"fusion_pca":pca,
            "fusion_quality_weighted":weighted,
            "fusion_quality_select":selected}


rows=[]
for no,rec in enumerate(records,1):
    raw=wfdb.rdrecord(str(DATA/rec)).p_signal[:,0].astype(float)
    labels=np.asarray(wfdb.rdann(str(DATA/rec),"apn").symbol)
    # r.dat dört kanallı ve bazı kayıtlarda başlıktan birkaç örnek kısadır.
    samples=(REF/f"{rec}r.dat").stat().st_size//8
    reference=wfdb.rdrecord(str(REF/f"{rec}er"),sampto=samples,
                            channels=[1,2,3]).p_signal.astype(float)
    reference=np.column_stack([filtfilt(b_resp100,a_resp100,fill_missing(reference[:,i]))
                               for i in range(3)])
    usable=min(len(raw),len(reference));raw=raw[:usable]
    peak_signal=filtfilt(b_peak,a_peak,raw);shape_signal=filtfilt(b_shape,a_shape,raw)
    centered=peak_signal-np.median(peak_signal)
    if abs(np.percentile(centered,.5))>np.percentile(centered,99.5):
        centered=-centered;shape_signal=-shape_signal
    peaks=find_peaks(centered,distance=30,height=.5*np.percentile(centered,99))[0]
    rr=np.diff(peaks)/FS;rr_minute=peaks[1:]//6000
    n=min(len(labels),usable//6000)
    p2p=np.array([np.ptp(raw[m*6000:(m+1)*6000]) for m in range(n)])
    record_med=np.median(p2p[p2p>0]);clean=np.zeros(n,bool)
    for m in range(n):
        take=rr_minute==m;r=rr[take];valid=(r>=.3)&(r<=2.0)
        count=int(np.sum((peaks>=m*6000)&(peaks<(m+1)*6000)))
        rejected=1-valid.mean() if len(r) else 1.0
        clean[m]=(constant_run_seconds(raw[m*6000:(m+1)*6000])<1
                  and p2p[m]/record_med>=.1 and 40<=count<=200
                  and valid.sum()>=30 and rejected<=.2)

    beat_t=[];beats=[]
    for pos in peaks:
        if pos<13 or pos+16>=usable:continue
        refined=pos-3+int(np.argmax(shape_signal[pos-3:pos+4]))
        beat=shape_signal[refined-10:refined+13]
        if len(beat)==23 and np.isfinite(beat).all():
            beat_t.append(refined/FS);beats.append(beat-np.median(beat[:3]))
    beat_t=np.asarray(beat_t);beats=np.asarray(beats)

    for m in range(2,n-2):
        if not clean[m-2:m+3].all():continue
        start,end=(m-2)*60,(m+3)*60;take=(beat_t>=start)&(beat_t<end)
        t=beat_t[take];shape=beats[take]
        if len(t)<100:continue
        qrs=shape[:,3:20]
        series={
            "qrs_area":np.trapezoid(np.abs(qrs),dx=1/FS,axis=1),
            "slope_range":np.ptp(np.diff(shape[:,5:16],axis=1)*FS,axis=1),
        }
        grid=np.arange(start,end,1/EFS)
        ref_grid=np.column_stack([np.interp(grid,np.arange(usable)/FS,reference[:,i])
                                  for i in range(3)])
        ref_dom=[dominant_bpm(ref_grid[:,i]) for i in range(3)]
        signals={name:edr(t,series[name],grid) for name in ("qrs_area","slope_range")}
        if any(v is None for v in signals.values()):continue
        signals.update(fuse(signals["qrs_area"],signals["slope_range"]))
        for name in methods:
            signal=signals[name]
            if signal is None:continue
            chest=max_abs_corr(signal,ref_grid[:,0]);abd=max_abs_corr(signal,ref_grid[:,1])
            nasal=max_abs_corr(signal,ref_grid[:,2]);dom=dominant_bpm(signal)
            rows.append({"record":rec,"minute":m,"label":labels[m],"method":name,
                         "effort_corr":max(chest,abd),"nasal_corr":nasal,
                         "rate_error_bpm":min(abs(dom-ref_dom[0]),abs(dom-ref_dom[1])),
                         "dominant_bpm":dom})
    print(f"[{no}/8] {rec}: pencere {sum(r['record']==rec for r in rows)//len(methods)}",flush=True)

summary={}
for method in methods:
    r=[x for x in rows if x["method"]==method]
    summary[method]={
        "windows":len(r),
        "median_effort_corr":float(np.median([x["effort_corr"] for x in r])),
        "median_nasal_corr":float(np.median([x["nasal_corr"] for x in r])),
        "median_rate_error_bpm":float(np.median([x["rate_error_bpm"] for x in r])),
        "N_effort_corr":float(np.median([x["effort_corr"] for x in r if x["label"]=="N"])),
        "A_effort_corr":float(np.median([x["effort_corr"] for x in r if x["label"]=="A"])),
    }
best_counts={m:0 for m in methods}
keys={(r["record"],r["minute"]) for r in rows}
for key in keys:
    candidates=[r for r in rows if (r["record"],r["minute"])==key]
    if len(candidates)==len(methods):
        best=max(candidates,key=lambda x:x["effort_corr"])["method"]
        best_counts[best]+=1
result={"reference_records":records,"window":"5 dakika, tüm dakikalar temiz",
        "primary_metric":"Resp C veya Resp A ile ±10 s gecikmede en yüksek mutlak korelasyon",
        "summary":summary,"best_method_window_counts":best_counts,
        "note":"Örtüşen pencereler bağımsız örnek değildir; sonuç yöntem doğrulaması içindir."}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2));print("Sonuç:",OUT)
