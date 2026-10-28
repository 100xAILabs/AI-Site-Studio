"""Isolated Docker runtime for generated JavaScript projects.

The API controls containers through Docker, but generated code only ever sees
its own project volume. Build containers have no network, capabilities, host
mounts, credentials, or access to the Docker socket.
"""

import asyncio
import io
import logging
import re
import tarfile
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)


class StudioRuntimeError(RuntimeError):
    pass


@dataclass
class RuntimeResult:
    exit_code: int
    logs: str


class StudioRuntime:
    IMAGE = "node:22-alpine"
    HELPER_IMAGE = "alpine:3.20"

    @staticmethod
    def _client():
        try:
            import docker
            client = docker.from_env(timeout=20)
            client.ping()
            return client
        except Exception as exc:
            raise StudioRuntimeError(
                "The isolated Studio runtime is unavailable. Start Docker Engine and enable the Studio runtime, or configure a remote sandbox provider."
            ) from exc

    @staticmethod
    def volume_name(build_id: UUID | str) -> str:
        clean = re.sub(r"[^a-f0-9]", "", str(build_id).lower())[:32]
        if len(clean) < 16:
            raise StudioRuntimeError("Invalid Studio build identifier for runtime workspace.")
        return f"studio-build-{clean}"

    def _ensure_volume(self, volume_name: str) -> None:
        client = self._client()
        try:
            client.volumes.get(volume_name)
        except Exception:
            client.volumes.create(name=volume_name, labels={"app": "ai-site-studio", "kind": "generated-project"})
        finally:
            client.close()

    def create_workspace(self, build_id: UUID | str) -> str:
        volume_name = self.volume_name(build_id)
        self._ensure_volume(volume_name)
        return volume_name

    def _safe_archive(self, files: dict[str, str]) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for path, content in files.items():
                normalized = path.replace("\\", "/").lstrip("/")
                if not normalized or any(part in {"", ".", ".."} for part in normalized.split("/")):
                    raise StudioRuntimeError(f"Unsafe generated file path: {path}")
                data = content.encode("utf-8")
                info = tarfile.TarInfo(normalized)
                info.size = len(data)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(data))
        return buffer.getvalue()

    def write_files(self, volume_name: str, files: dict[str, str]) -> None:
        client = self._client()
        helper = None
        try:
            volume = client.volumes.get(volume_name)
            helper = client.containers.run(
                self.HELPER_IMAGE,
                command=["sh", "-lc", "mkdir -p /workspace && sleep 60"],
                volumes={volume.name: {"bind": "/workspace", "mode": "rw"}},
                network_disabled=True,
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                mem_limit="128m",
                pids_limit=32,
                detach=True,
            )
            if not helper.put_archive("/workspace", self._safe_archive(files)):
                raise StudioRuntimeError("Could not write generated source files to the project volume.")
            result = helper.exec_run(["sh", "-lc", "chown -R 1000:1000 /workspace"], user="0:0")
            if result.exit_code != 0:
                raise StudioRuntimeError("Could not set safe ownership on generated source files.")
        finally:
            if helper is not None:
                try:
                    helper.remove(force=True)
                except Exception:
                    pass
            client.close()

    def run_command(
        self,
        volume_name: str,
        command: list[str],
        *,
        timeout_seconds: int,
        network_enabled: bool,
    ) -> RuntimeResult:
        client = self._client()
        container = None
        try:
            volume = client.volumes.get(volume_name)
            container = client.containers.run(
                self.IMAGE,
                command=command,
                working_dir="/workspace",
                user="1000:1000",
                environment={"HOME": "/tmp", "npm_config_cache": "/tmp/npm-cache", "CI": "1"},
                volumes={volume.name: {"bind": "/workspace", "mode": "rw"}},
                network_mode="bridge" if network_enabled else None,
                network_disabled=not network_enabled,
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=512m"},
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                mem_limit="1536m",
                nano_cpus=1_500_000_000,
                pids_limit=128,
                detach=True,
            )
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                container.reload()
                if container.status in {"exited", "dead"}:
                    break
                time.sleep(0.25)
            else:
                container.kill()
                logs = container.logs(stdout=True, stderr=True, tail=300).decode("utf-8", errors="replace")[-24000:]
                return RuntimeResult(exit_code=124, logs=f"Command timed out after {timeout_seconds}s.\n{logs}")
            result = container.wait()
            logs = container.logs(stdout=True, stderr=True, tail=300).decode("utf-8", errors="replace")[-24000:]
            return RuntimeResult(exit_code=int(result.get("StatusCode", 1)), logs=logs)
        except StudioRuntimeError:
            raise
        except Exception as exc:
            raise StudioRuntimeError(f"Sandbox command could not run: {type(exc).__name__}: {exc}") from exc
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            client.close()

    async def install_and_build(self, volume_name: str) -> RuntimeResult:
        install = await asyncio.to_thread(
            self.run_command,
            volume_name,
            ["sh", "-lc", "npm install --ignore-scripts --no-audit --no-fund && npm run build"],
            timeout_seconds=int(getattr(settings, "STUDIO_BUILD_TIMEOUT_SECONDS", 900)),
            network_enabled=True,
        )
        if install.exit_code != 0:
            return install
        return install

    async def start_preview(self, volume_name: str, stack: str) -> tuple[str, int]:
        return await asyncio.to_thread(self._start_preview, volume_name, stack)

    def _start_preview(self, volume_name: str, stack: str) -> tuple[str, int]:
        client = self._client()
        try:
            volume = client.volumes.get(volume_name)
            container = client.containers.run(
                self.IMAGE,
                command=["sh", "-lc", "npm run dev"],
                working_dir="/workspace",
                user="1000:1000",
                environment={"HOME": "/tmp", "npm_config_cache": "/tmp/npm-cache", "CI": "1"},
                volumes={volume.name: {"bind": "/workspace", "mode": "rw" if stack == "fullstack-node" else "ro"}},
                ports={"5173/tcp": ("127.0.0.1", None)},
                network_mode="bridge",
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=512m"},
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                mem_limit="1536m",
                nano_cpus=1_000_000_000,
                pids_limit=128,
                detach=True,
                labels={"app": "ai-site-studio", "build-volume": volume.name},
            )
            container.reload()
            port_info = container.attrs.get("NetworkSettings", {}).get("Ports", {}).get("5173/tcp") or []
            if not port_info or not port_info[0].get("HostPort"):
                container.remove(force=True)
                raise StudioRuntimeError("Preview container started without a published web port.")
            return container.id, int(port_info[0]["HostPort"])
        except StudioRuntimeError:
            raise
        except Exception as exc:
            raise StudioRuntimeError(f"Could not start the private app preview: {type(exc).__name__}: {exc}") from exc
        finally:
            client.close()

    async def stop_preview(self, container_id: str) -> None:
        if not container_id:
            return
        await asyncio.to_thread(self._stop_preview, container_id)

    def _stop_preview(self, container_id: str) -> None:
        client = self._client()
        try:
            container = client.containers.get(container_id)
            labels = container.labels or {}
            if labels.get("app") != "ai-site-studio":
                raise StudioRuntimeError("Refusing to stop a container not created by Studio.")
            container.remove(force=True)
        except Exception as exc:
            if type(exc).__name__ != "NotFound":
                logger.info("Could not stop Studio preview container %s: %s", container_id[:12], type(exc).__name__)
        finally:
            client.close()


studio_runtime = StudioRuntime()
