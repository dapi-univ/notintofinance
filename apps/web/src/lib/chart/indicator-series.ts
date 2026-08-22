import type { HistoryBar } from "@/lib/api/types";
import type { IndicatorDefinition, IndicatorId } from "@/lib/indicators/registry";

export type IndicatorSeries = {
  setData: (data: ReturnType<IndicatorDefinition["transform"]>) => void;
};

type SyncIndicatorSeriesOptions<TSeries extends IndicatorSeries> = {
  bars: HistoryBar[];
  definitions: IndicatorDefinition[];
  enabled: ReadonlySet<IndicatorId>;
  seriesById: Map<IndicatorId, TSeries>;
  createSeries: (definition: IndicatorDefinition) => TSeries;
  removeSeries: (series: TSeries) => void;
};

export function syncIndicatorSeries<TSeries extends IndicatorSeries>({
  bars,
  definitions,
  enabled,
  seriesById,
  createSeries,
  removeSeries,
}: SyncIndicatorSeriesOptions<TSeries>): void {
  for (const [id, series] of seriesById) {
    if (!enabled.has(id)) {
      removeSeries(series);
      seriesById.delete(id);
    }
  }

  for (const definition of definitions) {
    if (!enabled.has(definition.id)) continue;
    let series = seriesById.get(definition.id);
    if (!series) {
      series = createSeries(definition);
      seriesById.set(definition.id, series);
    }
    series.setData(definition.transform(bars));
  }
}
