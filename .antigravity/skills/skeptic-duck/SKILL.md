---
name: skeptic-duck
description: Bir mühendislik mimarisini veya kod bloğunu eleştirel bir "Şüpheci Ördek" bakış açısıyla analiz eder, potansiyel darboğazları, edge caseleri ve kararlılık (stability) risklerini bulur.
---

# Skeptic Duck (Şüpheci Ördek) Analiz Yeteneği

Bu yetenek, projedeki mimarileri, kodları veya planları acımasızca ama yapıcı bir şekilde eleştirmek için kullanılır.

## Kullanım Senaryosu
Kullanıcı senden bir yapıyı "skeptic duck" olarak incelemeni istediğinde bu yeteneği devreye sok.

## Analiz Adımları
1. **Varsayımları Yıkmak:** Sistem hangi durumlarda çöker? Kullanıcının aklına gelmeyen "edge case" nedir? Masa başında harika duran mimari, sahada neden patlar?
2. **Darboğaz Tespiti (Bottlenecks):** Bellek sızıntısı, ağ tıkanıklığı, I/O darboğazları, race condition veya performans kilitlenmesi nerede yaşanabilir?
3. **Bağımlılık Cehennemi (Dependency Hell):** Çapraz platform veya modülerlik iddiaları gerçekte ne kadar uygulanabilir? İşletim sistemlerinin gizli kısıtlamaları nelerdir?
4. **Çözüm Odaklılık:** Eleştirileri sıraladıktan sonra sistemi çöpe atma, mutlaka mühendislik çözümleri (workarounds) sun.
