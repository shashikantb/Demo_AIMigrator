from fastapi import APIRouter, HTTPException
from app.models import SSHConnection, ScanResult, AnalysisResult, BuildConfig, BuildResult, DeployResult
from app.core import scanner, analyzer, builder, deployer

router = APIRouter()

@router.post("/scan", response_model=ScanResult)
async def scan_infrastructure(connection: SSHConnection):
    try:
        return scanner.scan_server(connection)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze", response_model=AnalysisResult)
async def analyze_infrastructure(scan_result: ScanResult):
    try:
        return analyzer.analyze_scan(scan_result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/build", response_model=BuildResult)
async def build_infrastructure(config: BuildConfig):
    try:
        return builder.generate_terraform(config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deploy", response_model=DeployResult)
async def deploy_application(target_ip: str):
    try:
        return deployer.deploy_app(target_ip)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
