import type {
  PerformanceItem,
  RunHistoryItem,
  RunHistoryResponse,
} from "./types";

/** Keep already-rendered runs stable while one run's prices are refreshed. */
export function replaceHistoryRun(
  history: RunHistoryResponse,
  refreshedRun: RunHistoryItem,
): RunHistoryResponse {
  return {
    ...history,
    runs: history.runs.map((run) =>
      run.run_id === refreshedRun.run_id ? refreshedRun : run,
    ),
  };
}

/** Apply one entry-price recovery without hiding or reloading the full history. */
export function replaceHistoryItem(
  history: RunHistoryResponse,
  refreshedItem: PerformanceItem,
): RunHistoryResponse {
  return {
    ...history,
    runs: history.runs.map((run) =>
      run.run_id !== refreshedItem.run_id
        ? run
        : {
            ...run,
            items: run.items.map((item) =>
              item.recommendation_index === refreshedItem.recommendation_index
                ? refreshedItem
                : item,
            ),
          },
    ),
  };
}
