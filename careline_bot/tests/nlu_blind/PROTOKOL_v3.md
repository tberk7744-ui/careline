# v3 doğrulama protokolü (2026-11-27, v3 çalışmasından ÖNCE donduruldu)

## Kabul eşikleri (değiştirilemez)
| Ölçüt | Eşik | Nerede |
|---|---|---|
| emergency recall (model + RedFlagGuard) | 1,00 (sıfır kaçak) | kör set, geliştirme seti |
| give_consent ↔ deny_consent ters sınıflama | 0 | kör set, geliştirme seti |
| Genel ağırlıklı intent F1 | ≥ 0,80 | kör set ve 5 katlı CV |
| request_human recall | ≥ 0,90 | kör set |
| ask_privacy F1 | ≥ 0,80 | kör set |
| RedFlagGuard yanlış alarm | raporlanır, eşik yok (güvenlik lehine) | redflag_near_miss.yml + acil olmayan tüm eğitim örnekleri |

Bir eşik tutmazsa v3 üretime alınmaz; eşik gevşetilmez.

## Setler
- Geliştirme seti: `tests/nlu_holdout/test_data.yml` (87). Hataları incelendi, artık tarafsız değil → yalnızca geliştirme.
- Kör set: `blind_claude.yml` (72, Claude yazdı) + `blind_user.yml` (kullanıcı/ekip yazar; Claude son ölçüme kadar okumaz). İleride SUS katılımcı cümleleri `blind_sus.yml` olarak eklenir.
- Kör set sonuçları yalnızca v3 son ölçümünde açılır; sonuca göre veri/kural ayarı yapılırsa set "yanmış" sayılır ve yeni kör set gerekir.
- Bilinen sınırlılık: blind_claude.yml'i eğitim örneklerini de yazan Claude yazdı (üslup benzerliği). Asıl bağımsız doğrulama blind_user/blind_sus.

## Sıra (tek seferde tek değişken)
1. RedFlagGuard kalıp genişletmesi (kural) → v2 modeliyle geliştirme setinde ölçülür + yanlış alarm.
2. Onay/gizlilik kümesi (veri) → v3a.
3. bot_challenge/request_human kümesi (veri) → v3b.
4. Son: v3 kör sette + 5 katlı CV'de, bu eşiklerle.

## Dondurma özetleri (sha256)
- blind_claude.yml 09620ba8b6b1f68bef2d1a395c7e8ac3d49838e713843f3a06c3c6b7902183ce
- redflag_near_miss.yml b7702898e4944e2da748e9589e1ac77c3ebcad441736bb57fa2fcf25da3c40f2

## Durum güncellemesi (2026-11-27)
- v3 son ölçümde emergency eşiğini tutmadı (kör sette 12'de 3 kaçak: aşırı doz, anafilaksi, intihar düşüncesi) → KABUL EDİLMEDİ.
- Bu kaçaklar görülerek RedFlagGuard genişletildi (v3c) → `blind_claude.yml` YANDI; artık kanıt sayılmaz, yalnızca bilgi amaçlı.
- Sonraki doğrulama `blind_user.yml` (ve/veya `blind_sus.yml`) ile, aynı eşiklerle. Bu set üç bilinen türün yanında acil OLMAYAN yakın ifadeler de içermeli (yanlış alarm ölçümü için).
- blind_user.yml 52fd01c560deed9d6312bc8dfcd88d623c5fdb44ddf9fd6a46200a51496d2e20 (2026-11-27, kullanıcı yazdı, 48 cümle; ölçümden önce donduruldu)
