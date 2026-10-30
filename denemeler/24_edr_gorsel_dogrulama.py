"""a03 kaydında N ve A bölümlerinden QRS tabanlı EKG-türevli solunum çiz."""
from pathlib import Path
import os

import matplotlib.pyplot as plt
import numpy as np
import wfdb
from scipy.signal import butter, filtfilt, find_peaks, welch

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get(
    "APNEA_DATA_DIR",
    "/home/baris/.codex/.chatgpt-projects/g-p-6abd168410148191a54b53270fa904ff/Apnea Detection/data/source_full",
))
DEST = ROOT / "denemeler/24_a03_edr_normal_apne.png"
FS = 100
b_peak, a_peak = butter(2, [5, 20], btype="bandpass", fs=FS)
b_shape, a_shape = butter(2, [.5, 35], btype="bandpass", fs=FS)
b_resp, a_resp = butter(2, [5/60, 25/60], btype="bandpass", fs=4)

raw = wfdb.rdrecord(str(DATA/"a03")).p_signal[:, 0].astype(float)
labels = np.asarray(wfdb.rdann(str(DATA/"a03"), "apn").symbol)
peak_signal = filtfilt(b_peak, a_peak, raw)
shape_signal = filtfilt(b_shape, a_shape, raw)
centered = peak_signal-np.median(peak_signal)
if abs(np.percentile(centered, .5)) > np.percentile(centered, 99.5):
    centered = -centered; shape_signal = -shape_signal
peaks = find_peaks(centered, distance=30,
                   height=.5*np.percentile(centered, 99))[0]


def robust_z(x):
    med=np.median(x); mad=np.median(np.abs(x-med))
    return (x-med)/max(1.4826*mad, 1e-9)

def clean_series(times, values):
    z=robust_z(values); keep=np.abs(z)<=3.5
    return times[keep], z[keep]


def window(center_minute):
    start=(center_minute-2)*6000; end=(center_minute+3)*6000
    selected=peaks[(peaks >= start+13) & (peaks < end-16)]
    times=[]; amplitudes=[]; areas=[]
    for pos in selected:
        refined=pos-3+int(np.argmax(shape_signal[pos-3:pos+4]))
        beat=shape_signal[refined-10:refined+13]
        beat=beat-np.median(beat[:3])
        times.append(refined/FS)
        amplitudes.append(np.max(beat[3:20])-np.min(beat[3:20]))
        areas.append(np.trapezoid(np.abs(beat[3:20]), dx=.01))
    times=np.asarray(times); amplitudes=np.asarray(amplitudes); areas=np.asarray(areas)
    amp_t,amp_z=clean_series(times,amplitudes);area_t,area_z=clean_series(times,areas)
    grid=np.arange(start/FS, end/FS, .25)
    amp_i=np.interp(grid,amp_t,amp_z); area_i=np.interp(grid,area_t,area_z)
    amp_edr=filtfilt(b_resp,a_resp,amp_i)
    area_edr=filtfilt(b_resp,a_resp,area_i)
    def dominant(x):
        f,p=welch(x,fs=4,nperseg=min(512,len(x)))
        take=(f>=5/60)&(f<=25/60)
        return float(f[take][np.argmax(p[take])]*60)
    return start,end,amp_t,amp_z,area_t,area_z,grid,robust_z(amp_edr),robust_z(area_edr),dominant(amp_edr),dominant(area_edr)


examples=[("Normal bölüm",80,"N"),("Apne bölümü",125,"A")]
fig,axes=plt.subplots(3,2,figsize=(15,9))
for col,(title,center,label) in enumerate(examples):
    start,end,amp_t,amp,area_t,area,grid,amp_edr,area_edr,famp,farea=window(center)
    rel_amp_t=amp_t-start/FS;rel_area_t=area_t-start/FS;rel_g=grid-start/FS
    # İlk 10 saniyede geniş bant EKG ve R konumları.
    short_start=start; short_end=start+1000
    tt=np.arange(short_start,short_end)/FS-start/FS
    pk=peaks[(peaks>=short_start)&(peaks<short_end)]
    axes[0,col].plot(tt,shape_signal[short_start:short_end],lw=.8,color="black")
    axes[0,col].scatter(pk/FS-start/FS,shape_signal[pk],s=18,marker="x",color="red")
    axes[0,col].set_xlim(0,10);axes[0,col].set_xlabel("İlk bölüm (s)");axes[0,col].set_ylabel("EKG (mV)")
    axes[0,col].set_title(f"{title}: a03, dakika {center-2}–{center+2} ({label})")
    axes[1,col].scatter(rel_amp_t,amp,s=5,alpha=.35,label="Aykırısı çıkarılmış atımlar")
    axes[1,col].plot(rel_g,amp_edr,lw=1.3,label=f"Süzülmüş EDR ({famp:.1f}/dk)")
    axes[1,col].set_xlim(0,300);axes[1,col].set_ylabel("QRS genliği (sağlam z)");axes[1,col].legend(loc="upper right")
    axes[2,col].scatter(rel_area_t,area,s=5,alpha=.35,label="Aykırısı çıkarılmış atımlar")
    axes[2,col].plot(rel_g,area_edr,lw=1.3,label=f"Süzülmüş EDR ({farea:.1f}/dk)")
    axes[2,col].set_xlim(0,300);axes[2,col].set_ylabel("QRS alanı (sağlam z)");axes[2,col].set_xlabel("Pencere içindeki süre (s)")
    axes[2,col].legend(loc="upper right")
fig.suptitle("QRS genliği ve alanından EKG-türevli solunum (5–25 soluk/dk)")
fig.tight_layout();fig.savefig(DEST,dpi=180,bbox_inches="tight")
print("Etiket doğrulama:")
for title,center,label in examples:
    print(title, center, labels[center-2:center+3].tolist())
print(DEST)
