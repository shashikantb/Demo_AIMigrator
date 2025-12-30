# Migration Automater

An intelligent platform to streamline application migration from On-Premise to Google Cloud Platform (GCP).

## Features
- **Scan**: Discover and inventory application components via SSH.
- **Analyze**: Assess cloud readiness, map resources, and estimate costs.
- **Build**: Automatically generate Terraform code for GCP infrastructure.
- **Deploy**: Simulate application deployment to the new infrastructure.

## Project Structure
- `app/`: Main application logic (FastAPI + Core Modules).
- `migrator_cli.py`: Interactive Command Line Interface.
- `templates/`: Jinja2 templates for Infrastructure as Code (Terraform).
- `generated/`: Output directory for generated Terraform files.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### CLI Mode (Recommended)
Run the interactive CLI:
```bash
python3 migrator_cli.py
```
Follow the prompts to Scan -> Analyze -> Build -> Deploy.
You can use "mock" mode to test the flow without a real server.

### API Mode
Start the API server:
```bash
# Using the helper script
./start_api.sh

# OR directly with python module
python3 -m uvicorn app.main:app --reload
```
Access the API docs at `http://localhost:8000/docs`.

## Requirements
- Python 3.8+
- Terraform (for actual provisioning)
- GCP Credentials (if running real infrastructure builds)
