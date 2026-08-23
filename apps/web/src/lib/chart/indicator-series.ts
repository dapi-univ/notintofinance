import type { HistoryBar } from "@/lib/api/types";
import type {
  IndicatorDefinition,
  IndicatorId,
  IndicatorRenderTheme,
  IndicatorSeriesDefinition,
} from "@/lib/indicators/registry";

export type IndicatorSeries = {
  setData: (data: ReturnType<IndicatorSeriesDefinition["transform"]>) => void;
};

type SyncIndicatorSeriesOptions<TSeries extends IndicatorSeries> = {
  bars: HistoryBar[];
  definitions: IndicatorDefinition[];
  enabled: ReadonlySet<IndicatorId>;
  theme: IndicatorRenderTheme;
  seriesById: Map<IndicatorId, Map<string, TSeries>>;
  createSeries: (
    definition: IndicatorDefinition,
    seriesDefinition: IndicatorSeriesDefinition,
  ) => TSeries;
  removeSeries: (series: TSeries) => void;
};

export function syncIndicatorSeries<TSeries extends IndicatorSeries>({
  bars,
  definitions,
  enabled,
  theme,
  seriesById,
  createSeries,
  removeSeries,
}: SyncIndicatorSeriesOptions<TSeries>): void {
  for (const [id, group] of seriesById) {
    if (!enabled.has(id)) {
      group.forEach((series) => removeSeries(series));
      seriesById.delete(id);
    }
  }

  for (const definition of definitions) {
    if (!enabled.has(definition.id)) continue;
    let group = seriesById.get(definition.id);
    if (!group) {
      group = new Map<string, TSeries>();
      seriesById.set(definition.id, group);
    }
    const expected = new Set(
      definition.rendering.series.map((seriesDefinition) => seriesDefinition.id),
    );
    for (const [seriesId, series] of group) {
      if (!expected.has(seriesId)) {
        removeSeries(series);
        group.delete(seriesId);
      }
    }
    for (const seriesDefinition of definition.rendering.series) {
      let series = group.get(seriesDefinition.id);
      if (!series) {
        series = createSeries(definition, seriesDefinition);
        group.set(seriesDefinition.id, series);
      }
      series.setData(seriesDefinition.transform(bars, theme));
    }
  }
}
