"use client";

import { Activity, ChevronDown } from "lucide-react";

import {
  indicatorDefinitions,
  indicatorGroups,
  type IndicatorId,
} from "@/lib/indicators/registry";

type Props = {
  enabled: Set<IndicatorId>;
  onToggle: (id: IndicatorId) => void;
};

export function IndicatorMenu({ enabled, onToggle }: Props) {
  return (
    <details className="indicator-menu">
      <summary>
        <Activity aria-hidden="true" size={14} />
        <span>Indicators</span>
        <span className="indicator-menu__count" aria-label={`${enabled.size} indicators enabled`}>{enabled.size}</span>
        <ChevronDown aria-hidden="true" size={13} />
      </summary>
      <div className="indicator-menu__panel">
        {indicatorGroups.map((group) => (
          <section className="indicator-group" key={group.id} aria-labelledby={`indicator-group-${group.id}`}>
            <p className="indicator-menu__title" id={`indicator-group-${group.id}`}>{group.label}</p>
            {indicatorDefinitions.filter((indicator) => indicator.category === group.id).map((indicator) => {
              const required = indicator.id === "volume";
              return (
                <label key={indicator.id} className="indicator-option">
                  <input
                    type="checkbox"
                    checked={enabled.has(indicator.id)}
                    disabled={required}
                    onChange={() => onToggle(indicator.id)}
                  />
                  <span>
                    <strong>{indicator.label}</strong>
                    <small>{indicator.normalization ?? "Raw shares"}{required ? " · required" : ""}</small>
                  </span>
                </label>
              );
            })}
          </section>
        ))}
      </div>
    </details>
  );
}
