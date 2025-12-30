from app.models import BuildConfig, BuildResult, ScanResult, AnalysisResult
from jinja2 import Environment, FileSystemLoader
import os
import subprocess
import base64

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '../../templates/gcp')
GENERATED_DIR = os.path.join(os.path.dirname(__file__), '../../generated')

def generate_terraform(config: BuildConfig, scan_result: ScanResult = None, analysis_result: AnalysisResult = None) -> BuildResult:
    # Ensure generated directory exists
    if not os.path.exists(GENERATED_DIR):
        os.makedirs(GENERATED_DIR)
        
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template('main.tf.j2')
    
    # Generate startup script if we have config files
    startup_script = "#!/bin/bash\n"
    startup_script += "echo 'Starting system migration restoration...'\n\n"
    
    if scan_result:
        # 0. Install Manually Added Components
        if analysis_result and analysis_result.added_components:
            startup_script += "# Install Manually Added Components\n"
            startup_script += "apt-get update\n"
            for comp in analysis_result.added_components:
                # Basic assumption: Component name matches package name
                startup_script += f"apt-get install -y {comp.name.lower()} || echo 'Could not install {comp.name}'\n"
            startup_script += "\n"

        # 1. Install Packages (Debian/Ubuntu assumption for demo)
        if scan_result.installed_packages:
            packages = " ".join(scan_result.installed_packages[:50]) # Limit to top 50 to avoid huge command
            startup_script += "# Restore Packages (Partial)\n"
            startup_script += "apt-get update\n"
            startup_script += f"apt-get install -y {packages} || true\n\n"
            
        # 2. Setup Node.js & PM2 (if PM2 processes detected)
        if scan_result.pm2_processes:
            startup_script += "# Install Node.js & PM2\n"
            startup_script += "curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -\n"
            startup_script += "apt-get install -y nodejs\n"
            startup_script += "npm install -g pm2\n\n"
            
        # 3. Create Users
        if scan_result.system_users:
            startup_script += "# Restore Users\n"
            for user in scan_result.system_users:
                if user != 'root':
                    startup_script += f"id -u {user} &>/dev/null || useradd -m {user}\n"
            startup_script += "\n"

        # 5. Restore Config Files
        if scan_result.config_files:
            startup_script += "# Restore Configuration Files\n"
            for path, content in scan_result.config_files.items():
                # Encode content to avoid escaping issues
                b64_content = base64.b64encode(content.encode()).decode()
                startup_script += f"mkdir -p $(dirname {path})\n"
                startup_script += f"echo '{b64_content}' | base64 -d > {path}\n"
            startup_script += "\n"

        # 6. Restore PM2 Apps Configs
        if scan_result.pm2_processes and scan_result.custom_app_configs:
            startup_script += "# Restore PM2 Applications Configs\n"
            for app_name, configs in scan_result.custom_app_configs.items():
                # Find path for this app from pm2_processes
                app_path = next((p['path'] for p in scan_result.pm2_processes if p['name'] == app_name), f"/opt/{app_name}")
                
                startup_script += f"mkdir -p {app_path}\n"
                
                for filename, content in configs.items():
                    # filename is now a relative path (e.g., "src/config/db.js")
                    # We need to ensure the directory exists
                    full_target_path = os.path.join(app_path, filename)
                    dir_name = os.path.dirname(full_target_path)
                    
                    b64_content = base64.b64encode(content.encode()).decode()
                    
                    startup_script += f"mkdir -p {dir_name}\n"
                    startup_script += f"echo '{b64_content}' | base64 -d > {full_target_path}\n"
                
                # Try to install dependencies if package.json exists
                # Check keys for exact match or simple match
                has_package_json = any(k.endswith('package.json') for k in configs.keys())
                has_ecosystem = any(k.endswith('ecosystem.config.js') for k in configs.keys())
                
                if has_package_json:
                     startup_script += f"cd {app_path} && npm install || echo 'npm install failed'\n"
                
                # Try to restart app
                if has_ecosystem:
                    startup_script += f"cd {app_path} && pm2 start ecosystem.config.js || echo 'pm2 start failed'\n"
                elif has_package_json:
                     startup_script += f"cd {app_path} && npm start & \n"
            
            startup_script += "pm2 save\n\n"

        if scan_result.generic_apps:
            for app in scan_result.generic_apps:
                name = app.get("name") or app.get("service_name")
                app_path = app.get("app_path") or (f"/opt/{name}" if name else None)
                files = app.get("files") or {}
                unit_file_path = app.get("unit_file_path")
                unit_file_content = app.get("unit_file_content")

                if app_path and files:
                    for filename, content in files.items():
                        full_target_path = os.path.join(app_path, filename)
                        dir_name = os.path.dirname(full_target_path)
                        b64_content = base64.b64encode(content.encode()).decode()
                        startup_script += f"mkdir -p {dir_name}\n"
                        startup_script += f"echo '{b64_content}' | base64 -d > {full_target_path}\n"

                if unit_file_path and unit_file_content:
                    b64_unit = base64.b64encode(unit_file_content.encode()).decode()
                    unit_dir = os.path.dirname(unit_file_path)
                    startup_script += f"mkdir -p {unit_dir}\n"
                    startup_script += f"echo '{b64_unit}' | base64 -d > {unit_file_path}\n"
                    service_name = app.get("service_name") or (f"{name}.service" if name else None)
                    if service_name:
                        startup_script += "systemctl daemon-reload\n"
                        startup_script += f"systemctl enable {service_name} || true\n"
                        startup_script += f"systemctl restart {service_name} || true\n"

        if scan_result.crontabs:
            startup_script += "# Restore Crontabs\n"
            for user, cron_content in scan_result.crontabs.items():
                b64_cron = base64.b64encode(cron_content.encode()).decode()
                startup_script += f"echo '{b64_cron}' | base64 -d | crontab -u {user} -\n"
            startup_script += "\n"
            
    # Save startup script
    startup_path = os.path.join(GENERATED_DIR, 'startup.sh')
    with open(startup_path, 'w') as f:
        f.write(startup_script)
    
    # Map config to template variables
    terraform_content = template.render(
        project_id=config.project_id,
        region=config.region,
        zone=config.zone,
        instance_name=config.instance_name,
        machine_type=config.machine_type,
        source_image=config.source_image,
        startup_script_path="./startup.sh"
    )
    
    file_path = os.path.join(GENERATED_DIR, 'main.tf')
    with open(file_path, 'w') as f:
        f.write(terraform_content)
        
    return BuildResult(
        terraform_code_path=file_path,
        status="Success",
        message="Terraform configuration generated successfully. Configuration files restoration script included."
    )
