"use client";

import { useEffect, useState } from "react";

const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const development = process.env.NODE_ENV === "development";

type UserProfile = { id: string; email: string; name: string; picture?: string | null };

export default function Home() {
  const [uid, setUid] = useState("");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [csrf, setCsrf] = useState("");
  const [url, setUrl] = useState("");
  const [provider, setProvider] = useState("gemini");
  const [model, setModel] = useState("gemini-2.5-flash");
  const [key, setKey] = useState("");
  const [docs, setDocs] = useState<any[]>([]);
  const [companies, setCompanies] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [msg, setMsg] = useState("Sign in to start building your job-search workspace.");

  useEffect(() => {
    fetch(api + "/api/auth/me", { credentials: "include" })
      .then(async (response) => response.ok ? response.json() : null)
      .then((data) => {
        if (data?.authenticated) {
          setUser(data.user);
          setCsrf(data.csrf_token);
          setMsg("Signed in. Your workspace is ready.");
        }
      })
      .catch(() => setMsg("API is not reachable yet. Start the local services or check deployment."));
  }, []);

  const authHeaders = () => ({
    ...(development && uid ? { "X-User-Id": uid } : {}),
    ...(csrf ? { "X-CSRF-Token": csrf } : {}),
  });

  async function saveKey() {
    const response = await fetch(api + "/api/v1/settings/provider-key", {
      method: "PUT",
      credentials: "include",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ provider, model, api_key: key }),
    });
    setMsg(response.ok ? "Provider key validated and encrypted." : await response.text());
    if (response.ok) setKey("");
  }

  async function addCompany() {
    const response = await fetch(api + "/api/v1/companies", {
      method: "POST",
      credentials: "include",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ website_url: url }),
    });
    if (response.ok) {
      setMsg("Company added. Career-page discovery has been queued.");
      setUrl("");
      await loadCompanies();
      await loadJobs();
    } else {
      setMsg(await response.text());
    }
  }

  async function loadCompanies() {
    const response = await fetch(api + "/api/v1/companies", {
      credentials: "include",
      headers: authHeaders(),
    });
    if (response.ok) setCompanies(await response.json());
    else setMsg(await response.text());
  }

  async function loadJobs() {
    const response = await fetch(api + "/api/v1/jobs", {
      credentials: "include",
      headers: authHeaders(),
    });
    if (response.ok) setJobs(await response.json());
    else setMsg(await response.text());
  }

  async function loadDocuments() {
    const response = await fetch(api + "/api/v1/documents", {
      credentials: "include",
      headers: authHeaders(),
    });
    if (response.ok) setDocs(await response.json());
    else setMsg(await response.text());
  }

  async function upload(file?: File) {
    if (!file) return;
    const data = new FormData();
    data.append("file", file);
    const response = await fetch(api + "/api/v1/documents", {
      method: "POST",
      credentials: "include",
      headers: authHeaders(),
      body: data,
    });
    if (response.ok) {
      const document = await response.json();
      setDocs((items) => [document, ...items]);
      setMsg("PDF uploaded.");
    } else {
      setMsg(await response.text());
    }
  }

  async function loadHistory() {
    const response = await fetch(api + "/api/v1/applications", {
      credentials: "include",
      headers: authHeaders(),
    });
    if (response.ok) setHistory(await response.json());
    else setMsg(await response.text());
  }

  async function createLocalUser() {
    const response = await fetch(api + "/api/auth/dev/bootstrap", {
      method: "POST",
      credentials: "include",
    });
    if (response.ok) {
      const localUser = await response.json();
      setUid(localUser.id);
      setMsg("Local development profile created. Workspace actions are enabled.");
    } else {
      setMsg(await response.text());
    }
  }

  async function logout() {
    const response = await fetch(api + "/api/auth/logout", {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-Token": csrf },
    });
    if (response.ok) {
      setUser(null);
      setCsrf("");
      setMsg("Signed out.");
    } else {
      setMsg(await response.text());
    }
  }

  const canUseWorkspace = Boolean(user || (development && uid));

  useEffect(() => {
    if (canUseWorkspace) {
      void loadCompanies();
      void loadJobs();
    }
  }, [canUseWorkspace, user, uid, csrf]);

  return (
    <main className="wrap">
      <nav>
        <b>◈ ApplyPilot <span>AI</span></b>
        {user ? (
          <div className="account">
            <span>{user.name}</span>
            <button className="quiet" onClick={logout}>Sign out</button>
          </div>
        ) : (
          <a href={api + "/api/auth/google"}>Continue with Google ↗</a>
        )}
      </nav>
      <header>
        <small>YOUR CAREER WORKSPACE</small>
        <h1>Make every application<br /><i>count.</i></h1>
        <p>Bring your own AI key. Add a company career page. Organize your experience, discover roles, and prepare applications for your review.</p>
        <div className="notice">● {msg}</div>
        {user && <div className="notice">Signed in as {user.email}</div>}
      </header>
      <section className="grid">
        <article className="panel wide">
          <small>01 / DISCOVERY</small>
          <h2>Company career page</h2>
          <label>Company website or careers URL</label>
          <div className="line">
            <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://company.com/careers" />
            <button onClick={addCompany} disabled={!canUseWorkspace || !url}>Add company ↗</button>
          </div>
          <div className="toolbar">
            <button className="quiet" onClick={loadCompanies} disabled={!canUseWorkspace}>Refresh companies ↻</button>
            <button className="quiet" onClick={loadJobs} disabled={!canUseWorkspace}>Refresh jobs ↻</button>
          </div>
          {companies.map((company) => (
            <div className="row" key={company.id}>
              <span>{company.normalized_domain}<small className="subrow">{company.discovery_error || company.discovery_status}</small></span>
              <small>{company.discovery_status}</small>
            </div>
          ))}
          <p>Discovery checks public HTTPS pages and supported career platforms. Sites that block automated access are skipped.</p>
        </article>
        <article className="panel wide">
          <small>DISCOVERED OPENINGS</small>
          <h2>Jobs found <span className="count">{jobs.length}</span></h2>
          {jobs.length ? jobs.map((job) => (
            <div className="job" key={job.id}>
              <div>
                <strong>{job.title}</strong>
                <p>{job.company} · {job.location || "Location not listed"}{job.workplace_type ? " · " + job.workplace_type : ""}</p>
                <small>{job.source}</small>
              </div>
              <a href={job.apply_url} target="_blank" rel="noreferrer">View role ↗</a>
            </div>
          )) : <p>No jobs loaded yet. Add a company and refresh after its discovery status changes to completed.</p>}
        </article>
        <article className="panel">
          <small>02 / MODEL ACCESS · BYOK</small>
          <h2>Your AI provider</h2>
          <label>Provider</label>
          <select value={provider} onChange={(event) => {
            setProvider(event.target.value);
            setModel(({ gemini: "gemini-2.5-flash", openai: "gpt-4.1-mini", anthropic: "claude-3-7-sonnet-latest", xai: "grok-3-mini" } as Record<string, string>)[event.target.value]);
          }}>
            <option value="gemini">Gemini</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Claude</option>
            <option value="xai">Grok</option>
          </select>
          <label>Model</label>
          <input value={model} onChange={(event) => setModel(event.target.value)} />
          <label>API key</label>
          <input type="password" value={key} onChange={(event) => setKey(event.target.value)} placeholder="Paste key" />
          <button className="full" onClick={saveKey} disabled={!canUseWorkspace || !key}>Save encrypted key</button>
          <p>Keys are encrypted before storage and never returned by the API.</p>
        </article>
        <article className="panel">
          <small>03 / YOUR CONTEXT</small>
          <h2>Knowledge base <button className="quiet" onClick={loadDocuments} disabled={!canUseWorkspace}>Refresh ↻</button></h2>
          <label className="drop">
            <input type="file" accept="application/pdf,.pdf" disabled={!canUseWorkspace} onChange={(event) => upload(event.target.files?.[0])} />
            <strong>＋ Upload resume / knowledge PDF</strong>
            <span>PDF only · 20 MB limit</span>
          </label>
          {docs.map((document) => <div className="row" key={document.id}>{document.filename}<small>{document.status}</small></div>)}
        </article>
        <article className="panel">
          <small>04 / TRACKING</small>
          <h2>Application history <button className="quiet" onClick={loadHistory} disabled={!canUseWorkspace}>Refresh ↻</button></h2>
          {history.length ? history.map((item) => <div className="row" key={item.id}>{item.job_id}<small>{item.status}</small></div>) : <p>Applications appear here after discovery and preparation.</p>}
        </article>
      </section>
      {development && (
        <aside className="dev">
          <label>Development-only user UUID (local testing only)</label>
          <input value={uid} onChange={(event) => setUid(event.target.value)} placeholder="Existing user UUID" />
          <button className="quiet" onClick={createLocalUser}>Create local test profile</button>
        </aside>
      )}
      <footer>APPLYPILOT AI <span>Privacy first · Human review before submit</span></footer>
    </main>
  );
}
