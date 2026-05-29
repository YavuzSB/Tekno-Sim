#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TeknoSim Performans ve Gecikme Kıyaslama (Benchmark) Scripti
Baş Test Mühendisi (QA Tester)
"""

import os
import sys
import time
import socket
import struct
import json
import subprocess
from datetime import datetime

# Çevresel değişkenler ve parametreler
TEKNOSIM_MODE = os.environ.get("TEKNOSIM_MODE", "SITL").upper()
ITERATIONS = 100
PORT = int(os.environ.get("TEKNOSIM_EMULATOR_PORT", 34567))
IP = os.environ.get("TEKNOSIM_EMULATOR_IP", "127.0.0.1")
MAX_JOINTS = 32

def calculate_metrics(latencies, lost_packets, total_iterations):
    """
    Gecikme listesi ve kayıp paket sayısına göre performans metriklerini hesaplar.
    """
    if not latencies:
        return {
            "min_latency_ms": 0.0,
            "max_latency_ms": 0.0,
            "avg_latency_ms": 0.0,
            "jitter_ms": 0.0,
            "packet_loss_percentage": 100.0
        }

    min_lat = min(latencies)
    max_lat = max(latencies)
    avg_lat = sum(latencies) / len(latencies)
    
    # Jitter (Ardışık gecikme farklarının ortalama mutlak sapması)
    if len(latencies) > 1:
        jitter = sum(abs(latencies[i] - latencies[i-1]) for i in range(1, len(latencies))) / (len(latencies) - 1)
    else:
        jitter = 0.0

    packet_loss_pct = (lost_packets / total_iterations) * 100.0

    return {
        "min_latency_ms": round(min_lat, 4),
        "max_latency_ms": round(max_lat, 4),
        "avg_latency_ms": round(avg_lat, 4),
        "jitter_ms": round(jitter, 4),
        "packet_loss_percentage": round(packet_loss_pct, 2)
    }

def run_sitl_benchmark():
    print(f"\n[SITL MODE] Saf Simülasyon Döngü Testi Başlatılıyor ({ITERATIONS} iterasyon)...")
    
    # C++ SITL Loopback simülasyonunu taklit eden yapılar
    hw_commands = [0.0] * MAX_JOINTS
    hw_positions = [0.0] * MAX_JOINTS
    hw_velocities = [0.0] * MAX_JOINTS
    period = 0.02  # 50 Hz kontrol döngü periyodu

    latencies = []
    lost_packets = 0

    for i in range(ITERATIONS):
        start_time = time.perf_counter()
        
        # 1. Komut güncellemesi (örneğin sinüzoidal referans)
        for j in range(MAX_JOINTS):
            hw_commands[j] = float(i + j)
            
        # 2. C++ sitl_hardware_interface.cpp Loopback simülasyonu
        for j in range(MAX_JOINTS):
            hw_velocities[j] = hw_commands[j]
            hw_positions[j] += hw_velocities[j] * period
            
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        latencies.append(latency_ms)
        
        # Çok hızlı çalıştığı için CPU döngüsünü tamamen bloke etmemek ve
        # gerçekçi bir döngü hızı sağlamak adına minimal bekleme konulabilir.
        # Bu testin 1ms altında kalma garantisini riske atmayan küçük bir gecikmedir.
        time.sleep(0.0001)  # 100 mikrosaniye bekleme

    metrics = calculate_metrics(latencies, lost_packets, ITERATIONS)
    return metrics

def run_hitl_benchmark():
    print(f"\n[HITL MODE] Donanım Emülatör Bağlantı Testi Başlatılıyor ({IP}:{PORT}, {ITERATIONS} iterasyon)...")
    
    # Emülatör python scriptinin konumunu bulalım
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    emulator_path = os.path.join(project_root, "teknosim_core", "hardware_interfaces", "emulator", "esp32_sim.py")
    
    emulator_process = None
    is_emulator_running_externally = False

    # Portun kullanımda olup olmadığını (emülatörün zaten açık olup olmadığını) test edelim.
    ping_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ping_sock.settimeout(0.2)
    try:
        # ActuatorCommands paketi (32 double = 256 byte)
        ping_data = struct.pack('<32d', *([0.0] * MAX_JOINTS))
        ping_sock.sendto(ping_data, (IP, PORT))
        resp, _ = ping_sock.recvfrom(512)
        if len(resp) == 512:
            is_emulator_running_externally = True
            print(">>> Aktif bir ESP32 Emülatörü algılandı. Doğrudan bağlanılıyor.")
    except socket.timeout:
        print(">>> Aktif bir emülatör bulunamadı. Emülatör otomatik başlatılacak.")
    except Exception as e:
        print(f">>> Emülatör kontrol hatası: {e}. Otomatik başlatma denenecek.")
    finally:
        ping_sock.close()

    # Eğer emülatör çalışmıyorsa arka planda başlatalım
    if not is_emulator_running_externally:
        if os.path.exists(emulator_path):
            env = os.environ.copy()
            env["TEKNOSIM_HITL_MODE"] = "1"  # Gecikme simülasyonu aktif edilmesi için
            env["TEKNOSIM_EMULATOR_PORT"] = str(PORT)
            env["TEKNOSIM_EMULATOR_IP"] = IP
            try:
                emulator_process = subprocess.Popen(
                    [sys.executable, emulator_path],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                print(f">>> ESP32 Emülatörü arka planda başlatıldı (PID: {emulator_process.pid}).")
                time.sleep(1.5)  # Soketin hazır hale gelmesi için bekleme
            except Exception as e:
                print(f"Hata: ESP32 Emülatörü başlatılamadı: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Hata: Emülatör dosyası bulunamadı: {emulator_path}", file=sys.stderr)
            sys.exit(1)

    # Test Soketi Kurulumu
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)  # 500 ms timeout

    latencies = []
    lost_packets = 0

    commands = [1.0] * MAX_JOINTS
    send_data = struct.pack('<32d', *commands)

    for i in range(ITERATIONS):
        # 50Hz (20ms) frekans aralığı simüle etmek ve emülatörün paketleri düzgün işleyebilmesi için bekleme ekliyoruz.
        if i > 0:
            time.sleep(0.02)
            
        start_time = time.perf_counter()
        try:
            # ActuatorCommands gönder
            sock.sendto(send_data, (IP, PORT))
            
            # SensorStates al
            resp, addr = sock.recvfrom(1024)
            end_time = time.perf_counter()
            
            if len(resp) == 512:
                # Binary veriyi doğrula
                struct.unpack('<64d', resp)
                latency_ms = (end_time - start_time) * 1000
                latencies.append(latency_ms)
            else:
                lost_packets += 1
                print(f"  [İterasyon {i+1:03d}] Eksik paket alındı! Boyut: {len(resp)} byte, Beklenen: 512 byte.")
        except socket.timeout:
            lost_packets += 1
            print(f"  [İterasyon {i+1:03d}] Paket zaman aşımına uğradı (Timeout)!")
        except Exception as e:
            lost_packets += 1
            print(f"  [İterasyon {i+1:03d}] İletişim Hatası: {e}")

    sock.close()

    # Otomatik başlatılan emülatör sürecini temiz bir şekilde sonlandıralım
    if emulator_process:
        print(">>> Otomatik başlatılan ESP32 Emülatörü durduruluyor...")
        emulator_process.terminate()
        try:
            emulator_process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            emulator_process.kill()
            emulator_process.wait()
        print(">>> ESP32 Emülatörü başarıyla sonlandırıldı.")

    metrics = calculate_metrics(latencies, lost_packets, ITERATIONS)
    return metrics

def main():
    print("======================================================================")
    print("                 TEKNOSIM PERFORMANS TEST SCRIPTI                     ")
    print("======================================================================")
    print(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Çalışma Modu: {TEKNOSIM_MODE}")
    
    if TEKNOSIM_MODE == "HITL":
        metrics = run_hitl_benchmark()
        latency_threshold = 35.0  # ms
    else:
        # Varsayılan veya SITL modu
        metrics = run_sitl_benchmark()
        latency_threshold = 1.0  # ms

    # Sınır Değer Doğrulamaları (Assertions)
    success = True
    reasons = []

    if metrics["avg_latency_ms"] >= latency_threshold:
        success = False
        reasons.append(f"Ortalama gecikme ({metrics['avg_latency_ms']} ms) sınır değerin ({latency_threshold} ms) üzerinde!")

    if metrics["packet_loss_percentage"] > 0.0:
        success = False
        reasons.append(f"Paket kaybı ({metrics['packet_loss_percentage']}%) tespit edildi! Beklenen: %0.")

    # Raporlama ve Ekrana Yazdırma
    print("\n========================= TEST SONUÇLARI =========================")
    print(f"Mod                : {TEKNOSIM_MODE}")
    print(f"Toplam İterasyon   : {ITERATIONS}")
    print(f"Min Gecikme (RTT)  : {metrics['min_latency_ms']:.4f} ms")
    print(f"Maks Gecikme (RTT) : {metrics['max_latency_ms']:.4f} ms")
    print(f"Ortalama Gecikme   : {metrics['avg_latency_ms']:.4f} ms (Eşik: < {latency_threshold} ms)")
    print(f"Jitter             : {metrics['jitter_ms']:.4f} ms")
    print(f"Paket Kaybı        : {metrics['packet_loss_percentage']}% (Eşik: %0)")
    print("------------------------------------------------------------------")
    if success:
        print("DURUM              : BAŞARILI (Tüm sınırlar doğrulandı)")
    else:
        print("DURUM              : BAŞARISIZ (Sınır aşımı tespit edildi!)")
        for reason in reasons:
            print(f"  - Hata: {reason}")
    print("==================================================================")

    # Sonuçları JSON dosyasına kaydetme
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results_file = os.path.join(project_root, "benchmark_results.json")
    
    output_data = {
        "mode": TEKNOSIM_MODE,
        "iterations": ITERATIONS,
        "min_latency_ms": metrics["min_latency_ms"],
        "max_latency_ms": metrics["max_latency_ms"],
        "avg_latency_ms": metrics["avg_latency_ms"],
        "jitter_ms": metrics["jitter_ms"],
        "packet_loss_percentage": metrics["packet_loss_percentage"],
        "success": success,
        "timestamp": datetime.now().isoformat(),
        "reasons": reasons
    }

    try:
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        print(f"Sonuçlar başarıyla kaydedildi: {results_file}")
    except Exception as e:
        print(f"Hata: Sonuçlar JSON dosyasına kaydedilemedi: {e}", file=sys.stderr)

    # Eğer başarısızlık varsa sıfırdan farklı çıkış kodu ile CI/CD hattını patlat
    if not success:
        sys.exit(1)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
