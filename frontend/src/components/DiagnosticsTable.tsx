"use client";

import type { ImpactDiagnostics } from "@/lib/types";

const DIAGNOSTIC_ROWS: Array<[string, keyof ImpactDiagnostics]> = [
  ["실패한 이벤트 추출 배치", "failed_extraction_batches"],
  ["형식 오류로 제외된 추출 항목", "malformed_extraction_items"],
  ["영향 관측이 없는 승인 이벤트", "events_without_impact_observations"],
  ["생성된 영향 관측", "total_impact_observations"],
  ["점수 반영 가능 영향", "eligible_impact_observations"],
  ["기업 미해결로 제외", "unresolved_company_exclusions"],
  ["기업 식별자 누락으로 제외", "missing_company_identity_exclusions"],
  ["검증 미달 REVIEW로 제외", "review_not_verified_exclusions"],
  ["영향 방향 미확정으로 제외", "unknown_direction_exclusions"],
  ["점수화된 종목", "scored_company_count"],
];

interface DiagnosticsTableProps {
  diagnostics: ImpactDiagnostics | null;
  hasResult: boolean;
}

export function DiagnosticsTable({ diagnostics, hasResult }: DiagnosticsTableProps) {
  return (
    <section className="panel">
      <h2>후보 제외 진단</h2>
      {!diagnostics ? (
        <p className="empty">
          {hasResult
            ? "후보 제외 진단을 만들지 못했습니다."
            : "추천 실행 후 후보가 점수화되지 않은 이유를 표시합니다."}
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>단계별 판단</th>
              <th>건수</th>
            </tr>
          </thead>
          <tbody>
            {DIAGNOSTIC_ROWS.map(([label, key]) => (
              <tr key={key}>
                <td>{label}</td>
                <td>{diagnostics[key]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
