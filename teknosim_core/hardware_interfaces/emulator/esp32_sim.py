#!/usr/bin/env python3
import os
import time
import numpy as np
import asyncio
import logging
import struct
import random

# Detaylı loglama konfigürasyonu
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) %(message)s'
)

class ESP32Simulator:
    """
    ESP32 Donanımını taklit eden asenkron UDP sunucusu.
    Gerçek dünya senaryolarını test etmek için sensör gürültüsü (Gaussian Noise) ve 
    kablosuz iletişim gecikmesi (Latency) uygular.
    """
    def __init__(self):
        self.hitl_mode = os.environ.get("TEKNOSIM_HITL_MODE", "0") == "1"
        self.port = int(os.environ.get("TEKNOSIM_EMULATOR_PORT", 34567))
        self.ip = os.environ.get("TEKNOSIM_EMULATOR_IP", "0.0.0.0")
        
        # State Gönderim Modu:
        # - "joint_state": Her joint için [pos, vel] çifti döner (Boyut: 2 * N)
        # - "position_only": Her joint için sadece pos döner (Boyut: N)
        # - "velocity_only": Her joint için sadece vel döner (Boyut: N)
        self.state_mode = os.environ.get("TEKNOSIM_EMULATOR_STATE_MODE", "joint_state")
        
        # Fiziksel simülasyon durumları (Joint States)
        self.positions = {}   # joint_index -> position
        self.velocities = {}  # joint_index -> velocity
        self.last_update_time = None
        
        # Gaussian Gürültü Standart Sapmaları (HITL modu aktifse uygulanır)
        self.pos_noise_std = 0.01  # Pozisyon gürültüsü std sapma (radyan veya metre)
        self.vel_noise_std = 0.02  # Hız gürültüsü std sapma (rad/s veya m/s)
        
        logging.info(f"ESP32Simulator başlatıldı.")
        logging.info(f"  - Dinleme Adresi: {self.ip}:{self.port}")
        logging.info(f"  - HITL Modu: {'AKTİF' if self.hitl_mode else 'PASİF'}")
        logging.info(f"  - Durum Modu: {self.state_mode}")
        if self.hitl_mode:
            logging.info(f"  - Gaussian Gürültü Aktif (Pos std: {self.pos_noise_std}, Vel std: {self.vel_noise_std})")
            logging.info("  - Asenkron Kablosuz Ağ Gecikmesi Aktif (5-15 ms çift yönlü)")

    async def handle_packet(self, data, addr, transport):
        """
        Gelen C++ donanım eklentisi paketlerini asenkron çözer,
        fiziksel simülasyonu koşturur ve durumu geri iletir.
        """
        # 1. Kablosuz Ağ Gecikmesi Simülasyonu - Gelen (RX) yönü
        if self.hitl_mode:
            rx_latency = random.uniform(0.005, 0.015) # 5-15 ms arası
            await asyncio.sleep(rx_latency)
            
        # 2. Binary Struct Çözümleme (double commands[N])
        n_bytes = len(data)
        if n_bytes % 8 != 0:
            logging.warning(f"[{addr}] Geçersiz paket boyutu alındı: {n_bytes} bayt (8'in katı olmalı).")
            return
            
        n_commands = n_bytes // 8
        if n_commands == 0:
            logging.warning(f"[{addr}] Boş komut paketi alındı.")
            return
            
        try:
            # Gelen veriyi little-endian double array olarak çözüyoruz
            commands = struct.unpack(f"<{n_commands}d", data)
        except Exception as e:
            logging.error(f"[{addr}] Paket struct çözümlenirken hata: {e}")
            return
            
        # 3. Fiziksel Simülasyon (Diferansiyel Sürüş / Eklem Entegrasyonu)
        current_time = time.time()
        if self.last_update_time is None:
            dt = 0.02  # Varsayılan başlangıç zaman adımı (50 Hz)
        else:
            dt = current_time - self.last_update_time
            # Aşırı sıçramaları ve duraksamaları filtrele
            dt = min(max(dt, 0.001), 0.5)
            
        self.last_update_time = current_time
        
        # Eklem entegrasyonu (Joint Integration)
        for i in range(n_commands):
            cmd_vel = commands[i]
            if np.isnan(cmd_vel) or np.isinf(cmd_vel):
                cmd_vel = 0.0
                
            self.velocities[i] = cmd_vel
            if i not in self.positions:
                self.positions[i] = 0.0
                
            # Basit Euler Entegrasyonu (Position = Position + Velocity * dt)
            self.positions[i] += cmd_vel * dt
            
        # 4. Geri Dönecek Durumları (States) Hazırlama
        states = []
        for i in range(n_commands):
            pos = self.positions[i]
            vel = self.velocities[i]
            
            # Gaussian gürültü ekleme
            if self.hitl_mode:
                pos += np.random.normal(0, self.pos_noise_std)
                vel += np.random.normal(0, self.vel_noise_std)
                
            if self.state_mode == "joint_state":
                states.extend([pos, vel])
            elif self.state_mode == "position_only":
                states.append(pos)
            elif self.state_mode == "velocity_only":
                states.append(vel)
                
        # 5. Durumları Paketleme (double states[M])
        n_states = len(states)
        try:
            response_data = struct.pack(f"<{n_states}d", *states)
        except Exception as e:
            logging.error(f"[{addr}] Yanıt paketi struct oluşturulurken hata: {e}")
            return
            
        # 6. Kablosuz Ağ Gecikmesi Simülasyonu - Giden (TX) yönü
        if self.hitl_mode:
            tx_latency = random.uniform(0.005, 0.015) # 5-15 ms arası
            await asyncio.sleep(tx_latency)
            
        # 7. C++ Donanım Eklentisine Yanıt Gönder
        try:
            transport.sendto(response_data, addr)
            logging.info(f"[{addr}] Komutlar alındı: {[round(c, 4) for c in commands]} | Yanıt gönderildi ({self.state_mode}): {[round(s, 4) for s in states]}")
        except Exception as e:
            logging.error(f"[{addr}] Yanıt gönderilirken hata oluştu: {e}")

class ESP32UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, simulator):
        self.simulator = simulator
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        logging.info("UDP Dinleyici soketi başarıyla oluşturuldu.")

    def datagram_received(self, data, addr):
        # Asenkron işlemeyi tetikler, bu sayede sunucu yeni gelen paketleri bloklamadan bekleyebilir.
        asyncio.create_task(self.simulator.handle_packet(data, addr, self.transport))

    def error_received(self, exc):
        logging.error(f"UDP Protokol hatası alındı: {exc}")

    def connection_lost(self, exc):
        logging.info("UDP Dinleyici soketi kapatıldı.")

async def run_server():
    # Çevresel değişkenlerden yapılandırmayı oku veya varsayılanları kullan
    if "TEKNOSIM_HITL_MODE" not in os.environ:
        logging.info("TEKNOSIM_HITL_MODE ayarlanmamış, varsayılan olarak '1' (Aktif) yapılıyor.")
        os.environ["TEKNOSIM_HITL_MODE"] = "1"
        
    simulator = ESP32Simulator()
    
    loop = asyncio.get_running_loop()
    logging.info(f"UDP sunucusu başlatılıyor: {simulator.ip}:{simulator.port}...")
    
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ESP32UDPProtocol(simulator),
        local_addr=(simulator.ip, simulator.port)
    )
    
    try:
        # Sunucunun sürekli açık kalmasını sağla
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logging.info("Sunucu durduruluyor...")
    finally:
        transport.close()

def main():
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logging.info("Simülatör kullanıcı tarafından sonlandırıldı.")

if __name__ == "__main__":
    main()
