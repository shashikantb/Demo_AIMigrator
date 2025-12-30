from app.models import ScanResult, AnalysisResult, Component
import uuid
import re


def sanitize_id(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]", "_", value)
    if not cleaned:
        cleaned = "node"
    if cleaned[0].isdigit():
        cleaned = "n_" + cleaned
    return cleaned


def generate_architecture_diagram(scan: ScanResult, analysis: AnalysisResult | None = None) -> str:
    graph = ["graph TD"]
    
    lb_layer = []
    app_layer = []
    db_layer = []
    removed = set(analysis.removed_components) if analysis and analysis.removed_components else set()
    
    for service in scan.running_services:
        if service in removed:
            continue
        s_lower = service.lower()
        if 'nginx' in s_lower or 'apache' in s_lower or 'httpd' in s_lower:
            lb_layer.append(f"LB[{service}]")
        elif 'postgre' in s_lower or 'mysql' in s_lower or 'mongo' in s_lower or 'redis' in s_lower:
            db_layer.append(f"DB[({service})]")
        elif 'ssh' not in s_lower: # Treat other services as app-level or utility
            node_id = f"APP_{sanitize_id(service)}"
            app_layer.append(f"{node_id}[{service}]")
            
    for proc in scan.pm2_processes:
        name = proc.get('name', 'node-app')
        if name in removed:
            continue
        node_id = f"NODE_{sanitize_id(name)}"
        app_layer.append(f"{node_id}[Node: {name}]")

    for app in scan.generic_apps:
        name = app.get("name") or app.get("service_name") or "app"
        if name in removed:
            continue
        node_id = f"GEN_{sanitize_id(name)}"
        app_layer.append(f"{node_id}[App: {name}]")

    if analysis and analysis.added_components:
        for comp in analysis.added_components:
            if comp.name in removed:
                continue
            node_id = f"ADDED_{sanitize_id(comp.name)}"
            label = f"{comp.name}"
            app_layer.append(f"{node_id}[{label}]")
        
    # Construct the graph
    # User -> LB -> App -> DB
    
    graph.append("User((User))")
    
    if lb_layer:
        for lb in lb_layer:
            graph.append(f"User --> {lb.split('[')[0]}")
            graph.append(lb)
            # Connect LB to Apps
            if app_layer:
                for app in app_layer:
                    graph.append(f"{lb.split('[')[0]} --> {app.split('[')[0]}")
    else:
        # No LB, connect User directly to Apps
        if app_layer:
            for app in app_layer:
                graph.append(f"User --> {app.split('[')[0]}")
                
    if app_layer:
        for app in app_layer:
            graph.append(app)
            # Connect Apps to DBs
            if db_layer:
                for db in db_layer:
                    graph.append(f"{app.split('[')[0]} --> {db.split('[')[0]}")
    
    if db_layer:
        for db in db_layer:
            graph.append(db)
            
    # Fallback if no connections made but components exist (e.g. just DB)
    if not app_layer and not lb_layer and db_layer:
         for db in db_layer:
            graph.append(f"User -.-> {db.split('[')[0]}")

    return "\n".join(graph)

def analyze_scan(scan: ScanResult) -> AnalysisResult:
    # 1. Resource Mapping
    # Simple logic: Match CPU/RAM to nearest standard machine type
    machine_type = "e2-medium" # Default
    if scan.cpu_cores >= 4 and scan.memory_gb >= 16:
        machine_type = "e2-standard-4"
    elif scan.cpu_cores >= 2:
        machine_type = "e2-standard-2"
    
    # 2. Strategy Determination
    strategy = "Rehost"
    risks = []
    
    # Check for databases to suggest Replatform
    db_services = ["postgresql", "mysql", "oracle", "mongod"]
    found_dbs = [s for s in scan.running_services if any(db in s for db in db_services)]
    
    if found_dbs:
        strategy = "Replatform"
        risks.append(f"Database migration required for: {', '.join(found_dbs)}")
    
    # Check for older OS
    if "14.04" in scan.os_info or "16.04" in scan.os_info:
        risks.append("Legacy OS detected. Consider upgrading or containerizing (Refactor).")

    # 3. Cost Estimation (Mocked)
    # e2-standard-4 is roughly $100/mo, e2-medium is $25/mo
    cost = 25.0
    if machine_type == "e2-standard-4":
        cost = 100.0
    elif machine_type == "e2-standard-2":
        cost = 50.0

    diagram = generate_architecture_diagram(scan, None)

    return AnalysisResult(
        scan_id=str(uuid.uuid4()),
        recommended_gcp_instance=machine_type,
        estimated_cost_monthly=cost,
        migration_strategy=strategy,
        risks=risks,
        architecture_diagram=diagram
    )
