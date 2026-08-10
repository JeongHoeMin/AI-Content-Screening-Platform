"use client";

import { safeHref } from "@/lib/format";
import type { AnalysisItem } from "@/lib/types";

export function AnalysisCards({ analyses }: { analyses: AnalysisItem[] }) {
  return (
    <section className="panel">
      <h2>전체 수집 뉴스 분석</h2>
      <div className="cards">
        {analyses.length === 0 ? (
          <p className="empty">추천 실행 후 전체 뉴스의 분석 과정을 표시합니다.</p>
        ) : (
          analyses.map((item) => (
            <article key={item.id} className="card analysis-card">
              <small>{item.source}</small>
              <h3>{item.title}</h3>
              <p>
                <strong>{item.status}</strong>
              </p>
              {item.summary && <p>{item.summary}</p>}
              <div>
                {item.event_titles.length === 0 ? (
                  <span className="badge">이벤트 없음</span>
                ) : (
                  item.event_titles.map((title, index) => (
                    <span key={`${item.id}-event-${index}`} className="badge">
                      {title}
                    </span>
                  ))
                )}
              </div>
              {item.event_evidence.map((evidence, evidenceIndex) => (
                <div key={`${item.id}-evidence-${evidenceIndex}`}>
                  <h4>{evidence.event_title}</h4>
                  {evidence.quotes.map((quote, quoteIndex) => (
                    <blockquote key={`${item.id}-quote-${evidenceIndex}-${quoteIndex}`}>
                      {`문단 ${quote.paragraph_index}: ${quote.quote}`}
                    </blockquote>
                  ))}
                  <a
                    href={safeHref(evidence.source_url)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    원문 보기
                  </a>
                </div>
              ))}
              {item.relevance !== null && (
                <p>
                  {`관련성 ${item.relevance} · 중요도 ${item.importance} · 신뢰도 ${item.credibility}`}
                </p>
              )}
              {item.reasons.length > 0 && <p>{item.reasons.join(" · ")}</p>}
              {item.validation_status && <p>교차검증: {item.validation_status}</p>}
            </article>
          ))
        )}
      </div>
    </section>
  );
}
