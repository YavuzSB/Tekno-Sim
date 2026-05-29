import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

# Add workspace directory to python path and import sidecar_server
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import teknosim_core.utils.sidecar_server as sidecar

class TestHeartbeatWatchdog(unittest.TestCase):

    def setUp(self):
        """Reset global process tracking states."""
        sidecar.active_launch_processes.clear()
        sidecar.last_ping_time = time.time()

    def test_kill_process_group_sigint_success(self):
        """Tests that kill_process_group successfully closes a process group with SIGINT."""
        mock_proc = MagicMock()
        mock_proc.poll = MagicMock(return_value=0)  # successfully exited on SIGINT
        pid = 5555
        sidecar.active_launch_processes[pid] = mock_proc

        with patch("os.getpgid", return_value=5550) as mock_getpgid, \
             patch("os.killpg") as mock_killpg:
            
            sidecar.kill_process_group(pid)
            
            mock_getpgid.assert_called_once_with(pid)
            mock_killpg.assert_called_once_with(5550, 2)  # SIGINT (2)
            self.assertNotIn(pid, sidecar.active_launch_processes)

    def test_kill_process_group_sigkill_fallback(self):
        """Tests that kill_process_group falls back to SIGKILL if the process fails to close with SIGINT within timeout."""
        mock_proc = MagicMock()
        mock_proc.poll = MagicMock(return_value=None)  # process stays active
        pid = 6666
        sidecar.active_launch_processes[pid] = mock_proc

        # Mock time.sleep to fast forward the 3-second timeout wait
        with patch("os.getpgid", return_value=6660), \
             patch("os.killpg") as mock_killpg, \
             patch("time.sleep", return_value=None):
            
            sidecar.kill_process_group(pid)
            
            # Should first send SIGINT (2), then fall back to SIGKILL (9)
            mock_killpg.assert_any_call(6660, 2)
            mock_killpg.assert_any_call(6660, 9)
            self.assertNotIn(pid, sidecar.active_launch_processes)

    def test_kill_all_launches(self):
        """Tests that kill_all_launches terminates all actively tracked launch processes."""
        mock_proc1 = MagicMock()
        mock_proc1.poll = MagicMock(return_value=0)
        mock_proc2 = MagicMock()
        mock_proc2.poll = MagicMock(return_value=0)

        sidecar.active_launch_processes[100] = mock_proc1
        sidecar.active_launch_processes[200] = mock_proc2

        with patch("os.getpgid", side_effect=lambda x: x), \
             patch("os.killpg") as mock_killpg:
            
            count = sidecar.kill_all_launches()
            
            self.assertEqual(count, 2)
            self.assertEqual(len(sidecar.active_launch_processes), 0)

    def test_heartbeat_watchdog_cleanup_trigger(self):
        """Tests that the watchdog cleans up zombified processes when the last ping time exceeds 30 seconds."""
        mock_proc = MagicMock()
        mock_proc.poll = MagicMock(return_value=0)
        sidecar.active_launch_processes[7777] = mock_proc

        # Mock time.sleep inside watchdog loop to raise KeyboardInterrupt on second iteration to break loop
        sleep_count = 0
        def mock_sleep(seconds):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count > 1:
                raise KeyboardInterrupt()

        # Mock time.time to return a fixed time, and set last_ping_time to 40 seconds before
        fixed_time = 1000.0
        sidecar.last_ping_time = fixed_time - 40.0

        with patch("time.sleep", side_effect=mock_sleep), \
             patch("time.time", return_value=fixed_time), \
             patch("os.getpgid", return_value=7770), \
             patch("os.killpg") as mock_killpg:
            
            try:
                sidecar.heartbeat_watchdog()
            except KeyboardInterrupt:
                pass

            # Since the ping was older than 30s, active process 7777 should be terminated
            mock_killpg.assert_called_with(7770, 2)
            self.assertNotIn(7777, sidecar.active_launch_processes)

    def test_heartbeat_watchdog_no_trigger_within_time(self):
        """Tests that the watchdog does NOT clean up processes if the last ping was received within the 30-second window."""
        mock_proc = MagicMock()
        sidecar.active_launch_processes[8888] = mock_proc

        sleep_count = 0
        def mock_sleep(seconds):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count > 1:
                raise KeyboardInterrupt()

        fixed_time = 1000.0
        sidecar.last_ping_time = fixed_time - 10.0

        with patch("time.sleep", side_effect=mock_sleep), \
             patch("time.time", return_value=fixed_time), \
             patch("os.killpg") as mock_killpg:
            
            try:
                sidecar.heartbeat_watchdog()
            except KeyboardInterrupt:
                pass

            # Since last ping was within 30s, process 8888 must NOT be killed
            mock_killpg.assert_not_called()
            self.assertIn(8888, sidecar.active_launch_processes)

if __name__ == "__main__":
    unittest.main()
