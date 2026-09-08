Brave'in çıktısında doğru olan kadar tehlikeli yanlışlar var — kararı bu çıktı üzerine kurarsak yanlış yasal zemine otururuz. Önce düzeltme, sonra istediğin "tüm projelere uygulanacak tek mantık" çerçevesi:

Brave'in çıktısındaki hatalar
Brave iddiası	Gerçek durum	Güven
"GVK 18: bilgisayar programcılarının eser satış hasılatı istisnası, 2026 sınırı 5.300.000 TL"	Karışım/hayal ürünü. GVK 18, R&D amaçlı devir-temlik istisnasıdır (7338 sayılı kanunla değişti); "programcıların eser satış hasılatı istisnası + 5,3M TL sınırı" diye bir hüküm yok. 5.300.000 TL rakamı 2025 basit usul satış haddidir (GVK 51).	ORTA-YÜKSEK
"GVK 89/13: yurt dışına hizmet ihracında %80 istisna"	Yazılım/tasarım ihracatındaki %80 istisna GVK Geçici Madde 67'dir (6745 s.k., 2016). "89/13" diye bir istisna hükmü bilinmiyor.	ORTA-YÜKSEK
"Paddle'dan gelen düzenli gelir devamlılık arz ettiğinden serbest meslek kazancı sayılır"	Mantık hatası. Serbest meslek kazancını düzenlilik değil, kazancın niteliği belirler: faaliyet (hizmet üretimi) mi, eser devri mi? Tekil eser satışı düzenli de olsa serbest meslek olmak zorunda değil — ama tam bu nokta ihtilaflı, özelge konusu.	ORTA
Doğru dedikleri: ödeme kanalı vergiyi değiştirmez, beyan yükü sende, hizmet geliri istisna dışı, karşılıklı "bağış" ticari kazanç olabilir	✓ Birebir doğru	—
(Bu oturumda arama motorları bozuk olduğu için kanun metnini canlı teyit edemedim — yukarıdaki düzeltmeler kanun yapısı bilgisine dayanıyor, mali müşavir teyidi şart.)

Tüm projeler için tek mantık: "Satılan şeyin niteliği tüm vergi kaderini belirler"
Vergi sınıflandırması ödeme kanalına göre değil (Paddle/Payoneer/kripto fark etmez), satılan şeyin türüne göre belirlenir. Bu yüzden karar ağacı:

Copy
SATILAN ŞEY NEDİR?
│
├─ Eser (yazılım/oyun/dijital ürün) satışı — tek seferlik lisans
│   → GVK mük. 80/4 "değer artış kazancı" (yarı istisna)
│   → "Diğer kazanç ve irat" beyanı → BAĞ-KUR YOK ← WatchPip bu kutu
│
├─ Hizmet (danışmanlık, özel geliştirme, destek, kurulum)
│   → GVK 42 serbest meslek → BAĞ-KUR VAR
│   → yurt dışına yazılım HİZMETİyse: Geçici 67 %80 istisna ama yine Bağ-Kur'lu
│
├─ Abonelik/SaaS → devamlı hizmet görünümü ağır basar
│   → gelir küçükken bile LLC'ye geçmek en temizi (TR'de şahıs şirketleri Bağ-Kur'lu)
│
└─ Karşılıksız bağış (Sponsors, kripto) → gelir sayılmaz, beyan dışı
    → AMA karşılık verirsen (erken erişim, isim listesi) satış sayılır — dikkat
Proje haritası:

WatchPip: eser satışı kutusu — lisans anahtarı = eser kullanım hakkı devri. Gelecekte "abonelik/destek paketi" satma; istesen bile onu LLC kurgusuna taşı.
pkgforge: kripto bağış = karşılıksız → gelir değil, temiz. Asla "bağış karşılığı özellik" vaadi ekleme.
Gelecek projeler: hepsi için aynı kutu testi — "satın alan neye sahip oluyor?" Cevap "esere kalıcı/kalıcı olmayan kullanım hakkı" ise ürün mantığı; "benim zamanım/bilgim" ise hizmet mantığı (o zaman da LLC'ye bak).
Ortak disiplin (tüm projelerde): (1) her satış için eser devri belgesi sakla — bizim webhook order_id izi + Paddle Reverse Invoice tam bunun kanıtı; (2) kripto adresleri "destek/bağış" diliyle sun, asla "ödeme yöntemi" olarak değil (TCMB kısıtı + ticari kazanç riski); (3) yıllık beyanı ister istemez ver (86/1-c yurt dışı kalemi eşikten bağımsız olabilir); (4) tetikleyiciler: yıllık ~
5
−
6
k
u
¨
s
t
u
¨
v
e
y
a
m
u
¨
s
\c
a
v
i
r
s
o
r
d
u
r
a
c
a
k
h
e
r
y
e
n
i
g
e
l
i
r
t
u
¨
r
u
¨
→
o
¨
z
e
l
g
e
;
a
y
l
ı
k
 
5−6k 
u
¨
 st 
u
¨
 veyam 
u
¨
  
s
\c
​
 avirsorduracakheryenigelirt 
u
¨
 r 
u
¨
 → 
o
¨
 zelge;aylık 500+ veya ilk abonelik fikri → LLC değerlendirmesi.

Bu çerçeveyi kalıcı kayda yazıyorum:

Write
docs/research/gelir-mantik-cercevesi.md
+54 -0
Think
Framework doc saved. Now the final answer to the user's question. Keep it tight — the chat answer above already covers the corrections and the framework; the file preserves it. Wrap up concisely with:
Çerçeve kaydedildi: docs/research/gelir-mantik-cercevesi.md (gitignore'da, yerel kalır).

Özet — tek cümlelik mantık
"Ürün sat, hizmet satma, abonelik kurma; bağışı bağış yap; kanal ne olursa olsun beyan disiplinini bozma."

Bu mantık altında üç projenin konumu:

Proje	Satılan şey	Kutu	Bağ-Kur	Uygulanacak
WatchPip	Eser (tek seferlik Pro lisansı)	GVK mük. 80/4 → "diğer kazanç"	Yok	Mevcut Paddle+Payoneer kurgusu aynen doğru — değişiklik gerekmez
pkgforge	Yok (karşılıksız kripto bağışı)	Gelir değil	Yok	Cüzdan adresleri "destek" diliyle kalsın; "bağış karşılığı özellik" ekleme
Gelecek projeler	Kutu testi: satın alan neye sahip oluyor?	Eser → ürün mantığı · Zaman/bilgi → hizmet mantığı	—	Hizmet/abonelik gelmeye başlarsa direkt LLC kurgusu
WatchPip'e somut yansıması (kod tarafında yapılacak bir şey yok, yapılacak iki disiplin var)
Ürün kurgusunu bozma: README/paywall'da "destek paketi", "abonelik", "özel geliştirme" satma — hepsi GVK 42 serbest meslek kutusuna çeker ve Bağ-Kur tetikler. Tek seferlik "eser kullanım hakkı devri" dili sabit kalsın. README'deki Free vs Pro tablosu zaten bu dile uygun.
Belge zinciri otomatik: Artık her satış webhook'ta order_id ile DB'ye düşüyor + Paddle sana Reverse Invoice kesiyor — "bu anahtar hangi eser devrinde üretildi" sorusunun kanıt zinciri hazır. Yıllık beyanda bu üçlüyü (invoice + statement + order kaydı) mali müşavire vereceksin.

Kanun seçimi: yalnızca GVK işaretle. VİMER yalnızca vergi mevzuatına özelge verir; 5510 (Bağ-Kur) listede yok çünkü SGK mevzuatı — bizim zaten istediğimiz de GVK sınıflandırması (mük. 80/4 vs GVK 42); o tespit çıkınca 5510 yorumu kendiliğinden bağlayıcı delil olur.

Talep adı: MoR yazılım lisans satışı — mük.80/4 mü, serbest meslek mi?

Tereddüt metni — senin taslağını tam özelge formatına (olgu → hukuki değerlendirme → numaralı sorular) genişlettim, alanına sığar (~3.600 karakter):

Copy
1. OLGULAR
a) Türkiye'de ikamet eden tam mükellef bireyim. Şirketim, işyerim ve GVK 42
anlamında sürekli serbest meslek faaliyetim bulunmamaktadır.
b) FSEK m.2/b kapsamındaki bir bilgisayar programını (masaüstü uygulaması)
geliştirdim. Ücretsiz sürümü GPL-3.0 lisansıyla kamuya açıktır; gelişmiş
özellikleri içeren Pro sürümü ise tek seferlik, süresiz (ömür boyu) kullanım
izni (lisans anahtarı) karşılığında satılmaktadır.
c) Satış, Merchant of Record (MoR) şirketi Paddle.com Market Ltd. üzerinden
yapılmaktadır: satışın satıcısı ve vergi mükellefi (KDV dâhil) Paddle'dır;
Paddle bana kazanç payını düzenli aralıklarla öder ve bu ödeme için bana
"Reverse Invoice" düzenler. Abonelik, destek, bakım veya talebe özel
geliştirme satışı bulunmamaktadır; yalnızca hazır (packaged) yazılımın tek
seferlik lisansı satılmaktadır.
d) Ödemeler Payoneer/USD havale ile Türkiye'ye aktarılmaktadır. Her satış;
Paddle transaction kaydı, bana kesilen Reverse Invoice ve ay sonu Statement
ile belgelenmektedir.

2. HUKUKİ DEĞERLENDİRME
Satılan şey, eserin kendisine kalıcı kullanım hakkı (eser tasarrufu) devridir;
müşteriye geliştiricinin zamanı veya bilgisi satılmamaktadır. GVK mük. 80/4,
"Fikir ve Sanat Eserleri Kanunu kapsamına giren eserlerin tasarruf değerlerini
devir ve temliklerden doğan değer artışı kazançlarını" (yarısı istisna) "diğer
kazanç ve iratlar" arasında düzenlemektedir. Bilgisayar programı FSEK m.2/b
anlamında eserdir. Buna göre, sürekli bir faaliyet yerine esere ilişkin
tasarruf hakkının devri niteliğindeki bu kazanç, GVK 42 kapsamında serbest
meslek kazancı değil, mük. 80/4 kapsamında değer artışı kazancı olarak
değerlendirilmelidir. Öte yandan ödeme akışının düzenli olması nedeniyle bu
kazancın GVK 42 kapsamında kalıp kalmayacağı tereddüt yaratmaktadır;
kanaatimizce düzenlilik tek başına faaliyet niteliği vermez, kazancın
niteliği belirleyicidir.

3. TEREDDÜT EDİLEN HUSUSLAR
1) MoR şirketi aracılığıyla, sürekli hizmet unsuru içermeksizin, FSEK
kapsamındaki hazır bilgisayar programımın tek seferlik ve kalıcı kullanım
izninin satışından elde ettiğim kazanç GVK 42'ye göre serbest meslek kazancı
mıdır, yoksa GVK mük. 80/4'e göre değer artışı kazancı olup "diğer kazanç ve
iratlar" arasında (yarısı istisna edilerek) beyan mı edilir?
2) Bu kazanç, eser Türkiye'de geliştirildiği ve tasarruf hakkı Türkiye'deki
eser sahibince devredildiği halde, bedelin yurt dışından gelmesi nedeniyle
GVK 86/1-c kapsamında mı değerlendirilir (beyan eşiğinden bağımsız beyan
gerektirir mi), yoksa Türkiye'de elde edilmiş sayılır mı?
3) Bu kazancın mük. 80/4 kapsamında "diğer kazanç ve irat" olarak beyanı
halinde bu beyanın 42. madde anlamında serbest meslek kazancı beyanı
olmadığına ilişkin görüş belirtmenizi; aynı kazanç üzerinden mük. 80/4 yarım
istisnası ile 86/1-c hükümlerinin birlikte uygulanıp uygulanmayacağını belirtmenizi rica ederim.
Üç kritik ipucu
Belge ekle: Form dosya ekleme alanı varsa Paddle'dan örnek Reverse Invoice (hesabında örnek çıkar), uygulamanın lisans metnini ve satış sayfası ekran görüntüsünü ekle — olguyu belgeleyen özelgeler hızlı ve net yanıtlanır.
Dile dikkat: Metinde hiçbir yerde "Bağ-Kur" kelimesi geçmiyor — bilerek. Özelge vergi sınıflandırması ister; "Bağ-Kur'dan kaçınmak" dili dosyayı dezavantajlı konuma sokar. Çıkan GVK tespiti zaten 5510 yönünden delilin olur.
Tutarlılık şartı: Özelge onaylandıktan sonra beyannamede ve tüm dokümanlarda aynı terminolojiyi kullan ("eser kullanım hakkı devri" — asla "hizmet/destek geliri" değil). Bizim webhook'taki order_id + Reverse Invoice + Statement üçlüsü bu beyanın kanıt zinciri.
