export interface VaultStatus {
  passphrase_set: boolean;
  unlocked: boolean;
  failed_attempts: number;
  retry_after: number;
  kdf_n: number | null;
  auto_lock_minutes: number;
}

export type Tier = "unattended" | "protected";

export interface Credential {
  id: string;
  label: string;
  kind: "ssh" | "token";
  tier: Tier;
  username: string | null;
  public_key: string | null;
  fingerprint: string | null;
  created_at: string;
  repo_count: number;
}

export interface Repo {
  id: string;
  url: string;
  host: string;
  owner: string;
  name: string;
  slug: string;
  category: string;
  credential_id: string | null;
  ref_kind: string;
  pinned_ref: string | null;
  installed_ref: string | null;
  installed_version: string | null;
  available_version: string | null;
  auto_update: boolean;
  installed: boolean;
  update_available: boolean;
  last_checked: string | null;
  last_error: string | null;
}

export interface GitRef {
  name: string;
  kind: string;
  sha: string;
}

export interface Release {
  tag: string;
  name: string | null;
  body: string | null;
  prerelease: boolean;
  published_at: string | null;
}

export interface UpdateSummary {
  checked: number;
  skipped_locked: number;
  updates: string[];
  upgraded: string[];
  failed: Record<string, string>;
}

export interface HostKey {
  line: string;
  type: string;
  fingerprint: string;
}

export interface Info {
  version: string;
  dev_mode: boolean;
  supervisor: boolean;
  ingress_base: string;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly detail?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const text = await response.text();
  let payload: Record<string, unknown> = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { error: text.slice(0, 200) };
    }
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      String(payload.code ?? "Error"),
      String(payload.error ?? response.statusText),
      payload.detail ? String(payload.detail) : undefined,
    );
  }
  return payload as T;
}

export interface Theme {
  name: string | null;
  dark: boolean;
  variables: Record<string, string>;
}

export const api = {
  info: () => request<Info>("api/info"),
  theme: (dark: boolean) => request<Theme>(`api/theme?dark=${dark ? 1 : 0}`),

  vault: {
    status: () => request<VaultStatus>("api/vault"),
    setPassphrase: (passphrase: string) =>
      request<VaultStatus>("api/vault/passphrase", "POST", { passphrase }),
    change: (current: string, next: string) =>
      request<VaultStatus>("api/vault/passphrase", "PUT", { current, new: next }),
    remove: (passphrase: string) =>
      request<VaultStatus & { migrated: number }>("api/vault/passphrase", "DELETE", { passphrase }),
    unlock: (passphrase: string) => request<VaultStatus>("api/vault/unlock", "POST", { passphrase }),
    lock: () => request<VaultStatus>("api/vault/lock", "POST"),
  },

  credentials: {
    list: () => request<Credential[]>("api/credentials"),
    create: (payload: Record<string, unknown>) =>
      request<Credential>("api/credentials", "POST", payload),
    remove: (id: string) => request<{ deleted: boolean }>(`api/credentials/${id}`, "DELETE"),
    rotate: (id: string) => request<Credential>(`api/credentials/${id}/rotate`, "POST"),
    setTier: (id: string, tier: Tier) =>
      request<Credential>(`api/credentials/${id}/tier`, "PUT", { tier }),
    test: (id: string, url: string) =>
      request<{ ok: boolean; tags: string[]; branches: string[] }>(
        `api/credentials/${id}/test`,
        "POST",
        { url },
      ),
  },

  repos: {
    list: () => request<Repo[]>("api/repos"),
    add: (payload: Record<string, unknown>) => request<Repo>("api/repos", "POST", payload),
    patch: (id: string, payload: Record<string, unknown>) =>
      request<Repo>(`api/repos/${id}`, "PATCH", payload),
    remove: (id: string, force = false) =>
      request<{ deleted: boolean; modified: string[] }>(
        `api/repos/${id}?force=${force ? 1 : 0}`,
        "DELETE",
      ),
    refs: (id: string) => request<GitRef[]>(`api/repos/${id}/refs`),
    releases: (id: string) => request<Release[]>(`api/repos/${id}/releases`),
    refresh: (id: string) => request<Repo>(`api/repos/${id}/refresh`, "POST"),
    install: (id: string, ref?: string) =>
      request<{ files: number; domain: string | null; repo: Repo }>(
        `api/repos/${id}/install`,
        "POST",
        { ref },
      ),
    uninstall: (id: string, force = false) =>
      request<{ removed: number; missing: number; modified: string[] }>(
        `api/repos/${id}/uninstall`,
        "POST",
        { force },
      ),
  },

  hosts: {
    scan: (host: string, port = 22) =>
      request<{ host: string; port: number; keys: HostKey[] }>("api/hosts/scan", "POST", {
        host,
        port,
      }),
    trust: (lines: string[]) => request<{ added: number }>("api/hosts/trust", "POST", { lines }),
  },

  updates: {
    check: () => request<UpdateSummary>("api/updates/check", "POST"),
  },

  core: {
    restart: () => request<{ restarting: boolean }>("api/core/restart", "POST"),
  },
};
