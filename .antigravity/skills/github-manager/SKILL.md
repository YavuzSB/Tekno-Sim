---
name: github-manager
description: GitHub entegrasyonu, CI/CD süreçleri, .gitignore yönetimi ve Octopus AI ile Hibrit Code Review süreçlerini standartlaştırır.
---
# GitHub Manager Yeteneği

Bu yetenek, projenin versiyon kontrolünü ve kalite güvence kapılarını yönetir.

## Hibrit Code Review Kuralı
1. **İç Denetim:** Ajanlar veya kullanıcı kod yazdığında, PR öncesi mutlaka `skeptic-duck` tarafından ROS 2 / Iceoryx mimarisi açısından denetlenir.
2. **Otomatik Test:** Push işleminde `qa-tester`'ın yazdığı testler GitHub Actions üzerinde çalışmalıdır.
3. **Dış Denetim:** PR açıldığında genel C++/Python güvenlik ve syntax hataları için **Octopus AI** devreye girer.

## Git Süreçleri
- Master/Main dalına doğrudan push yapılamaz.
- Tüm devasa `build/` ve `install/` klasörleri `.gitignore` içinde tutulmalıdır.
- AI ajanlarının ürettiği geçici context dosyaları git'e dahil edilmemelidir.
