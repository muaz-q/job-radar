import { useEffect, useMemo, useState } from "react";
import { CheckIcon } from "../components/Icons";
import { RevealTitle, Segmented } from "../components/Motion";
import { ErrorBox, Loading } from "../components/Status";
import { api, HOSTED } from "../services/api";

const APPEARANCE = [["system", "System"], ["light", "Light"], ["dark", "Dark"]];

function Switch({ id, checked, onChange }) {
  return (
    <span className="switch">
      <input id={id} type="checkbox" role="switch" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="switch-track" aria-hidden="true" />
    </span>
  );
}

// Multi-select as chips: far more compact than a column of switches, and selection reads at a glance.
function ChipGroup({ label, options, selected, onChange, hint }) {
  const toggle = (option) => onChange(selected.includes(option) ? selected.filter((o) => o !== option) : [...selected, option]);
  return (
    <>
      <h2 className="section-label">{label}</h2>
      <div className="card">
        <div className="chips" role="group" aria-label={label}>
          {options.map((option) => {
            const on = selected.includes(option);
            return (
              <button key={option} type="button" className="chip" aria-pressed={on} onClick={() => toggle(option)}>
                {on && <CheckIcon />}{option}
              </button>
            );
          })}
        </div>
      </div>
      <p className="footnote">{selected.length === 0 ? "Nothing selected, so this filter is off." : hint}</p>
    </>
  );
}

const toKeywordList = (text) => text.split(",").map((k) => k.trim()).filter(Boolean);
const normalized = (form, keywordText) => JSON.stringify({
  ...form,
  keywords: toKeywordList(keywordText),
  locations: [...form.locations].sort(),
  job_types: [...form.job_types].sort(),
  categories: [...form.categories].sort(),
});

export default function SettingsPage({ notifier, theme }) {
  const [options, setOptions] = useState(null);
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(null);
  const [keywordText, setKeywordText] = useState("");
  const [status, setStatus] = useState({ saving: false, message: null, error: null });

  useEffect(() => {
    Promise.all([api.getSettingsOptions(), api.getSettings()])
      .then(([opts, settings]) => {
        setOptions(opts);
        setForm(settings);
        setKeywordText(settings.keywords.join(", "));
        setSaved(normalized(settings, settings.keywords.join(", ")));
      })
      .catch((error) => setStatus((s) => ({ ...s, error })));
  }, []);

  const dirty = useMemo(() => form && saved !== normalized(form, keywordText), [form, keywordText, saved]);

  const update = (key) => (value) => {
    setForm((f) => ({ ...f, [key]: value }));
    setStatus((s) => ({ ...s, message: null }));
  };

  async function save(event) {
    event.preventDefault();
    setStatus({ saving: true, message: null, error: null });
    try {
      const { detail, ...result } = await api.saveSettings({ ...form, keywords: toKeywordList(keywordText) });
      const text = result.keywords.join(", ");
      setForm(result);
      setKeywordText(text);
      setSaved(normalized(result, text));
      setStatus({ saving: false, message: detail ?? "Saved", error: null });
    } catch (error) {
      setStatus({ saving: false, message: null, error });
    }
  }

  const head = (
    <div className="page-head">
      <div>
        <RevealTitle>Settings</RevealTitle>
        <p className="page-sub">Decide which new jobs alert you</p>
      </div>
    </div>
  );

  const appearance = (
    <>
      <h2 className="section-label" style={{ marginTop: 0 }}>Appearance</h2>
      <Segmented className="appearance" role="radiogroup" label="Appearance" options={APPEARANCE}
                 value={theme.choice} onChange={(value, event) => theme.setChoice(value, event)} />
    </>
  );

  if (!form || !options) {
    return <section className="narrow">{head}{appearance}<div style={{ marginTop: 32 }}><ErrorBox error={status.error} />{!status.error && <Loading />}</div></section>;
  }

  const { permission, requestPermission, sendTest } = notifier;

  return (
    <section className="narrow">
      {head}
      {appearance}

      <form onSubmit={save}>
        <ChipGroup label="Locations" options={options.locations} selected={form.locations} onChange={update("locations")}
                   hint="Jobs in any selected location." />
        <ChipGroup label="Job types" options={options.job_types} selected={form.job_types} onChange={update("job_types")}
                   hint="Jobs of any selected type." />
        <ChipGroup label="Categories" options={options.categories} selected={form.categories} onChange={update("categories")}
                   hint="Jobs in any selected category." />

        <h2 className="section-label">Keywords and freshness</h2>
        <div className="group">
          <input id="keywords" className="field wide-field" type="text" value={keywordText} placeholder="Keywords, e.g. python, backend"
                 aria-label="Keywords, separated by commas" onChange={(e) => { setKeywordText(e.target.value); setStatus((s) => ({ ...s, message: null })); }} />
          <label className="row plain setting" htmlFor="max-age">
            <span>Posted within days</span>
            <input id="max-age" className="field inline-field" type="number" min="1" max="365" placeholder="Any"
                   value={form.max_age_days ?? ""}
                   onChange={(e) => update("max_age_days")(e.target.value === "" ? null : Number(e.target.value))} />
          </label>
        </div>
        <p className="footnote">A job matches if it contains any keyword. Leave either empty to skip it.</p>

        <h2 className="section-label">Notifications</h2>
        <div className="group">
          <label className="row plain setting" htmlFor="browser-popups">
            <span>{HOSTED ? "Browser alerts while open" : "Browser notifications"}</span>
            <Switch id="browser-popups" checked={form.browser_notifications} onChange={update("browser_notifications")} />
          </label>
          {permission !== "granted" && (
            <div className="row plain setting" style={{ cursor: "default" }}>
              <span className="muted">
                {permission === "default" && "This browser hasn't allowed alerts yet."}
                {permission === "denied" && "Blocked. Allow alerts for this site from the address bar."}
                {permission === "unsupported" && "This browser doesn't support alerts."}
              </span>
              {permission === "default" && <button type="button" className="btn btn-sm" onClick={requestPermission}>Allow</button>}
            </div>
          )}
          {permission === "granted" && (
            <div className="row plain setting" style={{ cursor: "default" }}>
              <span className="muted">Allowed in this browser</span>
              <button type="button" className="btn btn-sm" onClick={sendTest}>Send Test</button>
            </div>
          )}
        </div>
        {HOSTED && <p className="footnote">Telegram alerts arrive from the hourly scan whether or not this page is open.</p>}

        <div style={{ marginTop: 24 }}><ErrorBox error={status.error} /></div>
        <div className="save-bar">
          <button className="btn btn-primary btn-lg" type="submit" disabled={!dirty || status.saving}>
            {status.saving ? "Saving…" : "Save Changes"}
          </button>
          {status.message && !dirty && <span className="saved">{status.message}</span>}
        </div>
        {HOSTED && <p className="footnote" style={{ paddingInline: 0 }}>Saving asks for your admin password once per tab.</p>}
      </form>
    </section>
  );
}
