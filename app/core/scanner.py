import paramiko
from app.models import SSHConnection, ScanResult

def scan_server(conn: SSHConnection) -> ScanResult:
    # Mock behavior for demonstration if host is 'mock'
    if conn.host == 'mock':
        return ScanResult(
            hostname="legacy-app-server",
            os_info="Ubuntu 20.04 LTS",
            cpu_cores=4,
            memory_gb=16.0,
            disk_space_gb={"/": 100.0, "/var": 500.0},
            running_services=["nginx", "gunicorn", "postgresql"],
            open_ports=[80, 443, 5432, 22],
            installed_packages=["python3", "nginx", "postgresql-12"]
        )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        connect_kwargs = {
            "hostname": conn.host,
            "username": conn.username,
            "port": conn.port
        }
        if conn.password:
            connect_kwargs["password"] = conn.password
        if conn.key_path:
            connect_kwargs["key_filename"] = conn.key_path
            
        client.connect(**connect_kwargs)
        
        # Gather System Info
        # OS
        stdin, stdout, stderr = client.exec_command("cat /etc/os-release | grep PRETTY_NAME")
        os_info = stdout.read().decode().strip().split('=')[1].replace('"', '')
        
        # CPU
        stdin, stdout, stderr = client.exec_command("nproc")
        cpu_cores = int(stdout.read().decode().strip())
        
        # RAM
        stdin, stdout, stderr = client.exec_command("free -g | grep Mem | awk '{print $2}'")
        memory_gb = float(stdout.read().decode().strip())
        
        # Disk (Simplified: just root)
        stdin, stdout, stderr = client.exec_command("df -h / | awk 'NR==2 {print $2}'")
        disk_size_str = stdout.read().decode().strip()
        # Naive parsing, assuming G
        disk_space_gb = {"/": float(disk_size_str.replace('G', ''))} 

        # Services (Systemd)
        stdin, stdout, stderr = client.exec_command("systemctl list-units --type=service --state=running --no-pager | head -n 10")
        services_raw = stdout.read().decode().split('\n')
        running_services = [line.split()[0] for line in services_raw if line and '.service' in line]
        
        # Open Ports
        # This might fail if netstat/ss is not installed or requires sudo. 
        # Using a simple check or mocking if empty.
        stdin, stdout, stderr = client.exec_command("ss -tuln")
        ports_raw = stdout.read().decode().split('\n')
        open_ports = []
        for line in ports_raw:
            if 'LISTEN' in line:
                parts = line.split()
                # Address is usually 4th or 5th column depending on version
                for part in parts:
                    if ':' in part:
                        port_str = part.split(':')[-1]
                        if port_str.isdigit():
                            open_ports.append(int(port_str))
        open_ports = list(set(open_ports))

        # Hostname
        stdin, stdout, stderr = client.exec_command("hostname")
        hostname = stdout.read().decode().strip()
        
        client.close()
        
        return ScanResult(
            hostname=hostname,
            os_info=os_info,
            cpu_cores=cpu_cores,
            memory_gb=memory_gb,
            disk_space_gb=disk_space_gb,
            running_services=running_services,
            open_ports=open_ports,
            installed_packages=[], # Keeping empty for simplicity
            system_users=[],
            crontabs={},
            config_files={}
        )

    except Exception as e:
        # Fallback for demo if connection fails but we want to show something? 
        # No, better to raise error.
        raise Exception(f"Failed to scan server: {str(e)}")
