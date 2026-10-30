# EEM4011 – Tek Kanallı EKG ile Uyku Apnesi Dakikalarının İncelenmesi

Bu projede PhysioNet Apnea-ECG kayıtlarında ham ve 5–20 Hz süzülmüş R tepeleri karşılaştırılmış; dakika bazında SDNN ve `ln(SDNN/RMSSD)` eşik kuralları ile lojistik regresyon modelleri kişi bazlı çapraz doğrulamayla değerlendirilmiştir.

## Veri seti

**Apnea-ECG Database v1.0.0:** https://physionet.org/content/apnea-ecg/1.0.0/

Veri dosyaları bu depoya yüklenmemiştir. Çalıştırmadan önce 35 öğrenme kaydının `.hea`, `.dat` ve `.apn` dosyaları ile `additional-information.txt` dosyasını PhysioNet'ten indirip yerel `data/` klasörüne koyun. `c05` analizden çıkarılır. `x01–x35` kayıtları yalnız sonradan yapılan keşif testlerinde kullanılmıştır; birden fazla yöntem karşılaştırmasında görüldükleri için bağımsız son test olarak yorumlanmaz.

## Kurulum

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Veriler başka bir klasördeyse yolu ortam değişkeniyle belirtin:

```bash
export APNEA_DATA_DIR=/verinin/tam/yolu
```

## Çalıştırma sırası

```bash
.venv/bin/python kod/01_ham_suz_rtepeleri.py
.venv/bin/python kod/02_sdnn_baseline.py
.venv/bin/python kod/03_asama3_veri_ve_kisi_gruplari.py
.venv/bin/python kod/04_asama3_dakika_ozellikleri.py
.venv/bin/python kod/05_groupkfold_dort_kural.py
.venv/bin/python kod/06_groupkfold_lojistik.py
.venv/bin/python kod/08_asama3_ayni_dakikalar.py
.venv/bin/python kod/07_asama3_ozet.py
.venv/bin/python kod/09_test_kisisi_esik_sekli.py
.venv/bin/python kod/10_rmssd_ardisik_duyarlilik.py
.venv/bin/python denemeler/24_edr_gorsel_dogrulama.py
.venv/bin/python denemeler/25_edr_genlik_alan_tum_veri.py
.venv/bin/python denemeler/26_edr_gercek_solunum_dogrulama.py
.venv/bin/python denemeler/27_edr_birlestirme_dogrulama.py
.venv/bin/python denemeler/28_edr_kalite_agirlikli_fusion_test.py
.venv/bin/python kod/11_juri_solunum_sekilleri.py
```

Ara hesap dosyaları `veri/`, yeni jüri şekilleri `sonuclar/` klasöründe oluşturulur. `data/`, `veri/` ve `.venv/` yereldir; GitHub'ın tarayıcıdan dosya yükleme ekranında bu klasörler seçilmez.

## Ana sonuç

34 kayıt ve 24 kişi grubuyla yapılan beş katlı çapraz doğrulamada, bütün 16.579 dakikadaki süzülmüş SDNN baseline değeri **BA 0,607** olmuştur; sekiz kayıtlık Aşama 2 pilotundaki **0,589** ayrı bir deneydir. Lojistik regresyonun kullanabildiği aynı 16.375 dakikada süzülmüş `ln(SDNN/RMSSD)` kuralı **BA 0,678**, **F1 0,634**; RR ortalaması, RMSSD, R genliği standart sapması ve SDNN kullanan lojistik regresyon **BA 0,703**, **F1 0,647** vermiştir. Kişi bazlı yüzde 95 güven aralıkları sırasıyla **0,617–0,748** ve **0,607–0,797** olup örtüşür; modelin kesin üstünlüğü gösterilmiş değildir. Sonuçlar klinik tanı başarısı olarak yorumlanmaz.

Ham kolda aynı dakikalardan 1.726'sında özellik çıkarılamadı; mevcut kural bu dakikalara “apne yok” yanıtı verir. Böylece karşılaştırılan etiketli dakikalar aynı olsa da ham kolun ölçülebilirlik sınırı ayrıca raporlanır.

## RMSSD duyarlılık analizi

Eski hesap geçersiz R–R aralıklarını attıktan sonra kalanların ardışık farkını alıyordu. Gerçekten ardışık ve ikisi de geçerli R–R çiftleri kullanıldığında, `ln(SDNN/RMSSD)` kuralının BA değeri aynı 16.375 dakikada **0,6780'den 0,6829'a** çıktı; F1 **0,6336'dan 0,6398'e** çıktı. Bu ayrı bir duyarlılık analizidir; eski sonuçlar korunmuştur ve küçük farkın istatistiksel olarak anlamlı olduğu gösterilmemiştir.

## Aşama 3: EKG türevli solunum

R tepeleri için 5–20 Hz, QRS alanı için 0,5–35 Hz süzme yolu kullanılmıştır. Her hedef dakika, iki dakika öncesi ve iki dakika sonrasını içeren temiz beş dakikalık pencere içinde değerlendirilmiştir. QRS alanından çıkarılan solunum sinyalinden solunum bandı gücü, düşük/solunum bandı oranı, baskın solunum hızı, spektral yoğunlaşma, spektral entropi, genlik aralığı ve periyodiklik olmak üzere yedi özellik çıkarılmıştır.

Kişi bazlı beş katlı sınamada dört ritim özelliği **BA 0,702**, yalnız QRS alanı solunum özellikleri **BA 0,749**, ritim ve solunumun 11 özellikli birleşimi **BA 0,781 ve F1 0,738** vermiştir. `x01–x35` keşif testinde birleşik sistem **BA 0,836 ve F1 0,796** vermiştir; bu değer bağımsız doğrulama olarak sunulmaz.

EKG türevli solunum, gerçek solunum kanalı bulunan sekiz kayıttaki 3.900 pencerede ayrıca denetlenmiştir. QRS alanı yönteminde ortanca mutlak korelasyon **0,483**, solunum hızı hatası **0,6 nefes/dakika** bulunmuştur. Kalite ağırlıklı alan ve eğim birleşimi korelasyonu **0,536** ve hatayı **0,4 nefes/dakika** yapmış, fakat apne sınıflandırmasında QRS alanını tek başına geçmemiştir.

## Yeni jüri şekilleri

- `sonuclar/10_edr_normal_apne.png`: Normal ve apne bölümlerinde QRS alanından çıkarılan solunum.
- `sonuclar/11_solunum_ozellikleri_model_karsilastirmasi.png`: Ritim ve solunum özelliklerinin kişi bazlı karşılaştırması.
- `sonuclar/12_edr_gercek_solunum_dogrulama.png`: EKG türevli solunum yöntemlerinin gerçek solunumla doğrulanması.
