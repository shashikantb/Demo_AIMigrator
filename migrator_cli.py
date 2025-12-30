import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
import json
from app.models import SSHConnection, ScanResult, BuildConfig
from app.core import scanner, analyzer, builder, deployer

app = typer.Typer()
console = Console()

@app.command()
def migrate():
    console.print("[bold blue]Migration Automater CLI[/bold blue]")
    console.print("======================================")
    
    # Phase 1: Scan
    console.print("\n[bold green]Phase 1: Scan (Discovery & Inventory)[/bold green]")
    mode = Prompt.ask("Select Mode", choices=["mock", "real"], default="mock")
    
    if mode == "real":
        host = Prompt.ask("Enter Host IP")
        username = Prompt.ask("Enter Username")
        password = Prompt.ask("Enter Password", password=True)
        conn = SSHConnection(host=host, username=username, password=password)
    else:
        conn = SSHConnection(host="mock", username="test")
        
    with console.status("Scanning infrastructure..."):
        try:
            scan_result = scanner.scan_server(conn)
        except Exception as e:
            console.print(f"[bold red]Scan Failed:[/bold red] {e}")
            return

    # Display Scan Results
    table = Table(title="Scan Results")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Hostname", scan_result.hostname)
    table.add_row("OS", scan_result.os_info)
    table.add_row("CPU Cores", str(scan_result.cpu_cores))
    table.add_row("Memory (GB)", str(scan_result.memory_gb))
    table.add_row("Services", ", ".join(scan_result.running_services))
    console.print(table)
    
    if not Confirm.ask("Proceed to Analysis?"):
        return

    # Phase 2: Analyze
    console.print("\n[bold green]Phase 2: Analyze (Assessment & Recommendation)[/bold green]")
    with console.status("Analyzing..."):
        analysis = analyzer.analyze_scan(scan_result)
        
    console.print(f"[bold]Recommended Strategy:[/bold] {analysis.migration_strategy}")
    console.print(f"[bold]Recommended Instance:[/bold] {analysis.recommended_gcp_instance}")
    console.print(f"[bold]Estimated Cost:[/bold] ${analysis.estimated_cost_monthly}/month")
    
    if analysis.risks:
        console.print("[bold yellow]Risks Identified:[/bold yellow]")
        for risk in analysis.risks:
            console.print(f"- {risk}")

    if not Confirm.ask("Proceed to Build?"):
        return

    # Phase 3: Build
    console.print("\n[bold green]Phase 3: Build (Infrastructure Provisioning)[/bold green]")
    project_id = Prompt.ask("Enter GCP Project ID", default="my-migration-project")
    
    config = BuildConfig(
        project_id=project_id,
        region="us-central1",
        zone="us-central1-a",
        instance_name=f"migrated-{scan_result.hostname}",
        machine_type=analysis.recommended_gcp_instance,
        source_image="debian-cloud/debian-11" # Defaulting for demo
    )
    
    with console.status("Generating Infrastructure Code..."):
        build_result = builder.generate_terraform(config)
        
    console.print(f"[bold]Terraform Code:[/bold] {build_result.terraform_code_path}")
    console.print(build_result.message)
    
    if not Confirm.ask("Proceed to Deploy?"):
        return

    # Phase 4: Deploy
    console.print("\n[bold green]Phase 4: Deploy (Application Deployment)[/bold green]")
    target_ip = "34.12.13.14" # Mock IP
    
    with console.status(f"Deploying to {target_ip}..."):
        deploy_result = deployer.deploy_app(target_ip)
        
    console.print(f"[bold]Status:[/bold] {deploy_result.status}")
    console.print(f"[bold]Message:[/bold] {deploy_result.message}")
    console.print(f"[bold]App URL:[/bold] {deploy_result.deployment_url}")
    
    console.print("\n[bold blue]Migration Completed Successfully![/bold blue]")

if __name__ == "__main__":
    app()
