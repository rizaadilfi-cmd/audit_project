CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL DEFAULT 'Audit Keuangan TA 2026',
    client_name TEXT NOT NULL DEFAULT 'PT Suryamicrosystem',
    audit_period TEXT NOT NULL DEFAULT '2026'
);

CREATE TABLE IF NOT EXISTS audit_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER DEFAULT 1,
    area TEXT NOT NULL,
    condition TEXT NOT NULL,
    criteria TEXT NOT NULL,
    cause TEXT NOT NULL,
    effect TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    risk_level TEXT CHECK(risk_level IN ('HIGH', 'MEDIUM', 'LOW')),
    management_response TEXT DEFAULT '-',
    pic TEXT DEFAULT '-',
    target_date TEXT DEFAULT '-',
    status TEXT DEFAULT 'OPEN'
);
