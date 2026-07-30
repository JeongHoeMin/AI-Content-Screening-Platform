from __future__ import annotations

from dataclasses import dataclass

from app.candidates.candidate_selection_policy import CandidateSelectionPolicy
from app.models.candidate_selection import (
    DEFAULT_RANKING_POLICY_CONFIG,
    CandidateEvaluation,
    CandidateReasonCode,
    CandidateSelectionResult,
    CandidateStatus,
    RankingPolicyConfig,
    not_eligible_reason_for,
    selected_reason_for,
)
from app.models.recommendation import (
    RecommendationDecision,
    RecommendationResult,
)


@dataclass(frozen=True)
class RuleCandidateSelectionPolicy(CandidateSelectionPolicy):
    """Applies one injected ranking config without changing recommendation values."""

    config: RankingPolicyConfig = DEFAULT_RANKING_POLICY_CONFIG

    def select(self, recommendation: RecommendationResult) -> CandidateSelectionResult:
        indexed_decisions: tuple[tuple[int, RecommendationDecision], ...] = tuple(
            enumerate(recommendation.decisions)
        )
        eligible_indexes: tuple[int, ...] = tuple(
            index
            for index, decision in indexed_decisions
            if self.config.catalog.entry_for(decision.action).eligible
        )
        ordered_eligible_indexes: tuple[int, ...] = tuple(
            sorted(
                eligible_indexes,
                key=lambda index: (
                    self.config.catalog.entry_for(
                        recommendation.decisions[index].action
                    ).priority,
                    -recommendation.decisions[index].score,
                    index,
                ),
            )
        )
        selected_ranks: dict[int, int] = {
            index: rank
            for rank, index in enumerate(
                ordered_eligible_indexes[: self.config.max_candidates],
                start=1,
            )
        }
        evaluations: tuple[CandidateEvaluation, ...] = tuple(
            self._evaluate(index, decision, selected_ranks)
            for index, decision in indexed_decisions
        )
        return CandidateSelectionResult(
            policy_version=self.config.policy_version,
            evaluations=evaluations,
        )

    def _evaluate(
        self,
        input_index: int,
        decision: RecommendationDecision,
        selected_ranks: dict[int, int],
    ) -> CandidateEvaluation:
        entry = self.config.catalog.entry_for(decision.action)
        if not entry.eligible:
            return CandidateEvaluation(
                decision=decision,
                status=CandidateStatus.NOT_ELIGIBLE,
                reason_code=not_eligible_reason_for(decision.action),
                input_index=input_index,
            )
        rank: int | None = selected_ranks.get(input_index)
        if rank is not None:
            return CandidateEvaluation(
                decision=decision,
                status=CandidateStatus.SELECTED,
                reason_code=selected_reason_for(decision.action),
                input_index=input_index,
                rank=rank,
            )
        return CandidateEvaluation(
            decision=decision,
            status=CandidateStatus.OUTSIDE_LIMIT,
            reason_code=CandidateReasonCode.EXCLUDED_OUTSIDE_CANDIDATE_LIMIT,
            input_index=input_index,
        )
