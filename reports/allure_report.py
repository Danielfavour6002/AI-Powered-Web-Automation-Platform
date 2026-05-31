"""Allure report generation."""

from pathlib import Path
from core.models import Run, Result

def get_allure_results_dir(run_dir: Path) -> Path:
    """Returns the allure-results directory path."""
    return Path(run_dir) / "allure-results"

def generate_allure_index(run: Run, results: list[Result], allure_dir: Path) -> Path:
    """Generate a minimal standalone HTML index for allure."""
    allure_dir.mkdir(parents=True, exist_ok=True)
    index_path = allure_dir / "index.html"
    
    pass_rate = (run.passed_count / run.step_count * 100) if run.step_count else 0
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report: {run.test_name}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: #0a0b0e; color: #f1f0ed; margin: 0; padding: 40px; line-height: 1.6; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: #111318; padding: 30px; border-radius: 12px; border: 1px solid #2d3148; }}
        h1 {{ color: #0070f3; margin-top: 0; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }}
        .stat {{ background: #1a1d24; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #2d3148; }}
        .stat-value {{ font-size: 24px; font-weight: bold; }}
        .text-green {{ color: #22c55e; }}
        .text-red {{ color: #ef4444; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; font-size: 14px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #2d3148; }}
        th {{ color: #9a9892; text-transform: uppercase; font-size: 12px; }}
        tr:hover {{ background: #1f2330; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 11px; text-transform: uppercase; }}
        .bg-green {{ background: rgba(34,197,94,0.2); color: #22c55e; }}
        .bg-red {{ background: rgba(239,68,68,0.2); color: #ef4444; }}
        .bg-gray {{ background: #1f2330; color: #9a9892; }}
        .note {{ padding: 15px; background: rgba(59,130,246,0.1); border-left: 4px solid #3b82f6; color: #9a9892; font-size: 14px; }}
        a {{ color: #0070f3; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{run.test_name}</h1>
        
        <div class="summary">
            <div class="stat"><div class="stat-value text-{"green" if run.status.value=='passed' else "red"}">{run.status.value.upper()}</div><div>Status</div></div>
            <div class="stat"><div class="stat-value">{run.duration_seconds or 0:.1f}s</div><div>Duration</div></div>
            <div class="stat"><div class="stat-value">{pass_rate:.1f}%</div><div>Pass Rate</div></div>
            <div class="stat"><div class="stat-value">{run.step_count}</div><div>Steps</div></div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Action</th>
                    <th>Description</th>
                    <th>Status</th>
                    <th>Screenshot</th>
                </tr>
            </thead>
            <tbody>
"""
    for res in results:
        status_class = "bg-green" if res.status == 'passed' else "bg-red" if res.status == 'failed' else "bg-gray"
        ss_link = ""
        if res.screenshot_path:
            ss_name = Path(res.screenshot_path).name
            ss_link = f'<a href="../screenshots/{ss_name}" target="_blank">View</a>'
            
        html += f"""
                <tr>
                    <td>{res.sequence}</td>
                    <td><span class="badge bg-gray">{res.action.value}</span></td>
                    <td>{res.description or '-'}</td>
                    <td><span class="badge {status_class}">{res.status}</span></td>
                    <td>{ss_link}</td>
                </tr>
"""
    html += f"""
            </tbody>
        </table>
        
        <div class="note">
            <strong>Note:</strong> For the full interactive Allure report, install the Allure CLI and run:<br>
            <code>allure serve {allure_dir}</code>
        </div>
    </div>
</body>
</html>"""

    index_path.write_text(html, encoding="utf-8")
    return index_path

def get_allure_report_response(run: Run, results: list[Result], allure_dir: Path) -> Path:
    """Return index path, generate if not exists."""
    index_path = allure_dir / "index.html"
    if not index_path.exists():
        generate_allure_index(run, results, allure_dir)
    return index_path
