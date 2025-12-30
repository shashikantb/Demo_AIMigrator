import platform
import subprocess
import json
import urllib.request
import sys
import os

def get_os_info():
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=")[1].strip().strip('"')
        return platform.system() + " " + platform.release()
    except:
        return "Unknown Linux"

def get_cpu_cores():
    try:
        return os.cpu_count() or 1
    except:
        return 1

def get_memory_gb():
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if 'MemTotal' in line:
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024, 2)
        return 1.0
    except:
        return 1.0

def get_disk_space():
    try:
        result = subprocess.check_output("df -h / | awk 'NR==2 {print $2}'", shell=True)
        size_str = result.decode().strip()
        # Simplified parsing
        val = float(size_str.replace('G', '').replace('M', '').replace('T', ''))
        # Normalize to GB approx
        if 'T' in size_str: val *= 1024
        if 'M' in size_str: val /= 1024
        return {"/": val}
    except:
        return {"/": 0.0}

def get_services():
    try:
        # Check for common services
        services = []
        common = ["nginx", "apache2", "postgresql", "mysql", "docker", "ssh", "gunicorn"]
        try:
            output = subprocess.check_output("systemctl list-units --type=service --state=running", shell=True).decode()
            for s in common:
                if s in output:
                    services.append(s)
        except:
            pass
        return services
    except:
        return []

def get_open_ports():
    try:
        # Simplistic check using netstat if available, else skip
        # This is hard without sudo often, so return empty list or mock
        return [] 
    except:
        return []

def get_installed_packages():
    try:
        # Try Debian/Ubuntu
        output = subprocess.check_output("dpkg-query -f '${binary:Package}\n' -W", shell=True, stderr=subprocess.DEVNULL)
        return output.decode().strip().split('\n')
    except:
        try:
            # Try RHEL/CentOS
            output = subprocess.check_output("rpm -qa --queryformat '%{NAME}\n'", shell=True, stderr=subprocess.DEVNULL)
            return output.decode().strip().split('\n')
        except:
            return []

def get_system_users():
    users = []
    try:
        with open('/etc/passwd', 'r') as f:
            for line in f:
                parts = line.split(':')
                if len(parts) > 2:
                    uid = int(parts[2])
                    # Capture users with UID >= 1000 (standard users) or root (0)
                    if uid >= 1000 or uid == 0:
                        users.append(parts[0])
    except:
        pass
    return users

def get_crontabs(users):
    crons = {}
    for user in users:
        try:
            # Need sudo for other users usually, but agent runs as root ideally
            # If not root, can only get current user
            output = subprocess.check_output(f"crontab -l -u {user}", shell=True, stderr=subprocess.DEVNULL)
            if output:
                crons[user] = output.decode()
        except:
            pass
    return crons

def get_pm2_processes():
    processes = []
    try:
        # Check if pm2 is installed and get json list
        # Try both direct command and checking path
        cmd = "pm2 jlist"
        if subprocess.call("which pm2", shell=True, stdout=subprocess.DEVNULL) != 0:
             # Try standard paths if not in PATH
             possible_paths = ["/usr/local/bin/pm2", "/usr/bin/pm2", "/opt/node/bin/pm2"]
             for p in possible_paths:
                 if os.path.exists(p):
                     cmd = f"{p} jlist"
                     break
        
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL)
        data = json.loads(output.decode())
        
        for proc in data:
            processes.append({
                "name": proc.get("name"),
                "path": proc.get("pm2_env", {}).get("pm_cwd"),
                "status": proc.get("pm2_env", {}).get("status"),
                "version": proc.get("pm2_env", {}).get("version", "N/A"),
                "script": proc.get("pm2_env", {}).get("pm_exec_path")
            })
    except Exception as e:
        # PM2 likely not installed or error running it
        pass
    return processes

def capture_app_tree(root_path):
    configs = {}
    IGNORE_DIRS = {
        'node_modules', '.git', '.next', '.nuxt', 'dist', 'build', 'coverage',
        '__pycache__', 'venv', '.idea', '.vscode', 'tmp', 'logs', 'log'
    }
    IGNORE_EXTS = {
        '.log', '.lock', '.gz', '.zip', '.tar', '.png', '.jpg', '.jpeg', '.gif',
        '.ico', '.pdf', '.bin', '.exe', '.pyc', '.so', '.dll', '.woff', '.woff2', '.ttf'
    }
    MAX_FILE_SIZE = 100 * 1024
    MAX_TOTAL_FILES = 200
    file_count = 0

    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file_name in files:
            if file_count >= MAX_TOTAL_FILES:
                break

            if any(file_name.endswith(ext) for ext in IGNORE_EXTS):
                continue

            full_path = os.path.join(root, file_name)

            try:
                if os.path.getsize(full_path) > MAX_FILE_SIZE:
                    continue

                rel_path = os.path.relpath(full_path, root_path)

                with open(full_path, 'r', errors='ignore') as f:
                    content = f.read()
                    if '\0' in content:
                        continue
                    configs[rel_path] = content
                    file_count += 1
            except Exception:
                pass

        if file_count >= MAX_TOTAL_FILES:
            break

    return configs


def get_app_configs(pm2_procs):
    app_configs = {}

    for proc in pm2_procs:
        app_name = proc.get("name")
        app_path = proc.get("path")

        if not app_name or not app_path or not os.path.exists(app_path):
            continue

        app_configs[app_name] = capture_app_tree(app_path)

    return app_configs

def get_config_files(services):
    configs = {}
    # Common paths for services
    possible_paths = {
        "nginx": ["/etc/nginx/nginx.conf", "/etc/nginx/conf.d/default.conf"],
        "apache2": ["/etc/apache2/apache2.conf", "/etc/apache2/ports.conf"],
        "httpd": ["/etc/httpd/conf/httpd.conf"],
        "mysql": ["/etc/mysql/my.cnf"],
        "postgresql": ["/etc/postgresql/12/main/postgresql.conf", "/etc/postgresql/13/main/postgresql.conf"],
        "tomcat": ["/opt/tomcat/conf/server.xml", "/usr/local/tomcat/conf/server.xml"]
    }
    
    for service in services:
        # Match service name loosely
        for key, paths in possible_paths.items():
            if key in service:
                for path in paths:
                    if os.path.exists(path):
                        try:
                            with open(path, 'r') as f:
                                # Limit size to avoid huge payloads
                                content = f.read(10000) 
                                configs[path] = content
                        except Exception as e:
                            print(f"Could not read {path}: {e}")
                            
    return configs


def get_systemd_app_services():
    services = []
    try:
        output = subprocess.check_output(
            "systemctl list-units --type=service --state=running --no-legend --no-pager",
            shell=True,
            stderr=subprocess.DEVNULL,
        ).decode()
    except Exception:
        return services

    infra_keywords = [
        "nginx",
        "apache2",
        "httpd",
        "postgres",
        "mysql",
        "mariadb",
        "docker",
        "containerd",
        "sshd",
        "systemd-",
        "cron",
        "rsyslog",
        "networkd",
        "dbus",
        "polkit",
        "logind",
    ]

    for line in output.splitlines():
        parts = line.split()
        if not parts:
            continue
        unit = parts[0]
        if not unit.endswith(".service"):
            continue
        lowered = unit.lower()
        if any(k in lowered for k in infra_keywords):
            continue
        services.append(unit)

    return services


def inspect_systemd_service(unit_name):
    details = {
        "service_name": unit_name,
    }

    try:
        output = subprocess.check_output(
            f"systemctl show {unit_name} -p ExecStart -p WorkingDirectory -p FragmentPath",
            shell=True,
            stderr=subprocess.DEVNULL,
        ).decode()
    except Exception:
        return None

    exec_start = None
    working_dir = None
    fragment_path = None

    for line in output.splitlines():
        if line.startswith("ExecStart=") and exec_start is None:
            exec_start = line.split("=", 1)[1].strip()
        elif line.startswith("WorkingDirectory="):
            value = line.split("=", 1)[1].strip()
            if value:
                working_dir = value
        elif line.startswith("FragmentPath="):
            value = line.split("=", 1)[1].strip()
            if value:
                fragment_path = value

    app_path = None

    if working_dir and os.path.isdir(working_dir):
        app_path = working_dir

    if app_path is None and exec_start:
        parts = exec_start.split()
        for part in parts[1:]:
            if part.startswith('"') and part.endswith('"'):
                part = part[1:-1]
            if os.path.isdir(part):
                app_path = part
                break
            if os.path.isfile(part):
                app_path = os.path.dirname(part)
                break

    unit_file_content = None
    if fragment_path and os.path.exists(fragment_path):
        try:
            with open(fragment_path, 'r') as f:
                unit_file_content = f.read()
        except Exception:
            unit_file_content = None

    files = {}
    if app_path and os.path.isdir(app_path):
        try:
            files = capture_app_tree(app_path)
        except Exception:
            files = {}

    name = unit_name
    if name.endswith(".service"):
        name = name[:-8]

    details["name"] = name
    details["exec_start"] = exec_start
    details["working_directory"] = working_dir
    details["unit_file_path"] = fragment_path
    details["unit_file_content"] = unit_file_content
    details["app_path"] = app_path
    details["files"] = files

    return details


def get_generic_apps():
    generic_apps = []
    services = get_systemd_app_services()

    for unit in services:
        details = inspect_systemd_service(unit)
        if details is None:
            continue
        generic_apps.append(details)

    return generic_apps


def scan():
    print("Gathering system information...")
    services = get_services()
    users = get_system_users()
    pm2_procs = get_pm2_processes()
    generic_apps = get_generic_apps()

    data = {
        "hostname": platform.node(),
        "os_info": get_os_info(),
        "cpu_cores": get_cpu_cores(),
        "memory_gb": get_memory_gb(),
        "disk_space_gb": get_disk_space(),
        "running_services": services,
        "open_ports": get_open_ports(),
        "installed_packages": get_installed_packages(),
        "system_users": users,
        "crontabs": get_crontabs(users),
        "config_files": get_config_files(services),
        "pm2_processes": pm2_procs,
        "custom_app_configs": get_app_configs(pm2_procs),
        "generic_apps": generic_apps,
    }
    return data

def send_data(data, url):
    print(f"Sending data to {url}...")
    req = urllib.request.Request(url)
    req.add_header('Content-Type', 'application/json')
    jsondata = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req, jsondata) as response:
            print("Success! Server response:", response.read().decode())
    except Exception as e:
        print(f"Error sending data: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default URL if not provided (assume running from curl default)
        # In a real scenario, the download command would inject the URL
        target_url = "http://localhost:8000/api/scan/submit"
    else:
        target_url = sys.argv[1]
    
    scan_data = scan()
    print("Scan Complete.")
    print(json.dumps(scan_data, indent=2))
    
    # Auto-send
    if target_url:
        send_data(scan_data, target_url)
