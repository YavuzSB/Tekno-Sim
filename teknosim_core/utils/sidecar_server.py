#!/usr/bin/env python3
import os
import sys
import time
import json
import signal
import logging
import threading
import subprocess
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Loglama konfigürasyonu
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Global Süreç Yönetim Değişkenleri
process_lock = threading.Lock()
active_build_process = None
active_launch_processes = {}  # pid (int) -> subprocess.Popen
last_ping_time = time.time()

# Yardımcı Süreç Temizleme Fonksiyonları
def kill_process_group(pid):
    """
    Belirtilen PID'nin ait olduğu Unix süreç grubunu (Process Group)
    temiz bir şekilde kapatır. ROS 2 düğümlerinin düzgünce sonlanması
    için önce SIGINT gönderir, kapanmazsa SIGKILL ile zorlar.
    """
    global active_launch_processes
    try:
        pgid = os.getpgid(pid)
        logging.info(f"Süreç grubuna ({pgid}) SIGINT gönderiliyor...")
        os.killpg(pgid, signal.SIGINT)
        
        # Sürecin kapanmasını maksimum 3 saniye bekle
        proc = active_launch_processes.get(pid)
        if proc:
            for _ in range(30):  # 30 * 100ms = 3 saniye
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
                
            # Eğer hala sonlanmadıysa SIGKILL ile zorla
            if proc.poll() is None:
                logging.warning(f"Süreç ({pid}) SIGINT ile sonlanmadı. SIGKILL gönderiliyor!")
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except Exception as e:
                    logging.error(f"SIGKILL gönderme hatası: {e}")
                
        if pid in active_launch_processes:
            del active_launch_processes[pid]
            
    except ProcessLookupError:
        logging.info(f"Süreç ({pid}) zaten sonlanmış.")
        if pid in active_launch_processes:
            del active_launch_processes[pid]
    except Exception as e:
        logging.error(f"Süreç grubu {pid} kapatılırken hata oluştu: {e}")
        if pid in active_launch_processes:
            del active_launch_processes[pid]

def kill_all_launches():
    """
    Çalışmakta olan tüm launch süreçlerini temizler.
    """
    global active_launch_processes
    pids = list(active_launch_processes.keys())
    count = len(pids)
    if count > 0:
        logging.info(f"{count} adet aktif launch süreci temizleniyor...")
        for pid in pids:
            kill_process_group(pid)
    return count

# Arka Plan Zombi Süreç Koruyucusu (Heartbeat Watchdog)
def heartbeat_watchdog():
    """
    Foxglove veya kontrol arayüzünden gelen pingleri izler.
    Eğer son 30 saniye boyunca ping alınamazsa çalışan tüm ros2 launch
    süreçlerini zombi kalmaması için sonlandırır.
    """
    global last_ping_time
    logging.info("Heartbeat watchdog görevi başlatıldı.")
    while True:
        time.sleep(5)
        elapsed = time.time() - last_ping_time
        if elapsed > 30:
            if len(active_launch_processes) > 0:
                logging.warning(f"Heartbeat zaman aşımı! Son ping {elapsed:.2f} saniye önce alındı. Zombi süreçler temizleniyor...")
                kill_all_launches()

# Watchdog görevini arka planda başlat
threading.Thread(target=heartbeat_watchdog, daemon=True).start()

class SidecarHTTPHandler(BaseHTTPRequestHandler):

    def send_cors_headers(self):
        """Foxglove Studio gibi localhost üzerinden bağlanan istemciler için engelsiz CORS."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')

    def do_OPTIONS(self):
        """CORS preflight isteklerine 204 No Content ile cevap verir."""
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        if parsed_url.path in ["/", "/index.html"]:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            html_path = os.path.join(current_dir, "index.html")
            
            if os.path.exists(html_path):
                self.send_response(200)
                self.send_cors_headers()
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(html_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.send_cors_headers()
                self.end_headers()
            return
            
        elif parsed_url.path == "/projects":
            # teknosim_apps/ dizini altındaki klasörleri tarar
            current_dir = os.path.dirname(os.path.abspath(__file__))
            apps_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "teknosim_apps"))
            
            if not os.path.exists(apps_dir):
                apps_dir = "/workspace/teknosim_apps"
                
            logging.info(f"Projeler taranıyor: {apps_dir}")
            valid_projects = []
            
            if os.path.exists(apps_dir):
                try:
                    search_dirs = [apps_dir]
                    # Scan 1-level deep subdirectories (like 'templates/') to support modular project structure
                    for item in os.listdir(apps_dir):
                        sub_path = os.path.join(apps_dir, item)
                        if os.path.isdir(sub_path) and item not in [".", "..", "__pycache__"]:
                            search_dirs.append(sub_path)

                    for s_dir in search_dirs:
                        for item in os.listdir(s_dir):
                            item_path = os.path.join(s_dir, item)
                            if os.path.isdir(item_path):
                                pkg_xml = os.path.join(item_path, "package.xml")
                                launch_py = os.path.join(item_path, "launch", "competition.launch.py")
                                
                                if os.path.exists(pkg_xml) and os.path.exists(launch_py):
                                    valid_projects.append({
                                        "name": item,
                                        "path": item_path
                                    })
                except Exception as e:
                    logging.error(f"Projeler taranırken hata: {e}")
                    self.send_response(500)
                    self.send_cors_headers()
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"detail": f"Dizin tarama hatası: {str(e)}"}).encode('utf-8'))
                    return
            
            self.send_response(200)
            self.send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"projects": valid_projects}).encode('utf-8'))
            
        else:
            self.send_response(404)
            self.send_cors_headers()
            self.end_headers()

    def do_POST(self):
        global active_build_process, active_launch_processes, last_ping_time
        
        parsed_url = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = b""
        if content_length > 0:
            post_data = self.rfile.read(content_length)
            
        # JSON verisini çözümle (varsa)
        req_data = {}
        if post_data:
            try:
                req_data = json.loads(post_data.decode('utf-8'))
            except Exception:
                pass
                
        if parsed_url.path == "/project/build":
            project_name = req_data.get("project_name")
            if not project_name:
                self.send_response(400)
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"detail": "project_name is required"}).encode('utf-8'))
                return
                
            # Derleme veya çalıştırma aktif mi kontrol et (Process Lock)
            if not process_lock.acquire(blocking=False):
                self.send_response(409)
                self.send_cors_headers()
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"detail": "A build or launch process is already active. Please stop it first."}).encode('utf-8'))
                return
                
            try:
                # 1. Aktif launch süreçlerini durdur
                kill_all_launches()
                
                # 2. Çalışma dizini
                cwd_path = "/ros2_ws" if os.path.exists("/ros2_ws") else ("/workspace" if os.path.exists("/workspace") else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
                
                # 3. colcon build başlat
                ros_setup = "/opt/ros/humble/setup.bash"
                if not os.path.exists(ros_setup):
                    ros_setup = "/opt/ros/jazzy/setup.bash"
                build_cmd = f"source {ros_setup} && colcon build --base-paths /workspace/teknosim_core /workspace/teknosim_apps --packages-select {project_name}"
                cmd = ["nice", "-n", "10", "bash", "-c", build_cmd]
                
                self.send_response(200)
                self.send_cors_headers()
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'close')
                self.end_headers()
                
                self.wfile.write(f"data: Starting build: {' '.join(cmd)}\n\n".encode('utf-8'))
                self.wfile.flush()
                
                active_build_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=cwd_path,
                    preexec_fn=os.setsid
                )
                
                # Çıktıları anlık olarak SSE (Server-Sent Events) formatında akıt
                while True:
                    line = active_build_process.stdout.readline()
                    if not line:
                        break
                    self.wfile.write(f"data: {line.decode('utf-8')}\n\n".encode('utf-8'))
                    self.wfile.flush()
                    
                active_build_process.wait()
                exit_code = active_build_process.returncode
                self.wfile.write(f"data: [Build Finished] Exit Code: {exit_code}\n\n".encode('utf-8'))
                self.wfile.flush()
                
            except Exception as e:
                try:
                    self.wfile.write(f"data: [Build Error] {str(e)}\n\n".encode('utf-8'))
                    self.wfile.flush()
                except Exception:
                    pass
            finally:
                active_build_process = None
                process_lock.release()
                self.close_connection = True
                
        elif parsed_url.path in ["/project/start", "/project/launch"]:
            project_name = req_data.get("project_name")
            mode = req_data.get("mode", "SITL")
            
            if not project_name:
                self.send_response(400)
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"detail": "project_name is required"}).encode('utf-8'))
                return
                
            # Derleme aktifse çalıştırmayı engelle
            if active_build_process is not None:
                self.send_response(409)
                self.send_cors_headers()
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"detail": "A build process is currently running. Cannot launch application."}).encode('utf-8'))
                return
                
            # 1. Çevresel değişkeni ayarla
            os.environ["TEKNOSIM_MODE"] = mode.upper()
            logging.info(f"TEKNOSIM_MODE set to: {mode.upper()}")
            
            # 2. Çalışma dizini ve komutları ayarla
            cwd_path = "/ros2_ws" if os.path.exists("/ros2_ws") else ("/workspace" if os.path.exists("/workspace") else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
            
            ros_setup = "/opt/ros/humble/setup.bash"
            if not os.path.exists(ros_setup):
                ros_setup = "/opt/ros/jazzy/setup.bash"
            
            local_setup = "/ros2_ws/install/setup.bash"
            if not os.path.exists(local_setup):
                local_setup = "/workspace/install/setup.bash"
                
            setup_cmd = f"source {ros_setup}"
            if os.path.exists(local_setup):
                setup_cmd += f" && source {local_setup}"
            
            launch_cmd = f"{setup_cmd} && ros2 launch {project_name} competition.launch.py"
            cmd = ["bash", "-c", launch_cmd]
            
            try:
                # setsid ile yeni bir process group oluşturularak başlatılır
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=cwd_path,
                    preexec_fn=os.setsid
                )
                
                pid = proc.pid
                active_launch_processes[pid] = proc
                logging.info(f"Launched project: {project_name} in {mode} mode. PID: {pid}")
                
                self.send_response(200)
                self.send_cors_headers()
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "pid": pid,
                    "project_name": project_name,
                    "mode": mode
                }).encode('utf-8'))
                
            except Exception as e:
                logging.error(f"Launch operation failed: {e}")
                self.send_response(500)
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"detail": f"Launch failed: {str(e)}"}).encode('utf-8'))
                
        elif parsed_url.path == "/project/stop":
            # PID'yi query string'den veya gövdeden alabiliriz
            query_params = parse_qs(parsed_url.query)
            pid_str = query_params.get('pid', [None])[0]
            if not pid_str and req_data:
                pid_str = req_data.get("pid")
                
            if pid_str:
                try:
                    pid = int(pid_str)
                    if pid in active_launch_processes:
                        kill_process_group(pid)
                        self.send_response(200)
                        self.send_cors_headers()
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"status": "success", "message": f"Process group {pid} successfully terminated."}).encode('utf-8'))
                    else:
                        self.send_response(404)
                        self.send_cors_headers()
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"detail": f"Active process with PID {pid} not found."}).encode('utf-8'))
                except ValueError:
                    self.send_response(400)
                    self.send_cors_headers()
                    self.end_headers()
            else:
                count = kill_all_launches()
                self.send_response(200)
                self.send_cors_headers()
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": f"Terminated {count} launch processes."}).encode('utf-8'))
                
        elif parsed_url.path in ["/ping", "/project/ping"]:
            last_ping_time = time.time()
            self.send_response(200)
            self.send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "timestamp": last_ping_time}).encode('utf-8'))
            
        else:
            self.send_response(404)
            self.send_cors_headers()
            self.end_headers()

def run_server():
    server_address = ('0.0.0.0', 8000)
    httpd = ThreadingHTTPServer(server_address, SidecarHTTPHandler)
    logging.info("TeknoSim Zero-Dependency Sidecar Server V4.4 running on port 8000...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("Server shutting down...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
