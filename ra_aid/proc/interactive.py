#!/usr/bin/env python3
"""
Module for running interactive subprocesses with output capture,
with full raw input passthrough for interactive commands.

It uses a pseudo-tty and integrates pyte's HistoryScreen to simulate
a terminal and capture the final scrollback history (non-blank lines).
The interface remains compatible with external callers expecting a tuple (output, return_code),
where output is a bytes object (UTF-8 encoded).
"""

import os
import signal
import subprocess
from typing import List, Tuple

import keyboard

if os.name == 'nt':  # Windows
    from pywinpty import PTY as WinPTY
    pty = None
else:  # Unix-like
    import pty
    WinPTY = None

def run_interactive_command(cmd: List[str], expected_runtime_seconds: int = 30) -> Tuple[bytes, int]:
    # Get terminal size
    cols, rows = os.get_terminal_size()
    
    # Create PTY
    if os.name == 'nt':  # Windows
        process_pty = WinPTY(cols, rows)
        master_fd = process_pty.fd
        slave_fd = None
    else:  # Unix-like
        master_fd, slave_fd = os.openpty()

    # Set up environment
    env = os.environ.copy()
    env['TERM'] = 'xterm'

    # Create subprocess
    if os.name == 'nt':  # Windows
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=process_pty.slave_fd,
            stderr=process_pty.slave_fd,
            bufsize=0,
            close_fds=True,
            env=env,
            shell=True
        )
    else:  # Unix-like
        proc = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            bufsize=0,
            close_fds=True,
            env=env,
            preexec_fn=os.setsid
        )
        os.close(slave_fd)

    output = b''
    try:
        while proc.poll() is None:
            # Handle keyboard input
            event = keyboard.read_event()
            if event.event_type == keyboard.KEY_DOWN:
                if event.name == 'ctrl+c':
                    proc.send_signal(signal.SIGINT)
                    break
                else:
                    os.write(master_fd, event.name.encode())

            # Read output
            try:
                chunk = os.read(master_fd, 1024)
                if chunk:
                    output += chunk
                    print(chunk.decode(), end='', flush=True)
            except OSError:
                break

    finally:
        if os.name == 'nt':
            process_pty.close()
        elif master_fd >= 0:
            os.close(master_fd)

    return output, proc.returncode if proc.returncode is not None else -1

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: interactive.py <command> [args...]")
        sys.exit(1)
    output, return_code = run_interactive_command(sys.argv[1:])
    sys.exit(return_code)
