from pydantic import BaseModel
from typing import List, Optional, Dict

class SSHConnection(BaseModel):
    host: str
    username: str
    password: Optional[str] = None
    key_path: Optional[str] = None
    port: int = 22

class ScanResult(BaseModel):
    hostname: str
    os_info: str
    cpu_cores: int
    memory_gb: float
    disk_space_gb: Dict[str, float]
    running_services: List[str]
    open_ports: List[int]
    installed_packages: List[str]
    system_users: List[str] = [] # List of usernames (UID >= 1000)
    crontabs: Dict[str, str] = {} # User -> Crontab content
    config_files: Dict[str, str] = {}  # Path -> Content
    pm2_processes: List[Dict[str, str]] = [] # List of {name, path, status, version}
    custom_app_configs: Dict[str, Dict[str, str]] = {} # AppName -> {FileName -> Content}
    generic_apps: List[Dict] = []

class Component(BaseModel):
    name: str
    type: str # Service, Database, LoadBalancer, etc.

class AnalysisResult(BaseModel):
    scan_id: str
    recommended_gcp_instance: str
    estimated_cost_monthly: float
    migration_strategy: str  # e.g., "Rehost", "Replatform"
    risks: List[str]
    added_components: List[Component] = []
    architecture_diagram: Optional[str] = None # Mermaid.js graph definition
    removed_components: List[str] = []

class BuildConfig(BaseModel):
    project_id: str
    region: str
    zone: str
    instance_name: str
    machine_type: str
    source_image: str

class BuildResult(BaseModel):
    terraform_code_path: str
    status: str
    message: str

class DeployResult(BaseModel):
    status: str
    deployment_url: Optional[str]
    message: str
