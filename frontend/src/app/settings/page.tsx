"use client";

import { useCallback, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { Button, Card, ChipOption, EmptyState, Fieldset } from "@/components/ui";
import { THEMES, TOPICS, toggle } from "@/lib/catalog";

const LIMITS = [25, 50, 100] as const;
const inputClass = "mt-1 block w-full rounded-lg border border-line-strong bg-surface-sunken px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-subtle focus:border-accent focus:ring-2 focus:ring-accent/30";

interface ScheduleSettings {
  active: boolean;
  cron_expression: string;
  timezone: string;
  themes: string[];
  topics: string[];
  limit: number;
  telegram_enabled: boolean;
  version: number;
  next_run_at: string;
}

function nextRunText(nextRunAt: string): string {
  return `저장됨 · 다음 실행 ${new Date(nextRunAt).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST`;
}

export default function SettingsPage() {
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [active, setActive] = useState(true);
  const [cron, setCron] = useState("0 8 * * *");
  const [limit, setLimit] = useState<number>(25);
  const [themes, setThemes] = useState<string[]>([]);
  const [topics, setTopics] = useState<string[]>([]);
  const [telegram, setTelegram] = useState(false);
  const [version, setVersion] = useState<number | null>(null);
  const [saveStatus, setSaveStatus] = useState("");
  const [saving, setSaving] = useState(false);

  const applySettings = useCallback((value: ScheduleSettings) => {
    setVersion(value.version); setActive(value.active); setCron(value.cron_expression); setLimit(value.limit);
    setThemes([...value.themes]); setTopics([...value.topics]); setTelegram(value.telegram_enabled);
    setSaveStatus(nextRunText(value.next_run_at));
  }, []);

  const login = useCallback(async () => {
    setLoginError("");
    try {
      const response = await fetch("/api/settings/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ password }) });
      setPassword("");
      if (!response.ok) { setLoginError("비밀번호가 일치하지 않거나 서버 설정이 완료되지 않았습니다."); return; }
      setAuthenticated(true);
      const scheduleResponse = await fetch("/api/settings/schedule");
      if (scheduleResponse.status === 404) { setSaveStatus("아직 저장된 정기 실행 설정이 없습니다. 새로 만들 수 있습니다."); return; }
      if (!scheduleResponse.ok) throw new Error("schedule_load_failed");
      applySettings(await scheduleResponse.json());
    } catch {
      setPassword(""); setLoginError("서버에 연결하지 못했습니다.");
    }
  }, [applySettings, password]);

  const save = useCallback(async () => {
    setSaving(true);
    try {
      const response = await fetch("/api/settings/schedule", { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ active, cron_expression: cron, themes, topics, limit, telegram_enabled: telegram, version }) });
      if (response.status === 409) { setSaveStatus("다른 화면에서 설정이 변경되었습니다. 새로고침 후 다시 저장해 주세요."); return; }
      if (!response.ok) { setSaveStatus("저장에 실패했습니다. cron 및 서버 연결을 확인해 주세요."); return; }
      applySettings(await response.json());
    } catch { setSaveStatus("저장에 실패했습니다. 서버 연결을 확인해 주세요."); }
    finally { setSaving(false); }
  }, [active, applySettings, cron, limit, telegram, themes, topics, version]);

  return <AppShell current="/settings" title="정기 실행 설정" description="RSS 기반 추천 작업을 KST cron으로 예약합니다. 비밀번호는 로그인 요청에만 사용하고 브라우저에 저장하지 않습니다.">
    {!authenticated ? <Card title="접근 확인" description="설정을 조회하거나 변경하려면 비밀번호를 입력하세요.">
      <div className="max-w-md"><label className="block text-sm font-medium text-ink">설정 비밀번호<input className={inputClass} type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void login(); }} /></label>
      <div className="mt-4"><Button onClick={() => void login()}>설정 페이지 열기</Button></div>{loginError && <p className="mt-3 text-sm text-negative">{loginError}</p>}</div>
    </Card> : <Card title="실행 조건" description="저장하면 worker가 다음 KST 실행 시각부터 새 설정을 사용합니다." actions={<Button onClick={() => void save()} disabled={saving}>{saving ? "저장 중…" : "저장"}</Button>}>
      <div className="grid gap-6 lg:grid-cols-2"><div className="space-y-5"><label className="flex items-center gap-3 rounded-xl border border-line bg-surface-sunken px-4 py-3 text-sm font-medium text-ink"><input className="size-4 accent-accent" type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />정기 실행 활성화</label>
        <label className="block text-sm font-medium text-ink">cron 표현식<input className={inputClass} value={cron} maxLength={128} required onChange={(event) => setCron(event.target.value)} /></label>
        <label className="block text-sm font-medium text-ink">분석 건수<select className={inputClass} value={limit} onChange={(event) => setLimit(Number(event.target.value))}>{LIMITS.map((value) => <option key={value} value={value}>{value}건</option>)}</select></label>
        <label className="flex items-center gap-3 rounded-xl border border-line bg-surface-sunken px-4 py-3 text-sm font-medium text-ink"><input className="size-4 accent-accent" type="checkbox" checked={telegram} onChange={(event) => setTelegram(event.target.checked)} />Telegram 요약 전송</label>
        <p className="text-xs leading-relaxed text-ink-subtle">Telegram 자격 증명은 서버 환경 변수로만 설정합니다.</p></div>
        <div className="space-y-5"><Fieldset legend="투자 테마">{THEMES.map((theme) => <ChipOption key={theme.value} id={`setting-theme-${theme.value}`} type="checkbox" checked={themes.includes(theme.value)} label={theme.label} onChange={() => setThemes(toggle(themes, theme.value))} />)}</Fieldset>
          <Fieldset legend="뉴스 주제">{TOPICS.map((topic) => <ChipOption key={topic.value} id={`setting-topic-${topic.value}`} type="checkbox" checked={topics.includes(topic.value)} label={topic.label} onChange={() => setTopics(toggle(topics, topic.value))} />)}</Fieldset></div></div>
      {saveStatus && <div className="mt-6"><EmptyState>{saveStatus}</EmptyState></div>}
    </Card>}
  </AppShell>;
}
