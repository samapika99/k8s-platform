import React, { useEffect, useState, useCallback } from "react"
import { createRoot } from "react-dom/client"
import "./style.css"

const emptySummary = {
  clusters: 0,
  devices: 0,
  active_incidents: 0,
  critical_incidents: 0,
}

function App() {
  const [summary, setSummary] = useState(emptySummary)
  const [clusters, setClusters] = useState([])
  const [incidents, setIncidents] = useState([])
  const [nodes, setNodes] = useState([])
  const [deployments, setDeployments] = useState([])
  const [auditLogs, setAuditLogs] = useState([])
  const [page, setPage] = useState("Overview")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [lastUpdated, setLastUpdated] = useState(null)

  async function apiGet(url) {
    const response = await fetch(url, { cache: "no-store" })
    if (!response.ok) {
      throw new Error(`${url} returned HTTP ${response.status}`)
    }
    return response.json()
  }

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError("")

      const [summaryData, clustersData, incidentsData, nodesData, deploymentsData, auditData] =
        await Promise.all([
          apiGet("/api/summary"),
          apiGet("/api/clusters"),
          apiGet("/api/incidents"),
          apiGet("/api/nodes"),
          apiGet("/api/deployments"),
          apiGet("/api/audit?limit=50"),
        ])

      setSummary(summaryData)
      setClusters(clustersData)
      setIncidents(incidentsData)
      setNodes(nodesData)
      setDeployments(deploymentsData)
      setAuditLogs(auditData.items || [])
      setLastUpdated(new Date())
    } catch (err) {
      console.error("EdgeOps API error:", err)
      setError(`Unable to load API data: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, 10000)
    return () => clearInterval(timer)
  }, [load])

  const navigation = [
    "Overview",
    "Clusters",
    "Applications",
    "Deployments",
    "Incidents",
    "Telemetry",
    "Audit Log",
    "Settings",
  ]

  return (
    <div className="shell">
      <aside>
        <div className="logo">◈ EdgeOps</div>
        <div className="subtitle">Control Plane</div>
        <nav>
          {navigation.map((item) => (
            <button
              key={item}
              id={`nav-${item.toLowerCase().replace(/\s+/g, "-")}`}
              className={page === item ? "nav-button active" : "nav-button"}
              onClick={() => setPage(item)}
            >
              {item}
            </button>
          ))}
        </nav>
        <div className="sidebottom">
          <span className="pulse"></span>
          Platform Online
        </div>
      </aside>

      <main>
        <header>
          <div>
            <div className="eyebrow">OPERATIONS / SINGLE NODE</div>
            <h1>{page}</h1>
            <p>EdgeOps on-prem Kubernetes operations platform.</p>
          </div>

          <div className="header-right">
            {lastUpdated && (
              <span className="last-updated">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <button
              id="btn-refresh"
              className="refresh"
              onClick={load}
              disabled={loading}
            >
              {loading ? "Loading…" : "Refresh"}
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            <strong>API Error:</strong> {error}
          </div>
        )}

        {page === "Overview" && (
          <Overview
            summary={summary}
            clusters={clusters}
            incidents={incidents}
          />
        )}

        {page === "Clusters" && (
          <ClustersPage clusters={clusters} nodes={nodes} />
        )}

        {page === "Applications" && (
          <ApplicationsPage nodes={nodes} />
        )}

        {page === "Deployments" && (
          <DeploymentsPage deployments={deployments} />
        )}

        {page === "Incidents" && (
          <IncidentsPage incidents={incidents} />
        )}

        {page === "Telemetry" && (
          <TelemetryPage clusters={clusters} />
        )}

        {page === "Audit Log" && (
          <AuditLogPage logs={auditLogs} />
        )}

        {page === "Settings" && (
          <SettingsPage clusters={clusters} />
        )}

        <footer>EdgeOps · On-Prem Kubernetes Operations Platform</footer>
      </main>
    </div>
  )
}


// ============================================================
// Overview
// ============================================================

function Overview({ summary, clusters, incidents }) {
  return (
    <>
      <section className="stats">
        <Card title="Clusters" value={summary.clusters} note="Registered environments" />
        <Card title="Devices" value={summary.devices} note="Managed Kubernetes nodes" />
        <Card
          title="Active Incidents"
          value={summary.active_incidents}
          note="Needs attention"
          danger={summary.active_incidents > 0}
        />
        <Card
          title="Critical"
          value={summary.critical_incidents}
          note="Immediate action"
          danger={summary.critical_incidents > 0}
        />
      </section>

      <section className="grid">
        <div className="panel">
          <div className="paneltitle">
            <h2>Clusters</h2>
            <span>{clusters.length} total</span>
          </div>

          {clusters.length === 0 ? (
            <Empty text="No clusters registered." />
          ) : (
            clusters.map((cluster) => (
              <div className="cluster" key={cluster.id || cluster.name}>
                <div
                  className={cluster.status === "healthy" ? "health good" : "health warn"}
                ></div>

                <div className="clustername">
                  <b>{cluster.name}</b>
                  <small>
                    {cluster.location} · {cluster.environment}
                  </small>
                </div>

                <div className="usage">
                  <small>CPU</small>
                  {cluster.metrics_available === false ? (
                    <span className="metrics-na">—</span>
                  ) : (
                    `${cluster.cpu ?? 0}%`
                  )}
                </div>

                <div className="usage">
                  <small>MEM</small>
                  {cluster.metrics_available === false ? (
                    <span className="metrics-na">—</span>
                  ) : (
                    `${cluster.memory ?? 0}%`
                  )}
                </div>

                <div className="usage">
                  <small>DISK</small>
                  {`${cluster.disk ?? 0}%`}
                </div>

                <span
                  className={cluster.status === "healthy" ? "pill green" : "pill yellow"}
                >
                  {cluster.status || "unknown"}
                </span>
              </div>
            ))
          )}
        </div>

        <div className="panel">
          <div className="paneltitle">
            <h2>Active Incidents</h2>
            <span>{incidents.length}</span>
          </div>

          {incidents.length === 0 ? (
            <Empty text="No incidents. Platform is healthy." />
          ) : (
            incidents.slice(0, 8).map((incident) => (
              <div className="incident" key={incident.id}>
                <span className={`severity ${incident.severity}`}>
                  {incident.severity}
                </span>
                <div>
                  <b>{incident.reason}</b>
                  <small>{incident.cluster}</small>
                </div>
                <span className="incstatus">{incident.status}</span>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="panel architecture">
        <div className="paneltitle">
          <h2>Platform Components</h2>
          <span>Runtime view</span>
        </div>

        <div className="components">
          {[
            "FastAPI",
            "React",
            "MongoDB",
            "Redis",
            "Kafka",
            "Telemetry Worker",
            "Kubernetes Agent",
            "Prometheus",
            "Grafana",
            "Argo CD",
          ].map((component) => (
            <div className="component" key={component}>
              <span className="componentdot"></span>
              {component}
            </div>
          ))}
        </div>
      </section>
    </>
  )
}


// ============================================================
// Clusters Page
// ============================================================

function ClustersPage({ clusters, nodes }) {
  return (
    <>
      <section className="panel">
        <div className="paneltitle">
          <h2>Kubernetes Clusters</h2>
          <span>{clusters.length} clusters</span>
        </div>

        {clusters.length === 0 ? (
          <Empty text="No clusters registered." />
        ) : (
          clusters.map((cluster) => (
            <div className="detail-row cluster-detail" key={cluster.id || cluster.name}>
              <div>
                <b>{cluster.name}</b>
                <small>{cluster.location}</small>
              </div>

              <span>
                K8s: {cluster.kubernetes_version || "unknown"}
              </span>

              <span>
                Nodes: {cluster.node_count ?? "—"} / {cluster.ready_nodes ?? "—"} ready
              </span>

              <span>
                Pods: {cluster.pods ?? "—"}
              </span>

              <span>
                Deployments: {cluster.deployment_count ?? "—"}
              </span>

              <span
                className={cluster.status === "healthy" ? "pill green" : "pill yellow"}
              >
                {cluster.status || "unknown"}
              </span>
            </div>
          ))
        )}
      </section>

      <section className="panel">
        <div className="paneltitle">
          <h2>Kubernetes Nodes</h2>
          <span>{nodes.length} nodes</span>
        </div>

        {nodes.length === 0 ? (
          <Empty text="No nodes discovered yet." />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Cluster</th>
                  <th>Internal IP</th>
                  <th>OS</th>
                  <th>Architecture</th>
                  <th>K8s Version</th>
                  <th>Roles</th>
                  <th>CPU</th>
                  <th>Memory</th>
                  <th>Pods</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {nodes.map((node) => (
                  <tr key={node.id || `${node.cluster}-${node.name}`}>
                    <td><b>{node.name}</b></td>
                    <td>{node.cluster}</td>
                    <td className="mono">{node.internal_ip || "—"}</td>
                    <td>{node.os_image || node.operating_system || "—"}</td>
                    <td>{node.architecture || "—"}</td>
                    <td className="mono">{node.kubernetes_version || "—"}</td>
                    <td>
                      {(node.roles || []).length > 0
                        ? node.roles.map((r) => (
                            <span key={r} className="role-tag">{r}</span>
                          ))
                        : <span className="role-tag">worker</span>}
                    </td>
                    <td>{node.cpu_capacity || "—"}</td>
                    <td>{node.memory_capacity || "—"}</td>
                    <td>{node.pod_count ?? "—"}</td>
                    <td>
                      <span
                        className={
                          node.status === "ready"
                            ? "pill green"
                            : node.status === "not-ready"
                            ? "pill red"
                            : "pill yellow"
                        }
                      >
                        {node.status || "unknown"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}


// ============================================================
// Applications Page
// ============================================================

function ApplicationsPage({ nodes }) {
  // Show node-level workload summary as application proxy
  const totalPods = nodes.reduce((acc, n) => acc + (n.pod_count || 0), 0)

  return (
    <section className="panel">
      <div className="paneltitle">
        <h2>Applications</h2>
        <span>Node workload summary</span>
      </div>

      {nodes.length === 0 ? (
        <Empty text="No nodes discovered. Applications will appear once nodes are registered." />
      ) : (
        <>
          <div className="detail-row" style={{ fontWeight: 600, opacity: 0.6, fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            <div>Node</div>
            <span>Cluster</span>
            <span>Running Pods</span>
            <span>Pod Capacity</span>
            <span>Status</span>
          </div>
          {nodes.map((node) => (
            <div className="detail-row" key={node.id || node.name}>
              <div>
                <b>{node.name}</b>
                <small>{node.internal_ip}</small>
              </div>
              <span>{node.cluster}</span>
              <span>{node.pod_count ?? "—"}</span>
              <span>{node.pod_capacity || "—"}</span>
              <span className={node.status === "ready" ? "pill green" : "pill yellow"}>
                {node.status || "unknown"}
              </span>
            </div>
          ))}
          <div className="apps-summary">
            <strong>Total pods across all nodes: {totalPods}</strong>
          </div>
        </>
      )}
    </section>
  )
}


// ============================================================
// Deployments Page
// ============================================================

function DeploymentsPage({ deployments }) {
  return (
    <section className="panel">
      <div className="paneltitle">
        <h2>Deployments</h2>
        <span>{deployments.length} clusters</span>
      </div>

      {deployments.length === 0 ? (
        <Empty text="No deployment data yet. The agent collects this every 30 seconds." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Cluster</th>
                <th>Environment</th>
                <th>K8s Version</th>
                <th>Deployments</th>
                <th>Pods</th>
                <th>PVCs</th>
                <th>Nodes</th>
                <th>Last Seen</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {deployments.map((dep) => (
                <tr key={dep.id || dep.name}>
                  <td><b>{dep.name}</b></td>
                  <td>{dep.environment || "—"}</td>
                  <td className="mono">{dep.kubernetes_version || "—"}</td>
                  <td>{dep.deployment_count ?? "—"}</td>
                  <td>{dep.pods ?? "—"}</td>
                  <td>{dep.pvc_count ?? "—"}</td>
                  <td>{dep.node_count ?? "—"}</td>
                  <td>
                    {dep.last_seen
                      ? new Date(dep.last_seen).toLocaleString()
                      : "—"}
                  </td>
                  <td>
                    <span
                      className={dep.status === "healthy" ? "pill green" : "pill yellow"}
                    >
                      {dep.status || "unknown"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}


// ============================================================
// Incidents Page
// ============================================================

function IncidentsPage({ incidents }) {
  return (
    <section className="panel">
      <div className="paneltitle">
        <h2>Incidents</h2>
        <span>{incidents.length}</span>
      </div>

      {incidents.length === 0 ? (
        <Empty text="No incidents." />
      ) : (
        incidents.map((incident) => (
          <div className="incident" key={incident.id}>
            <span className={`severity ${incident.severity}`}>
              {incident.severity}
            </span>
            <div>
              <b>{incident.reason}</b>
              <small>{incident.cluster}</small>
            </div>
            <span className="incstatus">{incident.status}</span>
            <small className="mono">
              {incident.created_at
                ? new Date(incident.created_at).toLocaleString()
                : ""}
            </small>
          </div>
        ))
      )}
    </section>
  )
}


// ============================================================
// Telemetry Page
// ============================================================

function TelemetryPage({ clusters }) {
  return (
    <section className="panel">
      <div className="paneltitle">
        <h2>Cluster Telemetry</h2>
        <span>Live data</span>
      </div>

      {clusters.length === 0 ? (
        <Empty text="No telemetry data yet." />
      ) : (
        clusters.map((cluster) => (
          <div className="telemetry-card" key={cluster.id || cluster.name}>
            <div className="telemetry-header">
              <h3>{cluster.name}</h3>
              {cluster.metrics_available === false && (
                <span className="badge-warn">
                  ⚠ Metrics Server unavailable — showing reserved capacity
                </span>
              )}
              <span className={cluster.status === "healthy" ? "pill green" : "pill yellow"}>
                {cluster.status}
              </span>
            </div>

            <div className="telemetry-grid">
              <Metric title="Nodes" value={cluster.node_count ?? "—"} />
              <Metric title="Ready Nodes" value={cluster.ready_nodes ?? "—"} />
              <Metric title="Pods" value={cluster.pods ?? "—"} />
              <Metric title="Deployments" value={cluster.deployment_count ?? "—"} />
              <Metric title="PVCs" value={cluster.pvc_count ?? "—"} />
              <Metric
                title={cluster.metrics_available === false ? "CPU (reserved)" : "CPU"}
                value={`${cluster.cpu ?? 0}%`}
              />
              <Metric
                title={cluster.metrics_available === false ? "Memory (reserved)" : "Memory"}
                value={`${cluster.memory ?? 0}%`}
              />
              <Metric title="Disk" value={`${cluster.disk ?? 0}%`} />
            </div>

            <div className="telemetry-meta">
              <small>
                Last seen:{" "}
                {cluster.last_seen
                  ? new Date(cluster.last_seen).toLocaleString()
                  : "—"}
              </small>
              <small>Location: {cluster.location}</small>
              <small>K8s: {cluster.kubernetes_version}</small>
            </div>
          </div>
        ))
      )}
    </section>
  )
}


// ============================================================
// Audit Log Page
// ============================================================

function AuditLogPage({ logs }) {
  return (
    <section className="panel">
      <div className="paneltitle">
        <h2>Audit Log</h2>
        <span>{logs.length} events</span>
      </div>

      {logs.length === 0 ? (
        <Empty text="No audit events recorded yet." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Resource</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, idx) => (
                <tr key={log.id || idx}>
                  <td className="mono">
                    {log.created_at
                      ? new Date(log.created_at).toLocaleString()
                      : "—"}
                  </td>
                  <td>
                    <span className="audit-action">{log.action}</span>
                  </td>
                  <td className="mono">{log.resource}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}


// ============================================================
// Settings Page
// ============================================================

function SettingsPage({ clusters }) {
  return (
    <section className="panel">
      <div className="paneltitle">
        <h2>Settings</h2>
        <span>Platform configuration</span>
      </div>

      <div className="settings-group">
        <h3>Registered Clusters</h3>
        {clusters.length === 0 ? (
          <Empty text="No clusters registered." />
        ) : (
          clusters.map((c) => (
            <div className="detail-row" key={c.id || c.name}>
              <div>
                <b>{c.name}</b>
                <small>{c.location}</small>
              </div>
              <span>{c.environment}</span>
              <span className="mono">{c.kubernetes_version}</span>
              <span className={c.status === "healthy" ? "pill green" : "pill yellow"}>
                {c.status}
              </span>
            </div>
          ))
        )}
      </div>

      <div className="settings-group">
        <h3>Collection Settings</h3>
        <div className="setting-row">
          <span>Telemetry interval</span>
          <span className="mono">30s</span>
        </div>
        <div className="setting-row">
          <span>UI refresh interval</span>
          <span className="mono">10s</span>
        </div>
        <div className="setting-row">
          <span>Max incidents shown</span>
          <span className="mono">100</span>
        </div>
      </div>
    </section>
  )
}


// ============================================================
// Shared components
// ============================================================

function Metric({ title, value }) {
  return (
    <div className="metric">
      <small>{title}</small>
      <strong>{value}</strong>
    </div>
  )
}

function Card({ title, value, note, danger }) {
  return (
    <div className={danger ? "stat danger" : "stat"}>
      <small>{title}</small>
      <strong>{value}</strong>
      <span>{note}</span>
    </div>
  )
}

function Empty({ text }) {
  return <div className="empty">{text}</div>
}


createRoot(document.getElementById("root")).render(<App />)