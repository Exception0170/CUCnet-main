import datetime
import re
import subprocess
import time
from datetime import timedelta

import psutil


def get_service_status(service_name, name):
    """
    Check systemctl status of a service and return its state and uptime
    
    Args:
        service_name (str): Name of the systemd service
        
    Returns:
        dict: Dictionary containing service name, state, and uptime
    """
    try:
        # Run systemctl status command
        result = subprocess.run(
            ['systemctl', 'status', service_name],
            capture_output=True,
            text=True,
            timeout=5  # Timeout after 5 seconds
        )

        # Parse the output
        output = result.stdout

        # Extract active state
        active_line = [line for line in output.split('\n') if 'Active:' in line]
        if active_line:
            active_text = active_line[0]
            if 'active (running)' in active_text or (
                    service_name == 'wg-quick@wg0' and 'active (exited)' in active_text):
                state = 'Active'
            else:
                state = 'Failed'
        else:
            state = 'Unknown'

        # Extract uptime
        # Now get the uptime specifically
        uptime = 'N/A'
        if state == 'Active':
            # Use systemctl show to get the active enter timestamp
            show_result = subprocess.run(
                ['systemctl', 'show', service_name, '--property=ActiveEnterTimestamp'],
                capture_output=True,
                text=True,
                timeout=3
            )

            if show_result.returncode == 0:
                timestamp_line = show_result.stdout.strip()
                if 'ActiveEnterTimestamp=' in timestamp_line:
                    # Extract the timestamp
                    timestamp_str = timestamp_line.split('=', 1)[1]

                    try:
                        # Parse the systemd timestamp (format: "Day YYYY-MM-DD HH:MM:SS TIMEZONE")
                        # Example: "Tue 2023-10-10 14:30:45 UTC"
                        dt = datetime.datetime.strptime(timestamp_str, "%a %Y-%m-%d %H:%M:%S %Z")
                        uptime_seconds = (datetime.datetime.now() - dt).total_seconds()

                        # Convert to human readable format
                        uptime = str(timedelta(seconds=int(uptime_seconds)))
                        # Remove milliseconds if present
                        if '.' in uptime:
                            uptime = uptime.split('.')[0]

                    except ValueError:
                        # If parsing fails, try alternative approach
                        uptime = get_uptime_alternative(service_name)
            else:
                uptime = get_uptime_alternative(service_name)

        return {
            'name': name,
            'state': state,
            'uptime': uptime
        }

    except subprocess.TimeoutExpired:
        return {
            'name': name,
            'state': 'Timeout',
            'uptime': 'N/A'
        }
    except subprocess.CalledProcessError:
        return {
            'name': name,
            'state': 'Not Found',
            'uptime': 'N/A'
        }
    except Exception as e:
        return {
            'name': name,
            'state': f'Error: {str(e)}',
            'uptime': 'N/A'
        }


def get_uptime_alternative(service_name):
    """Alternative method to get uptime using systemctl status"""
    try:
        result = subprocess.run(
            ['systemctl', 'status', service_name],
            capture_output=True,
            text=True,
            timeout=3
        )

        if result.returncode == 0:
            output = result.stdout
            # Look for the active line with time information
            for line in output.split('\n'):
                if 'Active: active (running)' in line:
                    # Extract time information like "3 days, 12:34:56" or "12:34:56"
                    time_match = re.search(r'(\d+ days, )?(\d+:\d+:\d+)', line)
                    if time_match:
                        return time_match.group(0).replace(' days, ', ' days ')

        return 'N/A'
    except:
        return 'N/A'


def check_process_running(process_cmd, name):
    """
    Check if a process with the given command is running
    
    Args:
        process_cmd (str): Process command to check (e.g., 'python3 bot.py')
        
    Returns:
        dict: Dictionary containing process name, state, and uptime
    """
    try:
        # Check all running processes
        running = False
        uptime_seconds = 0
        process_name = process_cmd
        current_time = time.time()

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                # Check if the process command matches
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if process_cmd in cmdline:
                    running = True
                    # Calculate uptime
                    create_time = proc.info['create_time']
                    uptime_seconds = current_time - create_time
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        if running:
            # Convert uptime to human readable format
            uptime = str(timedelta(seconds=int(uptime_seconds)))
            # Remove milliseconds if present
            if '.' in uptime:
                uptime = uptime.split('.')[0]

            return {
                'name': name,
                'state': 'Active',
                'uptime': uptime,
                'type': 'process'
            }
        else:
            return {
                'name': name,
                'state': 'Not Running',
                'uptime': 'N/A',
                'type': 'process'
            }

    except Exception as e:
        return {
            'name': name,
            'state': f'Error: {str(e)}',
            'uptime': 'N/A',
            'type': 'process'
        }


def check_multiple_services(service_list, process_list):
    """
    Check status of multiple services
    
    Args:
        service_list (list): List of service names to check
        
    Returns:
        list: List of dictionaries with service status information
    """
    results = []
    for service, name in service_list:
        results.append(get_service_status(service, name))
    for process, name in process_list:
        results.append(check_process_running(process, name))
    return results
