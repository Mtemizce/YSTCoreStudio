"""The same project style catalogue is used by the creation form and the agents."""

STILLER = {
    "sade": {"ad": "Doğal montaj", "ozet": "Temiz kesmeler, doğal ritim ve özgün kaynaklar.",
             "plan": "Öykü ritmine göre düz kesme kullan; düz kesmeyi efekt olarak sayma."},
    "kalem": {"ad": "Kalem ve eskiz", "ozet": "Plandan veya fotoğraftan çizime, ardından gerçek görüntüye geçiş.",
              "plan": "Uygun kaynak varsa kalem-cizim skill ile çizimi canlandır. Çizim bitince gerçek kaynakla eşleşen kareye geç."},
    "teknik": {"ad": "Teknik sunum", "ozet": "Plan çizgileri, ölçü çağrıları ve kontrollü kamera hareketi.",
               "plan": "Sistem kitinden çizgi ve başlık bileşenleriyle kontrollü bir açıklama animasyonu kur; ölçü uydurma."},
    "kinetik": {"ad": "Kinetik tipografi", "ozet": "Vurgulu kelimeler, kısa tipografi animasyonları.",
                "plan": "Kısa metni kelime gruplarına böl; giriş, bekleme, çıkış zamanlarını ses ritmine bağla."},
    "kagit": {"ad": "Kâğıt kolaj", "ozet": "Katmanlı parçalar, kâğıt dokusu ve hafif paralaks.",
              "plan": "Mevcut görüntüleri maske ve katmanlarla ayır, hafif paralaks ve yapışma animasyonu kullan."},
    "suluboya": {"ad": "Suluboya defteri", "ozet": "Yumuşak pigment görünümü ve fırça maskesi.",
                 "plan": "Kurgu motorunda yerel maske ve doku ile fırça açılımını oluştur. Kaynağın yapısını değiştirip yeni detay uydurma."},
    "sinematik": {"ad": "Sinematik portfolyo", "ozet": "Yavaş kamera hareketi ve seçili yumuşak geçişler.",
                  "plan": "Kamera hareketini düşük genlikte tut; önemli mekân geçişinde tek bir dissolve veya match-cut seç."},
}


STILLER.update({
    "urun-lansman": {"ad": "Ürün lansmanı", "ozet": "İlk karede ürün, üç kısa fayda ve net kapanış.",
                     "plan": "Açılış karesinde ürünü ve başlığı göster. Özellikleri sırayla aç, her sahnede tek odak kullan.",
                     "beceriler": ["kurgu-video-studio", "hook-ve-kapak"], "kelimeler": ["lansman", "tanıtım", "launch", "ürün"]},
    "arayuz-akisi": {"ad": "Arayüz turu", "ozet": "Ekran kartları, odak halkası ve kontrollü yakınlaşma.",
                     "plan": "Gerçek ekranı kırpılmadan tanıt. Eylemin olduğu bölgeye yaklaş, imleç ve vurgu katmanlarını senkronla.",
                     "beceriler": ["kurgu-video-studio", "marka-kilidi"], "kelimeler": ["arayüz", "dashboard", "saas", "uygulama"]},
    "moduler-vitrin": {"ad": "Modüler vitrin", "ozet": "Kartlardan oluşan sahneler ve katmanlı girişler.",
                        "plan": "Kartları önem sırasına göre aç. Aynı düzen içinde ölçek, opaklık ve kısa gecikmeyle hiyerarşi kur.",
                        "beceriler": ["kurgu-video-studio"], "kelimeler": ["modüler", "bento", "vitrin", "kart"]},
    "ritmik-kolaj": {"ad": "Ritmik kolaj", "ozet": "Müziğin belirgin vuruşlarına oturan görsel kesmeler.",
                     "plan": "Vuruş haritasında güçlü anlara sahne değişimi koy. Konuşma varsa cümle sınırları önceliklidir.",
                     "beceriler": ["kurgu-video-studio", "kaba-kurgu"], "kelimeler": ["müzik", "vuruş", "ritmik", "beat"]},
    "konusma-klibi": {"ad": "Konuşma klibi", "ozet": "Kelime eşzamanlı altyazı ve onaylı sessizlik kesimleri.",
                      "plan": "Kelime transkriptini çıkar, sessizlik önerisini göster, onaylanan aralıkları uygula ve altyazıyı yeniden zamanla.",
                      "beceriler": ["kaba-kurgu", "sosyal-surumler"], "kelimeler": ["röportaj", "konuşma", "transkript", "altyazı"]},
})
STILLER["kinetik"].update(beceriler=["kurgu-video-studio"], kelimeler=["kinetik", "tipografi", "hareketli yazı"])
STILLER["kalem"].update(beceriler=["kalem-cizim"], kelimeler=["kalem", "eskiz", "çizim", "dwg"])
STILLER["suluboya"].update(beceriler=["kurgu-video-studio"], kelimeler=["suluboya", "sulu boya"])


STILLER['urun-lansman']["sahneler"] = ['Ürünü ilk karede göster', 'Temel faydayı örnekle', 'Tek eylemle kapanış']
STILLER['arayuz-akisi']["sahneler"] = ['Ekranı ve görevi tanıt', 'Gerçek işlemleri odakla', 'Sonucu göster']
STILLER['moduler-vitrin']["sahneler"] = ['Ana kart', 'Destekleyici kartlar', 'Kapanış düzeni']
STILLER['ritmik-kolaj']["sahneler"] = ['Açılış vuruşu', 'Görsel çeşitlilik', 'Güçlü vuruşta kapanış']
STILLER['konusma-klibi']["sahneler"] = ['Doğal ilk cümle', 'Ana anlatım ve altyazı', 'Kapanış']
STILLER['kinetik']["sahneler"] = ['İlk vurgu', 'Kelime grupları', 'Sabit okunabilir kapanış']


def stiller():
    return STILLER
