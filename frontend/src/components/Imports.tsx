import { useState, type FormEvent } from "react";
import { Database, FileUp, LoaderCircle, Spade } from "lucide-react";
import { api } from "../api";
import type { Session, ImportResult } from "../types";
export default function Imports({
  sessions,
  onDone,
  onError,
}: {
  sessions: Session[];
  onDone: () => void;
  onError: (s: string) => void;
}) {
  const [session, setSession] = useState("");
  const [owner, setOwner] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    onError("");
    setResult(null);
    const form = new FormData();
    form.set("session_id", session);
    if (owner) form.set("owner", owner);
    files.forEach((file) => form.append("files", file));
    try {
      setResult(
        await api<ImportResult>("/import", { method: "POST", body: form }),
      );
      onDone();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="import-grid">
        <section className="panel import-panel">
          <p className="eyebrow">YOUR DATA, YOUR WORKSPACE</p>
          <h2>Bring your hands to the table.</h2>
          <p>
            Upload PokerNow CSV exports. Reuse the same session label for
            overlapping exports; matching records are merged automatically.
          </p>
          <form onSubmit={submit}>
            <label>
              Session label
              <input
                required
                maxLength={200}
                value={session}
                placeholder="e.g. Friday home game"
                onChange={(e) => setSession(e.target.value)}
              />
            </label>
            <label>
              Export owner ID <small>OPTIONAL</small>
              <input
                value={owner}
                placeholder="Stable player ID, not display name"
                onChange={(e) => setOwner(e.target.value)}
              />
            </label>
            <p className="field-help">
              Assigns “Your hand is” observations to this player. Leave blank
              when the export owner is unknown.
            </p>
            <label className="upload-zone">
              <FileUp size={30} />
              <strong>Choose your CSV exports</strong>
              <span>
                {files.length
                  ? files.map((f) => f.name).join(", ")
                  : "Multiple files · up to 25 MB each"}
              </span>
              <input
                type="file"
                accept=".csv,text/csv"
                multiple
                required
                onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              />
            </label>
            <button className="primary" disabled={busy || !files.length}>
              {busy ? (
                <LoaderCircle className="spinner" size={16} />
              ) : (
                <Database size={16} />
              )}
              Import & analyze
            </button>
          </form>
          {result && (
            <div className="import-result" role="status">
              <strong>Import complete</strong>
              <p>
                {result.new_records} new records · {result.new_sources} new
                files
              </p>
              <p>
                {result.reconciled}/{result.hands} hands reconciled ·{" "}
                {result.issues} issues
              </p>
            </div>
          )}
        </section>
        <section className="panel principles">
          <div className="principle-mark">
            <Spade size={50} />
          </div>
          <h2>
            A reliable record
            <br />
            of every hand.
          </h2>
          <ul>
            <li>Stable player IDs across name changes</li>
            <li>Exact decimal chip accounting</li>
            <li>Original record provenance retained</li>
            <li>Incomplete and unsupported hands flagged</li>
            <li>Private data stored locally in DuckDB</li>
          </ul>
          <p className="footnote">
            Accounting reconciliation is not proof of optimal play. Unknown
            cards stay unknown.
          </p>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>Your sessions</h2>
          <span className="count">{sessions.length}</span>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>SESSION</th>
                <th>FILES</th>
                <th>HANDS</th>
                <th>RECONCILED</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.session_id}>
                  <td>
                    {s.session_id}
                    <small>
                      {s.start
                        ? new Date(s.start).toLocaleDateString(undefined, {
                            timeZone: "UTC",
                          })
                        : "Unknown date"}
                    </small>
                  </td>
                  <td>{s.sources}</td>
                  <td>{s.hands}</td>
                  <td>{s.reconciled}</td>
                  <td>
                    <button
                      className="secondary small"
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          await api(
                            "/sessions/" +
                              encodeURIComponent(s.session_id) +
                              "/rebuild",
                            { method: "POST" },
                          );
                          onDone();
                        } catch (e) {
                          onError((e as Error).message);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Rebuild
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
