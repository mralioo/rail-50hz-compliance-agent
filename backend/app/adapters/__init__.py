"""Adapters.

Each module here implements one domain port (app/domain/<context>/ports.py)
against a real technology. Adapters may import subprocess, HTTP clients,
third-party SDKs, app.core.config - anything infrastructure-facing. Nothing
outside app/bootstrap.py should import a concrete adapter class directly;
go through the port type and the bootstrap-level factory instead.
"""
