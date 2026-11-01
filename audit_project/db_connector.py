import os
import time
import socket
import sqlite3
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Tuple
import requests
import pandas as pd

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None


POSTGRES_SUPABASE_DDL = """-- =========================================================
-- AUDITLENS AI CORE - POSTGRESQL & SUPABASE SCHEMA DDL
-- Entitas: PT Suryamicrosystem
-- =========================================================

CREATE TABLE IF NOT EXISTS public.projects (
    id SERIAL PRIMARY KEY,
    project_name VARCHAR(255) NOT NULL DEFAULT 'Audit Keuangan TA 2026',
    client_name VARCHAR(255) NOT NULL DEFAULT 'PT Suryamicrosystem',
    audit_period VARCHAR(50) NOT NULL DEFAULT '2026',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.audit_findings (
    id SERIAL PRIMARY KEY,
    project_id INTEGER DEFAULT 1 REFERENCES public.projects(id),
    area VARCHAR(150) NOT NULL,
    condition TEXT NOT NULL,
    criteria TEXT NOT NULL,
    cause TEXT NOT NULL,
    effect TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    risk_level VARCHAR(20) CHECK (risk_level IN ('HIGH', 'MEDIUM', 'LOW')),
    management_response TEXT DEFAULT '-',
    pic VARCHAR(150) DEFAULT '-',
    target_date VARCHAR(50) DEFAULT '-',
    status VARCHAR(50) DEFAULT 'OPEN',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_findings_risk ON public.audit_findings(risk_level);
CREATE INDEX IF NOT EXISTS idx_audit_findings_area ON public.audit_findings(area);
"""


class MultiBackendDBConnector:
    """
    Manajer koneksi Multi-Backend Database untuk AuditLens AI Core:
    1. SQLite Local Engine (audit_system.db)
    2. PostgreSQL Enterprise Engine (External ERP / Data Warehouse)
    3. Supabase Cloud Engine (PostgREST API & PostgreSQL Pooler)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.sqlite_path = self.config.get("sqlite_path", "audit_system.db")
        self.backend_type = str(self.config.get("backend_type", "sqlite")).lower()

    def test_connection(self) -> Dict[str, Any]:
        """
        Menguji konektivitas ke database engine yang dipilih oleh Auditor.
        """
        t0 = time.perf_counter()
        b_type = self.backend_type

        if "sqlite" in b_type:
            try:
                conn = sqlite3.connect(self.sqlite_path)
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM audit_findings")
                cnt = cur.fetchone()[0]
                conn.close()
                ms = round((time.perf_counter() - t0) * 1000.0, 2)
                return {
                    "ok": True,
                    "status": "CONNECTED",
                    "engine": "SQLite Local Engine",
                    "latency_ms": ms,
                    "message": f"Terhubung ke berkas '{self.sqlite_path}' ({cnt} temuan audit tersimpan)."
                }
            except Exception as e:
                return {
                    "ok": False,
                    "status": "ERROR",
                    "engine": "SQLite Local Engine",
                    "latency_ms": 0.0,
                    "message": str(e)
                }

        elif "postgres" in b_type:
            dsn = self.config.get("pg_dsn", "").strip()
            host = self.config.get("pg_host", "localhost").strip()
            port = int(self.config.get("pg_port", 5432))
            dbname = self.config.get("pg_database", "postgres").strip()
            user = self.config.get("pg_user", "postgres").strip()
            password = self.config.get("pg_password", "")

            if dsn:
                parsed = urlparse(dsn)
                if parsed.hostname:
                    host = parsed.hostname
                if parsed.port:
                    port = parsed.port

            if psycopg2 is not None:
                try:
                    conn = psycopg2.connect(dsn) if dsn else psycopg2.connect(
                        host=host, port=port, dbname=dbname, user=user, password=password, connect_timeout=4
                    )
                    cur = conn.cursor()
                    cur.execute("SELECT version();")
                    ver = cur.fetchone()[0]
                    conn.close()
                    ms = round((time.perf_counter() - t0) * 1000.0, 2)
                    return {
                        "ok": True,
                        "status": "CONNECTED",
                        "engine": "PostgreSQL External",
                        "latency_ms": ms,
                        "message": f"Koneksi PostgreSQL Berhasil: {ver[:60]}..."
                    }
                except Exception as e:
                    return {
                        "ok": False,
                        "status": "FALLBACK_LOCAL",
                        "engine": "PostgreSQL External",
                        "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
                        "message": f"PostgreSQL ({host}:{port}) belum terjangkau ({e}). Menggunakan fallback SQLite lokal."
                    }
            else:
                try:
                    with socket.create_connection((host, port), timeout=3):
                        ms = round((time.perf_counter() - t0) * 1000.0, 2)
                        return {
                            "ok": True,
                            "status": "CONNECTED",
                            "engine": "PostgreSQL External (Socket Verified)",
                            "latency_ms": ms,
                            "message": f"Port PostgreSQL {host}:{port} aktif & dapat dijangkau."
                        }
                except Exception as e:
                    return {
                        "ok": False,
                        "status": "FALLBACK_LOCAL",
                        "engine": "PostgreSQL External",
                        "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
                        "message": f"Endpoint PostgreSQL ({host}:{port}) belum dikonfigurasi/terjangkau ({e}). Fallback SQLite aktif."
                    }

        elif "supabase" in b_type:
            supabase_url = self.config.get("supabase_url", "").strip().rstrip("/")
            supabase_key = self.config.get("supabase_key", "").strip()
            if not supabase_url or not supabase_key:
                return {
                    "ok": False,
                    "status": "STANDBY (LOCAL CACHE)",
                    "engine": "Supabase Cloud",
                    "latency_ms": 0.0,
                    "message": "Masukkan Supabase Project URL & API Key pada modul Pengaturan untuk sinkronisasi awan (Cache SQLite aktif)."
                }
            try:
                headers = {
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json"
                }
                res = requests.get(f"{supabase_url}/rest/v1/audit_findings?select=id&limit=1", headers=headers, timeout=5)
                ms = round((time.perf_counter() - t0) * 1000.0, 2)
                if res.status_code in (200, 206):
                    return {
                        "ok": True,
                        "status": "CONNECTED",
                        "engine": "Supabase Cloud (PostgREST)",
                        "latency_ms": ms,
                        "message": f"Terhubung ke Supabase '{supabase_url}' (Tabel audit_findings siap)."
                    }
                elif res.status_code == 404:
                    return {
                        "ok": True,
                        "status": "CONNECTED (DDL NEEDED)",
                        "engine": "Supabase Cloud",
                        "latency_ms": ms,
                        "message": "Endpoint Supabase aktif, buka Popup Skema DDL SQL untuk membuat tabel 'audit_findings'."
                    }
                else:
                    return {
                        "ok": False,
                        "status": "AUTH_ERROR",
                        "engine": "Supabase Cloud",
                        "latency_ms": ms,
                        "message": f"Respons Supabase HTTP {res.status_code}: {res.text[:100]}"
                    }
            except Exception as e:
                return {
                    "ok": False,
                    "status": "FALLBACK_LOCAL",
                    "engine": "Supabase Cloud",
                    "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
                    "message": f"Gagal menghubungi Supabase API ({e}). Fallback SQLite aktif."
                }

        return {
            "ok": False,
            "status": "UNKNOWN",
            "engine": self.backend_type,
            "latency_ms": 0.0,
            "message": "Tipe backend tidak dikenal."
        }

    def insert_finding(self, finding: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Menyimpan temuan 5C ke database lokal SQLite dan secara otomatis menyinkronkannya
        ke PostgreSQL / Supabase apabila backend eksternal diaktifkan oleh Auditor.
        """
        conn = sqlite3.connect(self.sqlite_path)
        conn.cursor().execute("""
            INSERT INTO audit_findings (
                project_id, area, condition, criteria, cause, effect,
                recommendation, risk_level, management_response, pic, target_date, status
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            finding.get("area", "Umum"),
            finding.get("condition", "-"),
            finding.get("criteria", "-"),
            finding.get("cause", "-"),
            finding.get("effect", "-"),
            finding.get("recommendation", "-"),
            str(finding.get("risk_level", "MEDIUM")).upper(),
            finding.get("management_response", "-"),
            finding.get("pic", "-"),
            finding.get("target_date", "-"),
            finding.get("status", "OPEN")
        ))
        conn.commit()
        conn.close()

        b_type = self.backend_type
        if "supabase" in b_type:
            supabase_url = self.config.get("supabase_url", "").strip().rstrip("/")
            supabase_key = self.config.get("supabase_key", "").strip()
            if supabase_url and supabase_key:
                try:
                    headers = {
                        "apikey": supabase_key,
                        "Authorization": f"Bearer {supabase_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal"
                    }
                    payload = {
                        "project_id": 1,
                        "area": finding.get("area", "Umum"),
                        "condition": finding.get("condition", "-"),
                        "criteria": finding.get("criteria", "-"),
                        "cause": finding.get("cause", "-"),
                        "effect": finding.get("effect", "-"),
                        "recommendation": finding.get("recommendation", "-"),
                        "risk_level": str(finding.get("risk_level", "MEDIUM")).upper(),
                        "management_response": finding.get("management_response", "-"),
                        "pic": finding.get("pic", "-"),
                        "target_date": finding.get("target_date", "-"),
                        "status": finding.get("status", "OPEN")
                    }
                    res = requests.post(f"{supabase_url}/rest/v1/audit_findings", json=payload, headers=headers, timeout=5)
                    if res.status_code in (200, 201, 204):
                        return True, "Temuan berhasil disimpan ke SQLite Lokal & disinkronkan ke Supabase Cloud!"
                    return True, f"Tersimpan di SQLite Lokal (Sinkronisasi Supabase HTTP {res.status_code})."
                except Exception as e:
                    return True, f"Tersimpan di SQLite Lokal (Supabase offline: {e})."

        elif "postgres" in b_type and psycopg2 is not None:
            dsn = self.config.get("pg_dsn", "").strip()
            host = self.config.get("pg_host", "localhost").strip()
            port = int(self.config.get("pg_port", 5432))
            dbname = self.config.get("pg_database", "postgres").strip()
            user = self.config.get("pg_user", "postgres").strip()
            password = self.config.get("pg_password", "")
            try:
                pg_conn = psycopg2.connect(dsn) if dsn else psycopg2.connect(
                    host=host, port=port, dbname=dbname, user=user, password=password, connect_timeout=4
                )
                pg_cur = pg_conn.cursor()
                pg_cur.execute(POSTGRES_SUPABASE_DDL)
                pg_cur.execute("""
                    INSERT INTO public.audit_findings (
                        project_id, area, condition, criteria, cause, effect,
                        recommendation, risk_level, management_response, pic, target_date, status
                    ) VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    finding.get("area", "Umum"),
                    finding.get("condition", "-"),
                    finding.get("criteria", "-"),
                    finding.get("cause", "-"),
                    finding.get("effect", "-"),
                    finding.get("recommendation", "-"),
                    str(finding.get("risk_level", "MEDIUM")).upper(),
                    finding.get("management_response", "-"),
                    finding.get("pic", "-"),
                    finding.get("target_date", "-"),
                    finding.get("status", "OPEN")
                ))
                pg_conn.commit()
                pg_conn.close()
                return True, "Temuan berhasil disimpan ke SQLite Lokal & PostgreSQL External!"
            except Exception as e:
                return True, f"Tersimpan di SQLite Lokal (PostgreSQL External belum terjangkau: {e})."

        return True, "Temuan Audit berhasil disimpan ke Database SQLite Lokal!"

    def update_finding_status(self, finding_id: int, new_status: str, management_response: Optional[str] = None) -> Tuple[bool, str]:
        """
        Memperbarui status tindak lanjut temuan audit (OPEN -> IN_PROGRESS -> CLOSED) pada database.
        """
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cur = conn.cursor()
            if management_response is not None and management_response.strip():
                cur.execute(
                    "UPDATE audit_findings SET status = ?, management_response = ? WHERE id = ?",
                    (new_status, management_response.strip(), int(finding_id))
                )
            else:
                cur.execute(
                    "UPDATE audit_findings SET status = ? WHERE id = ?",
                    (new_status, int(finding_id))
                )
            conn.commit()
            conn.close()
            return True, f"Status Temuan ID #{finding_id} berhasil diperbarui menjadi {new_status}."
        except Exception as e:
            return False, f"Gagal memperbarui status temuan: {e}"

    def delete_finding(self, finding_id: int) -> Tuple[bool, str]:
        """
        Menghapus temuan audit berdasarkan ID dari database lokal.
        """
        try:
            conn = sqlite3.connect(self.sqlite_path)
            conn.cursor().execute("DELETE FROM audit_findings WHERE id = ?", (int(finding_id),))
            conn.commit()
            conn.close()
            return True, f"Temuan ID #{finding_id} telah dihapus dari register."
        except Exception as e:
            return False, f"Gagal menghapus temuan: {e}"

    def fetch_findings(self) -> List[Dict[str, Any]]:
        """
        Mengambil seluruh daftar temuan audit dari backend aktif (atau fallback ke SQLite lokal).
        """
        b_type = self.backend_type
        if "supabase" in b_type:
            supabase_url = self.config.get("supabase_url", "").strip().rstrip("/")
            supabase_key = self.config.get("supabase_key", "").strip()
            if supabase_url and supabase_key:
                try:
                    headers = {
                        "apikey": supabase_key,
                        "Authorization": f"Bearer {supabase_key}"
                    }
                    res = requests.get(f"{supabase_url}/rest/v1/audit_findings?select=*&order=id.desc", headers=headers, timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, list) and len(data) > 0:
                            return data
                except Exception:
                    pass

        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.cursor().execute("SELECT * FROM audit_findings ORDER BY id DESC").fetchall()]
        conn.close()
        return rows
