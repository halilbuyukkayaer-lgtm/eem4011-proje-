from pathlib import Path
import os
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'veri').mkdir(exist_ok=True)
(ROOT/'ciktilar').mkdir(exist_ok=True)
rules=json.loads((ROOT/'veri/05_dort_kural_sonuclari.json').read_text())
models=json.loads((ROOT/'veri/06_lojistik_sonuclari.json').read_text())
items=[]
for r in rules:
    items.append({'name':f"Kural: {r['pipeline']} + {r['feature_name']}",**r})
for r in models:items.append({'name':f"Lojistik: {r['model']}",**r})
fig,axes=plt.subplots(1,2,figsize=(17,7));y=np.arange(len(items))
for ax,key,ci_key,color in [(axes[0],'BA','BA_CI95','#2f7195'),(axes[1],'F1','F1_CI95','#bd5b43')]:
    val=np.array([r[key] for r in items]);ci=np.array([r[ci_key] for r in items]);err=np.vstack([val-ci[:,0],ci[:,1]-val])
    ax.errorbar(val,y,xerr=err,fmt='o',color=color,ecolor='#777',capsize=4,markersize=8)
    ax.axvline(.5,color='#999',ls='--',lw=1);ax.set_xlim(.25,.85);ax.grid(axis='x',alpha=.25);ax.set_xlabel(key+' ve kişi bootstrap %95 güven aralığı')
    ax.set_yticks(y,[r['name'] for r in items]);ax.invert_yaxis()
fig.suptitle('Aşama 3: 24 kişi gruplu beş katlı çapraz doğrulama',fontsize=16)
fig.tight_layout(rect=(0,0,1,.94));fig.savefig(ROOT/'ciktilar/07_asama3_model_karsilastirmasi.png',dpi=180);plt.close(fig)
