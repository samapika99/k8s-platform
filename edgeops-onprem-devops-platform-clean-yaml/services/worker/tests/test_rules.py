from app.worker import evaluate

def test_cpu_warning():
    severity, reason = evaluate({
        "cpu": 95, "memory": 30, "disk": 40
    })
    assert severity == "warning"

def test_disk_critical():
    severity, reason = evaluate({
        "cpu": 20, "memory": 30, "disk": 95
    })
    assert severity == "critical"
