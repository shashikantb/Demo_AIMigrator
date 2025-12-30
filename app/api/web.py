from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os
from app.core import scanner, analyzer, builder, deployer
from app.models import ScanResult, BuildConfig, Component

router = APIRouter()
templates = Jinja2Templates(directory="templates/web")

PROJECTS = {}


def get_project_name(request: Request) -> str:
    project = request.query_params.get("project")
    if not project:
        project = "default"
    return project


def get_project_state(project: str):
    if project not in PROJECTS:
        PROJECTS[project] = {
            "scan": None,
            "analysis": None,
            "build": None,
        }
    return PROJECTS[project]


@router.post("/api/analyze/add_component")
async def add_component(comp: Component, request: Request):
    project = get_project_name(request)
    state = get_project_state(project)
    analysis = state.get("analysis")
    scan = state.get("scan")
    if not analysis:
        return {"status": "error", "message": "No active analysis found"}
    if not analysis.added_components:
        analysis.added_components = []
    analysis.added_components.append(comp)
    if scan:
        analysis.architecture_diagram = analyzer.generate_architecture_diagram(
            scan, analysis
        )
    state["analysis"] = analysis
    return {"status": "added", "component": comp}


@router.post("/api/analyze/remove_component")
async def remove_component(comp: Component, request: Request):
    project = get_project_name(request)
    state = get_project_state(project)
    analysis = state.get("analysis")
    scan = state.get("scan")
    if not analysis:
        return {"status": "error", "message": "No active analysis found"}
    if analysis.added_components:
        analysis.added_components = [
            c for c in analysis.added_components
            if not (c.name == comp.name and c.type == comp.type)
        ]
    if not analysis.removed_components:
        analysis.removed_components = []
    if comp.name not in analysis.removed_components:
        analysis.removed_components.append(comp.name)
    if scan:
        analysis.architecture_diagram = analyzer.generate_architecture_diagram(
            scan, analysis
        )
    state["analysis"] = analysis
    return {"status": "removed", "component": comp}

@router.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/guide/scan", response_class=HTMLResponse)
async def guide_scan(request: Request):
    project = get_project_name(request)
    state = get_project_state(project)
    host_url = str(request.base_url).rstrip('/')
    return templates.TemplateResponse("scan.html", {
        "request": request,
        "host_url": host_url,
        "scan_result": state.get("scan"),
        "project": project
    })


@router.get("/guide/analyze", response_class=HTMLResponse)
async def guide_analyze(request: Request):
    project = get_project_name(request)
    state = get_project_state(project)
    scan = state.get("scan")
    analysis = state.get("analysis")
    if scan and not analysis:
        analysis = analyzer.analyze_scan(scan)
        state["analysis"] = analysis

    return templates.TemplateResponse("analyze.html", {
        "request": request,
        "scan": scan,
        "analysis": analysis,
        "project": project
    })


@router.get("/guide/build", response_class=HTMLResponse)
async def guide_build(request: Request):
    project = get_project_name(request)
    state = get_project_state(project)
    scan = state.get("scan")
    analysis = state.get("analysis")
    build = state.get("build")

    if analysis and not build:
        config = BuildConfig(
            project_id=project,
            region="us-central1",
            zone="us-central1-a",
            instance_name=f"migrated-{scan.hostname}" if scan else f"migrated-{project}",
            machine_type=analysis.recommended_gcp_instance,
            source_image="debian-cloud/debian-11"
        )
        build = builder.generate_terraform(config, scan_result=scan, analysis_result=analysis)
        state["build"] = build

    startup_content = ""
    if build:
        startup_path = os.path.join(os.path.dirname(build.terraform_code_path), 'startup.sh')
        if os.path.exists(startup_path):
            with open(startup_path, 'r') as f:
                startup_content = f.read()

    return templates.TemplateResponse("build.html", {
        "request": request,
        "build": build,
        "scan": scan,
        "startup_script_content": startup_content,
        "project": project
    })


@router.post("/api/build/trigger")
async def trigger_build(config: BuildConfig, request: Request):
    project = get_project_name(request)
    state = get_project_state(project)
    scan = state.get("scan")
    build = builder.generate_terraform(config, scan_result=scan)
    state["build"] = build
    return build


@router.get("/guide/deploy", response_class=HTMLResponse)
async def guide_deploy(request: Request):
    project = get_project_name(request)
    return templates.TemplateResponse("deploy.html", {"request": request, "project": project})


@router.post("/api/scan/submit")
async def submit_scan(scan_data: ScanResult, request: Request):
    project = get_project_name(request)
    state = get_project_state(project)
    state["scan"] = scan_data
    state["analysis"] = None
    state["build"] = None
    return {"status": "received", "hostname": scan_data.hostname, "project": project}


@router.get("/api/scan/status")
async def check_scan_status(request: Request):
    project = get_project_name(request)
    state = get_project_state(project)
    scan = state.get("scan")
    if scan:
        return {"ready": True, "hostname": scan.hostname, "project": project}
    return {"ready": False, "project": project}
