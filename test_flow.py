from app.models import SSHConnection, BuildConfig
from app.core import scanner, analyzer, builder, deployer
import os

def test_migration_flow():
    print("=== Starting Migration Flow Test ===")
    
    # 1. Scan
    print("\n[1] Scanning...")
    conn = SSHConnection(host="mock", username="test")
    scan_result = scanner.scan_server(conn)
    print(f"Scan Result: {scan_result.hostname} ({scan_result.os_info})")
    
    # 2. Analyze
    print("\n[2] Analyzing...")
    analysis = analyzer.analyze_scan(scan_result)
    print(f"Strategy: {analysis.migration_strategy}")
    print(f"Instance: {analysis.recommended_gcp_instance}")
    
    # 3. Build
    print("\n[3] Building...")
    config = BuildConfig(
        project_id="test-project",
        region="us-central1",
        zone="us-central1-a",
        instance_name=f"migrated-{scan_result.hostname}",
        machine_type=analysis.recommended_gcp_instance,
        source_image="debian-cloud/debian-11"
    )
    build_result = builder.generate_terraform(config)
    print(f"Terraform Path: {build_result.terraform_code_path}")
    
    # Verify file exists
    if os.path.exists(build_result.terraform_code_path):
        print("Terraform file successfully generated.")
        with open(build_result.terraform_code_path, 'r') as f:
            print("--- Content Preview ---")
            print(f.read()[:200] + "...")
            print("-----------------------")
    
    # 4. Deploy
    print("\n[4] Deploying...")
    deploy_result = deployer.deploy_app("1.2.3.4")
    print(f"Status: {deploy_result.status}")
    print(f"Message: {deploy_result.message}")
    
    print("\n=== Test Completed Successfully ===")

if __name__ == "__main__":
    test_migration_flow()
