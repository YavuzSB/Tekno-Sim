import os
import sys
import json
import time
import unittest
import threading
import urllib.request
import urllib.error
from unittest.mock import MagicMock, patch

# Add workspace directory to python path and import sidecar_server
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import teknosim_core.utils.sidecar_server as sidecar

class TestSidecarHTTPServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Starts the sidecar HTTP server on a random free port in a background thread."""
        # Port 0 tells the OS to select any free ephemeral port
        cls.server = sidecar.ThreadingHTTPServer(('127.0.0.1', 0), sidecar.SidecarHTTPHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        logging = MagicMock() # Suppress logging during tests

    @classmethod
    def tearDownClass(cls):
        """Stops the background HTTP server."""
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join()

    def setUp(self):
        """Resets global server state before each test."""
        sidecar.active_launch_processes.clear()
        sidecar.active_build_process = None
        # Ensure the lock is unlocked
        if sidecar.process_lock.locked():
            try:
                sidecar.process_lock.release()
            except RuntimeError:
                pass

    def test_options_cors_preflight(self):
        """Tests that OPTIONS requests return CORS preflight headers."""
        req = urllib.request.Request(self.base_url + "/projects", method="OPTIONS")
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 204)
            headers = dict(response.info())
            self.assertEqual(headers.get('Access-Control-Allow-Origin'), '*')
            self.assertIn('Access-Control-Allow-Methods', headers)

    def test_get_projects_empty(self):
        """Tests that GET /projects returns an empty list if directory is empty."""
        with patch("teknosim_core.utils.sidecar_server.os.path.exists", return_value=True), \
             patch("teknosim_core.utils.sidecar_server.os.listdir", return_value=[]):
            
            with urllib.request.urlopen(self.base_url + "/projects") as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode('utf-8'))
                self.assertEqual(data, {"projects": []})

    def test_get_projects_valid(self):
        """Tests that GET /projects successfully scans and lists valid ROS 2 competition packages."""
        def mock_exists(path):
            if "package.xml" in path or "competition.launch.py" in path:
                return True
            if "teknosim_apps" in path:
                return True
            return False

        def mock_isdir(path):
            if path.endswith("valid_project") or path.endswith("teknosim_apps"):
                return True
            return False

        def mock_listdir(path):
            if path.endswith("teknosim_apps"):
                return ["valid_project"]
            return []

        with patch("teknosim_core.utils.sidecar_server.os.path.exists", side_effect=mock_exists), \
             patch("teknosim_core.utils.sidecar_server.os.path.isdir", side_effect=mock_isdir), \
             patch("teknosim_core.utils.sidecar_server.os.listdir", side_effect=mock_listdir):
            
            with urllib.request.urlopen(self.base_url + "/projects") as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode('utf-8'))
                self.assertEqual(len(data["projects"]), 1)
                self.assertEqual(data["projects"][0]["name"], "valid_project")

    def test_start_project_success(self):
        """Tests that POST /project/start successfully launches a subprocess in setsid group."""
        mock_proc = MagicMock()
        mock_proc.pid = 4444
        
        payload = json.dumps({"project_name": "rover_template", "mode": "SITL"}).encode('utf-8')
        req = urllib.request.Request(
            self.base_url + "/project/start",
            data=payload,
            headers={'Content-Type': 'application/json'}
        )

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch("os.environ", {}):
            
            with urllib.request.urlopen(req) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode('utf-8'))
                self.assertEqual(data["status"], "success")
                self.assertEqual(data["pid"], 4444)
                
                # Check process group configuration setsid
                mock_popen.assert_called_once()
                kwargs = mock_popen.call_args[1]
                self.assertIn("preexec_fn", kwargs)
                self.assertEqual(kwargs["preexec_fn"], os.setsid)

    def test_start_project_conflict(self):
        """Tests that starting a project fails with 409 Conflict if a build is active."""
        sidecar.active_build_process = MagicMock()
        
        payload = json.dumps({"project_name": "rover_template", "mode": "SITL"}).encode('utf-8')
        req = urllib.request.Request(
            self.base_url + "/project/start",
            data=payload,
            headers={'Content-Type': 'application/json'}
        )

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 409)

    def test_stop_project_by_pid(self):
        """Tests that POST /project/stop terminates a specific active process by PID."""
        mock_proc = MagicMock()
        mock_proc.poll = MagicMock(return_value=0)
        sidecar.active_launch_processes[123] = mock_proc

        req = urllib.request.Request(
            self.base_url + "/project/stop?pid=123",
            data=b"",
            method="POST"
        )

        with patch("os.getpgid", return_value=120) as mock_getpgid, \
             patch("os.killpg") as mock_killpg:
            
            with urllib.request.urlopen(req) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode('utf-8'))
                self.assertEqual(data["status"], "success")
                self.assertNotIn(123, sidecar.active_launch_processes)
                mock_getpgid.assert_called_with(123)
                mock_killpg.assert_called_with(120, 2)  # SIGINT

    def test_stop_all_projects(self):
        """Tests that POST /project/stop terminates all launch processes when PID is omitted."""
        mock_proc1 = MagicMock()
        mock_proc1.poll = MagicMock(return_value=0)
        mock_proc2 = MagicMock()
        mock_proc2.poll = MagicMock(return_value=0)
        
        sidecar.active_launch_processes[11] = mock_proc1
        sidecar.active_launch_processes[22] = mock_proc2

        req = urllib.request.Request(
            self.base_url + "/project/stop",
            data=b"",
            method="POST"
        )

        with patch("os.getpgid", side_effect=lambda x: x), \
             patch("os.killpg") as mock_killpg:
            
            with urllib.request.urlopen(req) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode('utf-8'))
                self.assertEqual(data["status"], "success")
                self.assertEqual(len(sidecar.active_launch_processes), 0)
                self.assertEqual(mock_killpg.call_count, 2)

    def test_ping_endpoint(self):
        """Tests that POST /ping records the request timestamp correctly."""
        req = urllib.request.Request(
            self.base_url + "/ping",
            data=b"",
            method="POST"
        )
        
        with patch("time.time", return_value=999999999.0):
            with urllib.request.urlopen(req) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode('utf-8'))
                self.assertEqual(data["status"], "ok")
                self.assertEqual(data["timestamp"], 999999999.0)
                self.assertEqual(sidecar.last_ping_time, 999999999.0)

if __name__ == "__main__":
    unittest.main()
